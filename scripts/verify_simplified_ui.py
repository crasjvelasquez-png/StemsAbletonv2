"""Repeatable Qt flow check with fake Ableton/automation; never controls Live.

Failure cases: extra confirmation; stale set/track indices; lost partial selection;
readiness failures leaving Export enabled; clipboard overwritten; bad destination;
preferences silently choosing custom templates; busy-window rescans; close mid-worker.
Artifacts: screenshots and JSON in /tmp/stems-ui-verification by default.
"""
import json
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QComboBox
from stems.models import StemTrack
from stems.preferences import Preferences, PreferencesStore
from stems.state import AppState
from stems.ui import main_window as ui
from stems.ui import worker
from stems.ui.preferences_dialog import PreferencesDialog


def wait(app, condition):
    deadline = time.monotonic() + 5
    while not condition():
        app.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("Qt flow timed out")
        time.sleep(.01)
    app.processEvents()


def main():
    artifacts = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/stems-ui-verification")
    artifacts.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    class Gateway:
        def start_listener(self): pass
        def stop_listener(self): pass
    class Client:
        def __init__(self, *_):
            self.tracks = [dict(index=0, name="DRUMS"), dict(index=1, name="BASS")]
            self.solo = {0: False, 1: True}
        def get_track_count(self): return len(self.tracks)
        def get_bpm(self): return 128
        def get_all_tracks(self, count): return self.tracks
        def get_track_solo(self, index): return self.solo[index]
        def set_track_solo(self, index, value): self.solo[index] = value
    class Automation:
        app_path_finder = staticmethod(lambda: "/Applications/Live.app")
        script_runner = staticmethod(lambda *_a, **_kw: "1")
        def trigger_export(self, path, *_a, **_kw):
            path.write_bytes(b"fake-wave-for-flow-check")
    with TemporaryDirectory() as temp:
        root = Path(temp)
        store = PreferencesStore(root / "preferences.json")
        store.save(Preferences(auto_open_folder=False))
        client = Client()
        state = AppState(client, project_info_getter=lambda: (root, "Song"))
        with patch.object(ui, "PreferencesStore", return_value=store), patch.object(ui, "OSCGateway", Gateway), patch.object(ui, "AbletonClient", return_value=client), patch.object(ui, "AppState", return_value=state), patch.object(worker, "find_ableton_app_path", return_value="/Applications/Live.app"), patch.object(worker, "osascript", return_value="1"), patch.object(worker, "ExportAutomation", Automation), patch.object(ui, "is_launch_agent_installed", return_value=False):
            panel = ui.MainWindow()
            panel.show()
            wait(app, lambda: panel.project is not None and panel.scan_thread is None)
            assert panel.export_button.isEnabled()
            assert panel.retry_button.isHidden()
            assert not panel.findChildren(QComboBox)
            panel.grab().save(str(artifacts / "ready.png"))
            panel.resize(480, 560)
            app.processEvents()
            panel.grab().save(str(artifacts / "compact.png"))
            panel.track_list.itemWidget(panel.item_by_track_name["BASS"]).checkbox.setChecked(False)
            app.clipboard().setText("keep my clipboard")
            panel.export_button.click()
            wait(app, lambda: panel.current_result is not None and panel.export_thread is None and panel.scan_thread is None)
            assert [t.name for t in panel.current_result.job.selected_tracks] == ["DRUMS"]
            assert panel.current_result.success_count == 1
            assert app.clipboard().text() == "keep my clipboard"
            assert client.solo == {0: False, 1: True}
            panel.grab().save(str(artifacts / "complete.png"))
            previous = panel.current_result
            client.tracks = [dict(index=0, name="BASS"), dict(index=1, name="DRUMS")]
            panel.export_button.click()
            wait(app, lambda: panel.scan_thread is None)
            assert panel.current_result is previous
            assert "changed" in panel.summary_label.text().lower()
            panel.grab().save(str(artifacts / "set-changed.png"))
            dialog = PreferencesDialog(panel.preferences, panel)
            assert len(dialog.findChildren(QComboBox)) == 2
            assert all(combo.count() == 3 for combo in dialog.findChildren(QComboBox))
            dialog.show()
            app.processEvents()
            dialog.grab().save(str(artifacts / "preferences.png"))
            dialog.close()
            with patch.object(worker, "osascript", return_value="ERROR: not authorized"):
                panel.scan_current_set()
                wait(app, lambda: panel.scan_thread is None)
                assert not panel.export_button.isEnabled()
                assert not panel.retry_button.isHidden()
                assert "Accessibility" in panel.summary_label.text()
                panel.grab().save(str(artifacts / "accessibility-error.png"))
            panel.close()
        (artifacts / "result.json").write_text(json.dumps({"passed": True, "scope": "Qt application flow with fake Ableton and export automation; no live export", "checks": ["one click export", "partial selection", "solo restore", "clipboard preservation", "changed track guard", "readiness failure", "built in naming choices", "compact layout"]}, indent=2))
    print(artifacts)

if __name__ == "__main__": main()
