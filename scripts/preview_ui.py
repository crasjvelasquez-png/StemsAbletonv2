"""Repeatable UI check with simulated Ableton data.
Run: python3 scripts/preview_ui.py (screenshots: /tmp/stems-ui-preview).
Failure cases: clipped compact layout, long labels expanding the window,
empty list without guidance, selection losing export availability, unreadable
progress states. Real Ableton export is intentionally outside this preview.
"""
import os
import sys
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from stems.ui import main_window as m
from stems.models import StemTrack, ProjectContext
from stems.preferences import Preferences
from stems.state import AppState

app = QApplication([])
out = Path(os.environ.get('PREVIEW_DIR', '/tmp/stems-ui-preview'))
out.mkdir(parents=True, exist_ok=True)
with patch.object(m.OSCGateway, 'start_listener', lambda self: None), patch.object(m.MainWindow, '_build_tray', lambda self: None), patch.object(m.QTimer, 'singleShot', lambda *args: None), patch.object(m.PreferencesStore, 'load', return_value=Preferences(sticky_panel_position=False)), patch.object(m.PreferencesStore, 'save'), patch.object(m, 'is_launch_agent_installed', return_value=False):
    w = m.MainWindow()
    w.show()
    app.processEvents()
    app.processEvents()
    w.grab().save(str(out / 'empty.png'))
    state = AppState(object())
    state.project = ProjectContext(song_name='Neon Tide', project_folder=Path('/Music/Ableton/Neon Tide'), bpm=128)
    state.detected_tracks = [StemTrack(index=i, name=n) for i,n in enumerate(['DRUMS','BASS','SYNTHS','VOCALS'])]
    w._handle_scan_success(state, state.project)
    w.resize(620,760)
    app.processEvents()
    app.processEvents()
    w.grab().save(str(out / 'ready.png'))
    row = w.track_list.itemWidget(w.track_list.item(0))
    row.checkbox.click()
    assert w.selection_count_label.text() == '3 selected'
    row.checkbox.click()
    assert w.export_button.isEnabled()
    w.resize(480,560)
    app.processEvents()
    app.processEvents()
    w.grab().save(str(out / 'compact.png'))
    assert w.width() == 480
    w.resize(620,760)
    w.progress_bar.setRange(0,4)
    w._handle_export_progress('stem', '2/4 BASS')
    app.processEvents()
    app.processEvents()
    w.grab().save(str(out / 'progress.png'))
    w.close()
print(out)
