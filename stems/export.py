from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable

from .automation import find_ableton_app_path, osascript, wait_for_live_window
from .errors import DependencyError, ExportAutomationError
from .models import ExportItemResult, ExportJob, ExportResult, StemTrack
from .naming import AUDIO_EXTENSIONS, escape_applescript, stem_file_name
from .preflight import run_export_preflight


EXPORT_TIMEOUT = 180
RETRY_ATTEMPTS = 2
ProgressCallback = Callable[[str, str], None]
CancelCheck = Callable[[], bool]


def audio_base_name(name: str) -> str:
    """Strip a trailing audio extension (any case). Ableton adds its own."""
    lowered = name.lower()
    for ext in AUDIO_EXTENSIONS:
        if lowered.endswith(ext):
            return name[: -len(ext)]
    return name


def find_audio_files(folder: Path, base_name: str) -> list[Path]:
    """Every audio file in folder called base_name, whatever its format."""
    wanted = base_name.casefold()
    try:
        entries = list(folder.iterdir())
    except OSError:
        return []
    return [
        path for path in entries
        if path.is_file()
        and path.suffix.lower() in AUDIO_EXTENSIONS
        and path.name[: -len(path.suffix)].casefold() == wanted
    ]


def next_free_name(folder: Path, base_name: str) -> str:
    """First of 'NAME (2)', 'NAME (3)', ... with no audio file of any format."""
    counter = 2
    while find_audio_files(folder, f"{base_name} ({counter})"):
        counter += 1
    return f"{base_name} ({counter})"


def planned_stem_paths(job: ExportJob) -> list[tuple[StemTrack, Path]]:
    planned = []
    for position, track in enumerate(job.selected_tracks, start=1):
        name = stem_file_name(
            job.custom_song_name or job.song_name,
            track.name,
            key=job.key,
            bpm=job.bpm,
            index=position,
            format_string=job.stem_name_format,
            artist=job.artist,
        )
        planned.append((track, job.stems_dir / name))
    return planned


def find_conflicts(job: ExportJob) -> list[StemTrack]:
    """Selected stems that already have an audio file (any format) in the folder."""
    return [
        track for track, path in planned_stem_paths(job)
        if find_audio_files(path.parent, audio_base_name(path.name))
    ]


def wait_for_exported_audio(
    output_path: Path,
    export_start: float,
    timeout: int = EXPORT_TIMEOUT,
    clock=time.time,
    sleep=time.sleep,
) -> Path | None:
    """Wait for Ableton to finish writing NAME.<any audio format>."""
    base = audio_base_name(output_path.name)
    deadline = clock() + timeout
    while clock() < deadline:
        for candidate in find_audio_files(output_path.parent, base):
            try:
                stat = candidate.stat()
                if stat.st_mtime >= export_start and stat.st_size > 0:
                    size_before = stat.st_size
                    sleep(0.5)
                    if candidate.stat().st_size == size_before:
                        return candidate
            except FileNotFoundError:
                pass
        sleep(0.2)
    return None


def verify_exported_file(output_path: Path) -> None:
    if not output_path.exists():
        raise ExportAutomationError(f"Expected exported file was not created: {output_path.name}")
    if output_path.suffix.lower() not in AUDIO_EXTENSIONS:
        raise ExportAutomationError(f"Exported file is not audio: {output_path.name}")
    if output_path.stat().st_size <= 0:
        raise ExportAutomationError(f"Exported file is empty: {output_path.name}")


SHORT_REASONS = (
    ("export dialog never opened", "Ableton didn't open Export"),
    ("save window never appeared", "Save window didn't open"),
    ("destination folder", "Couldn't pick folder"),
    ("go to folder", "Couldn't pick folder"),
    ("filename field", "Couldn't type name"),
    ("timed out", "No file appeared"),
    ("empty", "File came out empty"),
    ("not audio", "Wrong file type"),
    ("was not created", "No file appeared"),
)


def short_failure_reason(message: str) -> str:
    lowered = message.lower()
    for needle, reason in SHORT_REASONS:
        if needle in lowered:
            return reason
    return "Ableton didn't respond"


class ExportAutomation:
    def __init__(
        self,
        pyautogui_module=None,
        runner=subprocess.run,
        sleep=time.sleep,
        script_runner=osascript,
        app_path_finder=find_ableton_app_path,
        window_waiter=wait_for_live_window,
    ) -> None:
        self.runner = runner
        self.sleep = sleep
        self.script_runner = script_runner
        self.app_path_finder = app_path_finder
        self.window_waiter = window_waiter
        self.retry_attempts = RETRY_ATTEMPTS

        if pyautogui_module is None:
            try:
                import pyautogui as imported_pyautogui
            except ImportError as exc:
                raise DependencyError("pyautogui not installed. Run: pip install pyautogui") from exc
            pyautogui_module = imported_pyautogui
        self.pyautogui = pyautogui_module

    def reset_export_ui(self) -> None:
        for _ in range(3):
            self.pyautogui.press("escape")
            self.sleep(0.2)

    def _trigger_export_once(
        self,
        output_path: Path,
        project_folder: Path,
        navigate_folder: bool = True,
        progress: ProgressCallback | None = None,
    ) -> Path:
        del project_folder
        callback = progress or (lambda _event, _message: None)
        pyautogui = self.pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.15

        stems_dir = output_path.parent
        callback("activate", "Activating Ableton")
        app_path = self.app_path_finder()
        if app_path:
            self.runner(["open", app_path], check=False)
        self.sleep(1.5)

        callback("dialog", "Opening Export dialog")
        pyautogui.hotkey("command", "shift", "r")
        if not self.window_waiter("Export Audio/Video", timeout=8.0):
            pyautogui.press("escape")
            self.sleep(0.5)
            pyautogui.hotkey("command", "shift", "r")
            if not self.window_waiter("Export Audio/Video", timeout=8.0):
                raise ExportAutomationError("Export dialog never opened.")

        callback("save", "Opening Save dialog")
        pyautogui.press("return")
        if not self.window_waiter("Save", timeout=6.0):
            raise ExportAutomationError("Save window never appeared.")

        folder_escaped = escape_applescript(str(stems_dir))
        name_escaped = escape_applescript(audio_base_name(output_path.name))

        go_to_folder_block = ""
        if navigate_folder:
            go_to_folder_block = f'''
        keystroke "g" using {{command down, shift down}}
        set gotFolder to false
        repeat 50 times
            repeat with w in every window
                if name of w is "Save" then
                    if (count of sheets of w) > 0 then
                        set s to first sheet of w
                        set value of text field 1 of s to "{folder_escaped}"
                        delay 0.2
                        if value of text field 1 of s is not "{folder_escaped}" then
                            return "ERROR: destination folder was not entered correctly"
                        end if
                        key code 36
                        set gotFolder to true
                        exit repeat
                    end if
                end if
            end repeat
            if gotFolder then exit repeat
            delay 0.1
        end repeat
        if not gotFolder then
            return "ERROR: Go to Folder sheet not found"
        end if
        repeat 50 times
            set stillOpen to false
            repeat with w in every window
                if name of w is "Save" and (count of sheets of w) > 0 then
                    set stillOpen to true
                end if
            end repeat
            if not stillOpen then exit repeat
            delay 0.1
        end repeat
'''

        export_start = time.time()
        result = self.script_runner(
            f'''
tell application "System Events"
    tell process "Live"
{go_to_folder_block}
        set gotName to false
        repeat with w in every window
            if name of w is "Save" then
                try
                    set value of text field 1 of w to "{name_escaped}"
                    delay 0.3
                    key code 36
                    set gotName to true
                end try
            end if
        end repeat

        if not gotName then
            return "ERROR: filename field not found"
        end if

        delay 1.0
        repeat with w in every window
            if name of w is "Save" then
                if (count of sheets of w) > 0 then
                    set s to first sheet of w
                    try
                        click button "Replace" of s
                    end try
                end if
            end if
        end repeat

        return "ok"
    end tell
end tell''',
            timeout=20,
        )
        if result.startswith("ERROR") or not result:
            raise ExportAutomationError(result or "Export scripting failed.")

        callback("wait", "Waiting for exported file")
        new_file = wait_for_exported_audio(output_path, export_start, timeout=EXPORT_TIMEOUT, sleep=self.sleep)
        if new_file is None:
            raise ExportAutomationError("Timed out waiting for the exported audio file.")
        verify_exported_file(new_file)
        return new_file

    def trigger_export(
        self,
        output_path: Path,
        project_folder: Path,
        navigate_folder: bool = True,
        progress: ProgressCallback | None = None,
    ) -> Path:
        callback = progress or (lambda _event, _message: None)
        last_error: ExportAutomationError | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                callback("attempt", "Preparing stem" if attempt == 1 else "Trying this stem again")
                return self._trigger_export_once(
                    output_path,
                    project_folder,
                    navigate_folder=navigate_folder,
                    progress=callback,
                )
            except ExportAutomationError as exc:
                last_error = exc
                if attempt < self.retry_attempts:
                    callback("retry", f"Retrying: {short_failure_reason(str(exc))}")
                self.reset_export_ui()
        raise ExportAutomationError(
            f"Export failed after {self.retry_attempts} attempts: {last_error}"
        ) from last_error


def execute_export_job(
    job: ExportJob,
    ableton_client,
    export_automation: ExportAutomation,
    progress: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> ExportResult:
    callback = progress or (lambda _event, _message: None)
    should_cancel = cancel_check or (lambda: False)
    tracks = job.selected_tracks
    items: list[ExportItemResult] = []
    callback("preflight", "Checking Ableton is ready")
    run_export_preflight(
        ableton_client=ableton_client,
        project_folder=job.project_folder,
        song_name=job.song_name,
        app_path_finder=export_automation.app_path_finder,
        script_runner=export_automation.script_runner,
    )
    job.stems_dir.mkdir(parents=True, exist_ok=True)
    original_solos = {track.index: ableton_client.get_track_solo(track.index) for track in tracks}

    try:
        for position, (track, planned_path) in enumerate(planned_stem_paths(job), start=1):
            callback("stem", f"{position}/{len(tracks)} {track.name}")

            if should_cancel():
                callback("cancelled", "Export cancelled before next stem")
                break

            base = audio_base_name(planned_path.name)
            existing = find_audio_files(job.stems_dir, base)
            if existing and job.replace_mode == "keep":
                items.append(ExportItemResult(track=track, output_path=existing[0], status="skipped"))
                callback("skipped", f"Skipped {track.name}")
                continue
            if existing and job.replace_mode == "keep_both":
                base = next_free_name(job.stems_dir, base)
                existing = []
            output_path = job.stems_dir / (base + ".wav")  # Ableton picks the real extension.

            for selected_track in tracks:
                ableton_client.set_track_solo(selected_track.index, False)
            ableton_client.set_track_solo(track.index, True)
            time.sleep(0.3)

            # Replace: park old files aside so the old take survives a failed export.
            parked = _park_files(existing)
            try:
                exported = export_automation.trigger_export(
                    output_path,
                    job.project_folder,
                    navigate_folder=True,
                    progress=callback,
                )
            except ExportAutomationError as exc:
                _restore_parked(parked)
                items.append(ExportItemResult(track=track, output_path=output_path, status="failed", error=str(exc)))
                callback("failed", f"{track.name}: {short_failure_reason(str(exc))}")
            else:
                _discard_parked(parked)
                final_path = exported if isinstance(exported, Path) else output_path
                items.append(ExportItemResult(track=track, output_path=final_path, status="success"))
                callback("success", f"Exported {track.name}")
            time.sleep(0.5)
    finally:
        for track in tracks:
            ableton_client.set_track_solo(track.index, original_solos[track.index])

    return ExportResult(job=job, items=items)


def _park_files(paths: list[Path]) -> list[tuple[Path, Path]]:
    parked = []
    for path in paths:
        hidden = path.with_name(f".{path.name}.stems-old")
        try:
            path.replace(hidden)
        except OSError:
            continue
        parked.append((path, hidden))
    return parked


def _restore_parked(parked: list[tuple[Path, Path]]) -> None:
    for original, hidden in parked:
        try:
            if not original.exists():
                hidden.replace(original)
        except OSError:
            pass


def _discard_parked(parked: list[tuple[Path, Path]]) -> None:
    for _original, hidden in parked:
        try:
            hidden.unlink()
        except OSError:
            pass
