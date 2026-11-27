"""End-to-end test for keeping Stems on top and bringing it back to front during export.

Drives MainWindow -> start_export -> ExportWorker -> execute_export_job -> ExportAutomation
with fake Ableton/OSC/osascript hooks, recording window flags and frontmost transitions
across every export phase.

Writes tests/artifacts/export_frontmost.json for repeatable verification.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

import stems.export as export_module
from stems.export import ExportAutomation
from stems.models import ProjectContext, StemTrack
from stems.preferences import Preferences
from stems.state import AppState
from stems.ui import main_window as main_window_module
from stems.ui import worker as worker_module

ARTIFACT = Path(__file__).parent / "artifacts" / "export_frontmost.json"
FOLDER_RE = re.compile(r'set value of text field 1 of s to "(.*?)"')
NAME_RE = re.compile(r'set value of text field 1 of w to "(.*?)"')


class DummyGateway:
    def start_listener(self) -> None:
        pass

    def stop_listener(self) -> None:
        pass


class DummyPreferencesStore:
    def __init__(self, prefs: Preferences) -> None:
        self._prefs = prefs

    def load(self) -> Preferences:
        return self._prefs

    def save(self, _preferences: Preferences) -> None:
        pass


class FakeOSC:
    def __init__(self) -> None:
        self.solo: dict[int, bool] = {}

    def get_track_count(self) -> int:
        return 2

    def get_track_solo(self, index: int) -> bool:
        return self.solo.get(index, False)

    def set_track_solo(self, index: int, soloed: bool) -> None:
        self.solo[index] = soloed


class FakePyAutoGUI:
    FAILSAFE = False
    PAUSE = 0.0

    def hotkey(self, *_keys) -> None:
        pass

    def press(self, _key: str) -> None:
        pass


class FakeAbletonScript:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def __call__(self, script: str, timeout: int = 20) -> str:
        del timeout
        if "count of windows" in script:
            return "1"
        if self.fail:
            return "ERROR: filename field not found"
        folder = Path(FOLDER_RE.search(script).group(1))
        name = NAME_RE.search(script).group(1)
        (folder / f"{name}.wav").write_bytes(b"audio-bytes")
        return "ok"


def _make_window(monkeypatch, tmp_path: Path, *, auto_open_folder: bool, fail: bool = False):
    app = QApplication.instance() or QApplication([])
    timeline: list[dict] = []

    project_dir = tmp_path / "Song Project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "Song.als").write_bytes(b"")

    prefs = Preferences(auto_open_folder=auto_open_folder, replace_mode="replace")
    monkeypatch.setattr(main_window_module, "PreferencesStore", lambda: DummyPreferencesStore(prefs))
    monkeypatch.setattr(main_window_module, "OSCGateway", DummyGateway)
    monkeypatch.setattr(main_window_module, "AbletonClient", lambda *_a, **_k: FakeOSC())
    monkeypatch.setattr(main_window_module.QTimer, "singleShot", staticmethod(lambda *_a, **_k: None))
    monkeypatch.setattr(main_window_module, "is_launch_agent_installed", lambda: False)
    monkeypatch.setattr(export_module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_a, **_k: None)

    window = main_window_module.MainWindow()

    def record_open(cmd, **_kwargs):
        timeline.append({
            "action": "open_folder",
            "cmd": list(cmd),
            "stays_on_top": bool(window.windowFlags() & Qt.WindowStaysOnTopHint),
        })
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(main_window_module.subprocess, "run", record_open)

    def fake_bring_to_front(*_args, **_kwargs) -> bool:
        timeline.append({
            "action": "bring_to_front",
            "stays_on_top": bool(window.windowFlags() & Qt.WindowStaysOnTopHint),
            "progress_state": window._progress_state,
        })
        return True

    monkeypatch.setattr(main_window_module, "bring_process_to_front", fake_bring_to_front)

    def make_automation():
        return ExportAutomation(
            pyautogui_module=FakePyAutoGUI(),
            runner=lambda *_a, **_k: timeline.append({
                "action": "activate_ableton",
                "stays_on_top": bool(window.windowFlags() & Qt.WindowStaysOnTopHint),
            }),
            sleep=lambda _s: None,
            script_runner=FakeAbletonScript(fail=fail),
            app_path_finder=lambda: "/Applications/Ableton Live.app",
            window_waiter=lambda _name, timeout=8.0: True,
        )

    monkeypatch.setattr(worker_module, "ExportAutomation", make_automation)

    osc = FakeOSC()
    state = AppState(osc)
    project = ProjectContext(song_name="Song", project_folder=project_dir, bpm=120)
    tracks = [StemTrack(index=0, name="DRUMS"), StemTrack(index=1, name="BASS")]
    state.project = project
    state.detected_tracks = tracks
    window._handle_scan_success(state, project)
    window.show()
    app.processEvents()
    return app, window, timeline


def _wait_export_done(app: QApplication, window: main_window_module.MainWindow) -> None:
    for _ in range(500):
        app.processEvents()
        if window.export_thread is None:
            break
    assert window.export_thread is None


def test_export_stays_on_top_and_returns_to_front_e2e(tmp_path, monkeypatch):
    report: dict = {}

    # 1. Successful export with auto_open_folder=True:
    #    - Stays on top while Ableton activates for Save dialog
    #    - Brings Stems to front when Ableton starts printing ("wait") for each stem
    #    - Drops stays-on-top before opening Finder so Finder isn't covered
    #    - Focus activation right after finish does not wipe "Export complete"
    app, window, timeline = _make_window(monkeypatch, tmp_path / "ok", auto_open_folder=True)
    try:
        assert not bool(window.windowFlags() & Qt.WindowStaysOnTopHint)
        window.start_export()
        assert bool(window.windowFlags() & Qt.WindowStaysOnTopHint)
        _wait_export_done(app, window)

        assert not bool(window.windowFlags() & Qt.WindowStaysOnTopHint)
        assert window._progress_state == "export-complete"
        assert window.progress_label.text() == "Export complete"

        ableton_activations = [e for e in timeline if e["action"] == "activate_ableton"]
        front_calls = [e for e in timeline if e["action"] == "bring_to_front"]
        folder_opens = [e for e in timeline if e["action"] == "open_folder"]

        assert len(ableton_activations) == 2
        assert all(e["stays_on_top"] is True for e in ableton_activations)
        # At least once per stem during "wait" (printing) plus completion.
        assert len(front_calls) >= 3
        assert len(folder_opens) == 1
        assert folder_opens[0]["stays_on_top"] is False

        # Verify sequence: Ableton activates -> Stems comes back to front while printing
        actions = [e["action"] for e in timeline]
        first_ableton = actions.index("activate_ableton")
        first_front = actions.index("bring_to_front")
        assert first_ableton < first_front

        # Verify rescan guard was refreshed so focus doesn't wipe Export complete
        assert window._last_scan > 0
        report["success_timeline"] = timeline
    finally:
        window.close()

    # 2. Failed export (preflight failure):
    #    - Drops stays-on-top and brings Stems to front for the error state
    app2, window2, timeline2 = _make_window(monkeypatch, tmp_path / "fail", auto_open_folder=False)
    try:
        monkeypatch.setattr(
            worker_module,
            "ExportAutomation",
            lambda: ExportAutomation(
                pyautogui_module=FakePyAutoGUI(),
                runner=lambda *_a, **_k: None,
                sleep=lambda _s: None,
                script_runner=FakeAbletonScript(),
                app_path_finder=lambda: None,  # Triggers preflight failure
                window_waiter=lambda _name, timeout=8.0: True,
            ),
        )
        window2.start_export()
        _wait_export_done(app2, window2)

        assert not bool(window2.windowFlags() & Qt.WindowStaysOnTopHint)
        assert window2._progress_state == "export-failed"
        assert any(e["action"] == "bring_to_front" for e in timeline2)
        report["failed_timeline"] = timeline2
    finally:
        window2.close()

    ARTIFACT.parent.mkdir(exist_ok=True)
    ARTIFACT.write_text(json.dumps(report, indent=2) + "\n")
