from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable

from .automation import find_ableton_app_path, osascript, wait_for_live_window
from .errors import DependencyError, ExportAutomationError
from .models import ExportItemResult, ExportJob, ExportResult
from .naming import escape_applescript, stem_file_name
from .preflight import run_export_preflight


EXPORT_TIMEOUT = 120
RETRY_ATTEMPTS = 2
ProgressCallback = Callable[[str, str], None]
CancelCheck = Callable[[], bool]


def wait_for_new_wav(
    stems_dir: Path,
    export_start: float,
    timeout: int = EXPORT_TIMEOUT,
    clock=time.time,
    sleep=time.sleep,
) -> Path | None:
    deadline = clock() + timeout
    while clock() < deadline:
        for file_path in stems_dir.glob("*.wav"):
            try:
                stat = file_path.stat()
                if stat.st_mtime >= export_start:
                    size_before = stat.st_size
                    sleep(0.3)
                    if file_path.stat().st_size == size_before and size_before > 0:
                        return file_path
            except FileNotFoundError:
                continue
        sleep(0.2)
    return None


def verify_exported_file(output_path: Path) -> None:
    if not output_path.exists():
        raise ExportAutomationError(f"Expected exported file was not created: {output_path.name}")
    if output_path.suffix.lower() != ".wav":
        raise ExportAutomationError(f"Exported file has unexpected extension: {output_path.name}")
    if output_path.stat().st_size <= 0:
        raise ExportAutomationError(f"Exported file is empty: {output_path.name}")


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
    ) -> bool:
        del project_folder
        callback = progress or (lambda _event, _message: None)
        pyautogui = self.pyautogui
        pyautogui.FAILSAFE = False
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
        name_escaped = escape_applescript(output_path.stem)
        if output_path.exists():
            output_path.unlink()

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
        new_file = wait_for_new_wav(stems_dir, export_start, timeout=EXPORT_TIMEOUT, sleep=self.sleep)
        if new_file is None:
            raise ExportAutomationError("Timed out waiting for exported WAV file.")

        if new_file != output_path:
            if output_path.exists():
                output_path.unlink()
            new_file.rename(output_path)
        verify_exported_file(output_path)
        return True

    def trigger_export(
        self,
        output_path: Path,
        project_folder: Path,
        navigate_folder: bool = True,
        progress: ProgressCallback | None = None,
    ) -> bool:
        callback = progress or (lambda _event, _message: None)
        last_error: ExportAutomationError | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                callback("attempt", f"Export attempt {attempt}/{self.retry_attempts}")
                return self._trigger_export_once(
                    output_path,
                    project_folder,
                    navigate_folder=navigate_folder,
                    progress=callback,
                )
            except ExportAutomationError as exc:
                last_error = exc
                callback("retry", f"Attempt {attempt} failed: {exc}")
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
    first_export = True
    callback("preflight", "Running export preflight checks")
    run_export_preflight(
        ableton_client=ableton_client,
        project_folder=job.project_folder,
        song_name=job.song_name,
        app_path_finder=export_automation.app_path_finder,
        script_runner=export_automation.script_runner,
    )
    original_solos = {track.index: ableton_client.get_track_solo(track.index) for track in tracks}

    try:
        for position, track in enumerate(tracks, start=1):
            output_path = job.stems_dir / stem_file_name(
                job.custom_song_name or job.song_name,
                track.name,
                key=job.key,
                bpm=job.bpm,
                index=position,
                format_string=job.stem_name_format,
            )
            callback("stem", f"{position}/{len(tracks)} {track.name}")

            if should_cancel():
                callback("cancelled", "Export cancelled before next stem")
                break

            if job.replace_mode == "keep" and output_path.exists():
                items.append(ExportItemResult(track=track, output_path=output_path, status="skipped"))
                callback("skipped", f"Skipped {track.name}")
                continue

            for selected_track in tracks:
                ableton_client.set_track_solo(selected_track.index, False)
            ableton_client.set_track_solo(track.index, True)
            time.sleep(0.3)

            try:
                export_automation.trigger_export(
                    output_path,
                    job.project_folder,
                    navigate_folder=first_export,
                    progress=callback,
                )
            except ExportAutomationError as exc:
                items.append(ExportItemResult(track=track, output_path=output_path, status="failed", error=str(exc)))
                callback("failed", f"{track.name}: {exc}")
            else:
                items.append(ExportItemResult(track=track, output_path=output_path, status="success"))
                callback("success", f"Exported {track.name}")
                first_export = False
            time.sleep(0.5)
    finally:
        for track in tracks:
            ableton_client.set_track_solo(track.index, original_solos[track.index])

    return ExportResult(job=job, items=items)
