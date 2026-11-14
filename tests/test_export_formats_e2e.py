"""End-to-end export run against a simulated Ableton (fake UI + fake OSC).

Drives AppState -> execute_export_job -> ExportAutomation with the real
AppleScript text. The fake "Ableton" reads the folder and file name out of
that script and writes the file in whatever format the scenario picks.

Writes tests/artifacts/export_formats.json so results can be compared run to run.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import stems.export as export_module
from stems.export import ExportAutomation, execute_export_job
from stems.models import ProjectContext, StemTrack
from stems.state import AppState

ARTIFACT = Path(__file__).parent / "artifacts" / "export_formats.json"
FOLDER_RE = re.compile(r'set value of text field 1 of s to "(.*?)"')
NAME_RE = re.compile(r'set value of text field 1 of w to "(.*?)"')


class FakeOSC:
    def __init__(self):
        self.solo = {}

    def get_track_count(self):
        return 3

    def get_track_solo(self, index):
        return self.solo.get(index, False)

    def set_track_solo(self, index, soloed):
        self.solo[index] = soloed


class FakePyAutoGUI:
    FAILSAFE = False
    PAUSE = 0.0

    def hotkey(self, *_keys):
        pass

    def press(self, _key):
        pass


class FakeAbleton:
    """Plays Ableton: writes NAME.<ext> into the folder the script typed."""

    def __init__(self, extension: str, fail: bool = False):
        self.extension = extension
        self.fail = fail
        self.export_calls = 0

    def __call__(self, script: str, timeout: int = 20) -> str:
        del timeout
        if "count of windows" in script:
            return "1"
        self.export_calls += 1
        if self.fail:
            return "ERROR: filename field not found"
        folder = Path(FOLDER_RE.search(script).group(1))
        name = NAME_RE.search(script).group(1)
        (folder / f"{name}{self.extension}").write_bytes(b"audio-bytes")
        return "ok"


def _run(project: Path, extension: str, replace_mode: str, fail: bool = False):
    ableton = FakeAbleton(extension, fail=fail)
    automation = ExportAutomation(
        pyautogui_module=FakePyAutoGUI(),
        runner=lambda *_a, **_k: None,
        sleep=lambda _s: None,
        script_runner=ableton,
        app_path_finder=lambda: "/Applications/Ableton Live.app",
        window_waiter=lambda _name, timeout=8.0: True,
    )
    state = AppState(FakeOSC())
    state.project = ProjectContext(song_name="Song", project_folder=project, bpm=120)
    state.detected_tracks = [StemTrack(index=0, name="DRUMS"), StemTrack(index=1, name="BASS")]
    job = state.build_export_job(key="C Major", replace_mode=replace_mode)
    events = []
    result = execute_export_job(
        job, FakeOSC(), automation, progress=lambda e, m: events.append((e, m))
    )
    return job, result, events


def test_export_formats_existing_files_and_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(export_module.time, "sleep", lambda _s: None)
    project = tmp_path / "Song Project"
    project.mkdir()
    (project / "Song.als").write_bytes(b"")
    # A stems folder from an earlier day already sits in the project.
    old_folder = project / "Song - March 01 2026 - Stems - C Major 120 BPM"
    old_folder.mkdir()
    report = {}

    # 1. MP3 export into the reused folder.
    job, result, _ = _run(project, ".mp3", "replace")
    assert job.stems_dir == old_folder
    assert [i.status for i in result.items] == ["success", "success"]
    assert all(i.output_path.suffix == ".mp3" and i.output_path.exists() for i in result.items)
    report["mp3_into_existing_folder"] = sorted(p.name for p in old_folder.iterdir())

    # 2. Replace: AIFF over the MP3s. Old files go, new ones stay.
    _, result, _ = _run(project, ".aiff", "replace")
    assert [i.status for i in result.items] == ["success", "success"]
    names = sorted(p.name for p in old_folder.iterdir() if not p.name.startswith("."))
    assert all(name.endswith(".aiff") for name in names) and len(names) == 2
    assert not any(p.name.startswith(".") for p in old_folder.iterdir())
    report["replace_mp3_with_aiff"] = names

    # 3. Skip: nothing new gets written.
    _, result, _ = _run(project, ".wav", "keep")
    assert [i.status for i in result.items] == ["skipped", "skipped"]
    report["skip_existing"] = [i.status for i in result.items]

    # 4. Keep both: new "(2)" copies next to the old ones.
    _, result, _ = _run(project, ".wav", "keep_both")
    assert all(i.output_path.name.endswith(" (2).wav") for i in result.items)
    report["keep_both"] = sorted(p.name for p in old_folder.iterdir())

    # 5. Failure: retried, flagged with a short reason, old file restored.
    before = sorted(p.name for p in old_folder.iterdir())
    _, result, events = _run(project, ".wav", "replace", fail=True)
    assert [i.status for i in result.items] == ["failed", "failed"]
    assert any(e == "retry" for e, _ in events)
    failed_messages = [m for e, m in events if e == "failed"]
    assert failed_messages == ["DRUMS: Couldn't type name", "BASS: Couldn't type name"]
    assert sorted(p.name for p in old_folder.iterdir()) == before
    report["failure_messages"] = failed_messages

    ARTIFACT.parent.mkdir(exist_ok=True)
    ARTIFACT.write_text(json.dumps(report, indent=2) + "\n")
