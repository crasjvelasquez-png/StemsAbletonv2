import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QMessageBox, QVBoxLayout

from stems.models import ExportItemResult, ExportJob, ExportResult, ProjectContext, StemTrack
from stems.preferences import Preferences
from stems.ui import main_window as main_window_module
from stems.ui.main_window import ElidedLabel


class DummyGateway:
    def start_listener(self) -> None:
        pass

    def stop_listener(self) -> None:
        pass


class DummyPreferencesStore:
    def load(self) -> Preferences:
        return Preferences(sticky_panel_position=False)

    def save(self, _preferences: Preferences) -> None:
        pass


class DummyState:
    def __init__(self, *_args, **_kwargs) -> None:
        self.detected_tracks: list[StemTrack] = []


class ExportReadyState:
    def __init__(self, tracks: list[StemTrack], project: ProjectContext) -> None:
        self.detected_tracks = tracks
        self.project = project

    def build_export_job(
        self,
        key: str | None = None,
        replace_mode: str = "replace",
        destination_root: str | Path | None = None,
        custom_song_name: str | None = None,
        stem_name_format: str | None = None,
        folder_name_format: str | None = None,
    ) -> ExportJob:
        stems_root = Path(destination_root) if destination_root is not None else self.project.project_folder
        return ExportJob(
            song_name=self.project.song_name,
            project_folder=self.project.project_folder,
            stems_dir=stems_root / "Stems",
            tracks=self.detected_tracks,
            bpm=self.project.bpm,
            key=key,
            replace_mode=replace_mode,
            custom_song_name=custom_song_name,
            stem_name_format=stem_name_format,
            folder_name_format=folder_name_format,
        )


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


@pytest.fixture
def window(app, monkeypatch):
    monkeypatch.setattr(main_window_module, "PreferencesStore", DummyPreferencesStore)
    monkeypatch.setattr(main_window_module, "OSCGateway", DummyGateway)
    monkeypatch.setattr(main_window_module, "AbletonClient", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(main_window_module, "AppState", DummyState)
    monkeypatch.setattr(main_window_module.MainWindow, "_build_tray", lambda self: None)
    monkeypatch.setattr(main_window_module.QTimer, "singleShot", staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(main_window_module, "is_launch_agent_installed", lambda: False)

    panel = main_window_module.MainWindow()
    yield panel
    panel.close()


def test_current_set_card_uses_stronger_info_blocks(window):
    assert window.song_value.objectName() == "currentSetValue"
    assert window.bpm_value.objectName() == "currentSetValue"
    assert window.path_value.objectName() == "currentSetPathValue"
    assert isinstance(window.song_value, ElidedLabel)
    assert isinstance(window.path_value, ElidedLabel)


def test_progress_card_uses_bounded_status_components(window):
    assert window.progress_card.objectName() == "progressCard"
    assert window.progress_card.property("progressState") == "idle"
    assert window.progress_label.objectName() == "progressStatePill"
    assert window.progress_label.property("progressState") == "idle"
    assert window.progress_status_module.objectName() == "progressStatusModule"
    assert window.progress_icon_label.objectName() == "progressStatusIcon"
    assert window.progress_percent_label.objectName() == "progressPercent"
    assert window.progress_percent_label.text() == "0%"
    assert window.progress_bar.objectName() == "progressBar"
    assert window.progress_bar.isTextVisible() is False
    assert window.progress_bar.height() == 6
    assert window.progress_summary_area.maximumHeight() == 60
    assert window.summary_label.wordWrap() is True
    assert window.summary_label.textInteractionFlags() & Qt.TextSelectableByMouse


def test_main_content_scrolls_without_overlapping_export_and_progress(window, app):
    window.resize(700, 860)
    window.show()
    app.processEvents()

    root_layout = window.centralWidget().layout()
    scroll_area = root_layout.itemAt(0).widget()
    action_widget = root_layout.itemAt(root_layout.count() - 1).widget()
    export_card = window.key_input.parentWidget().parentWidget()

    assert scroll_area.objectName() == "mainScrollArea"
    assert export_card.geometry().bottom() < window.progress_card.geometry().top()
    assert scroll_area.geometry().bottom() < action_widget.geometry().top()


def test_export_controls_stay_within_their_rows_when_window_is_constrained(window, app):
    window.resize(504, 680)
    window.show()
    app.processEvents()

    for row_widget, row_data in zip(window.export_row_widgets, window.export_row_data):
        for control in row_data[1:]:
            assert control.geometry().bottom() <= row_widget.contentsRect().bottom()


def test_bottom_action_row_matches_button_hierarchy(window):
    window_layout = window.centralWidget().layout()
    action_widget = window_layout.itemAt(window_layout.count() - 1).widget()
    action_layout = action_widget.layout()
    buttons = [action_layout.itemAt(index).widget() for index in range(action_layout.count())]

    assert [button.text() for button in buttons] == [
        "Scan Current Set",
        "Open Folder",
        "Cancel",
        "Export Stems",
    ]
    assert window.scan_button.objectName() == "primaryAction"
    assert window.open_button.objectName() == "secondary"
    assert window.cancel_button.objectName() == "secondary"
    assert window.export_button.objectName() == "secondary"
    assert window.export_button.isEnabled() is False
    assert action_layout.spacing() == 12
    assert all(button.property("actionBarButton") is True for button in buttons)
    assert {button.minimumHeight() for button in buttons} == {30}
    assert {button.maximumHeight() for button in buttons} == {30}
    assert window.preferences_button.objectName() == "headerAction"
    assert window.preferences_button not in buttons


def test_scan_success_updates_current_set_values(window, monkeypatch):
    monkeypatch.setattr(window, "update_destination_preview", lambda: None)

    tracks = [
        StemTrack(index=0, name="DRUMS"),
        StemTrack(index=1, name="BASS"),
    ]
    state = SimpleNamespace(detected_tracks=tracks)
    project = ProjectContext(
        song_name="Neon Tide",
        project_folder=Path("/Users/c4milo/Music/Ableton/Projects/Very Long Folder Name/Neon Tide"),
        bpm=128,
    )

    window._handle_scan_success(state, project)

    assert window.song_value.fullText() == "Neon Tide"
    assert window.bpm_value.text() == "128"
    assert window.path_value.fullText() == str(project.project_folder)
    assert window.progress_label.text() == "Scan complete"
    assert window.progress_card.property("progressState") == "idle"
    assert window.summary_label.text() == "Detected 2 stems."
    assert window.export_button.isEnabled() is True


def test_export_button_tracks_selected_stems(window):
    tracks = [
        StemTrack(index=0, name="DRUMS"),
        StemTrack(index=1, name="BASS"),
    ]
    project = ProjectContext(
        song_name="Neon Tide",
        project_folder=Path("/Users/c4milo/Music/Ableton/Projects/Neon Tide"),
        bpm=128,
    )
    state = ExportReadyState(tracks, project)

    window._handle_scan_success(state, project)

    assert window.export_button.isEnabled() is True

    for track in tracks:
        row = window.track_list.itemWidget(window.item_by_track_name[track.name])
        row.checkbox.setChecked(False)

    assert window.export_button.isEnabled() is False

    row = window.track_list.itemWidget(window.item_by_track_name["DRUMS"])
    row.checkbox.setChecked(True)

    assert window.export_button.isEnabled() is True


def test_scan_failure_keeps_current_set_values_and_updates_status(window, monkeypatch):
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )

    window.song_value.setText("Existing Song")
    window.bpm_value.setText("121")
    window.path_value.setText("/Users/c4milo/Music/Ableton/Projects/Existing Song")

    message = "Ableton Live is not reachable."
    window._handle_scan_failure(message)

    assert window.song_value.fullText() == "Existing Song"
    assert window.bpm_value.text() == "121"
    assert window.path_value.fullText() == "/Users/c4milo/Music/Ableton/Projects/Existing Song"
    assert window.progress_label.text() == "Scan failed"
    assert window.progress_card.property("progressState") == "scan-failed"
    assert window.progress_status_module.property("progressState") == "scan-failed"
    assert window.progress_icon_label.text() == "!"
    assert window.progress_bar.property("progressState") == "scan-failed"
    assert window.progress_percent_label.text() == "0%"
    assert window.summary_label.text() == message
    assert window.progress_summary_area.maximumHeight() == 60
    assert warnings == [("Scan failed", message)]


def test_export_failure_uses_error_state_with_readable_summary(window, monkeypatch):
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    message = "Export failed after 3 attempts: " + "Unable to confirm Ableton save dialog. " * 8

    window._handle_export_failed(message)

    assert window.progress_label.text() == "Export failed"
    assert window.progress_card.property("progressState") == "export-failed"
    assert window.progress_status_module.property("progressState") == "export-failed"
    assert window.progress_icon_label.text() == "!"
    assert window.summary_label.text() == message
    assert window.summary_label.wordWrap() is True
    assert window.progress_summary_area.maximumHeight() == 60
    assert warnings == [("Export failed", message)]


def test_cancelled_export_keeps_cancelled_state(window, tmp_path):
    class FakeWorker:
        def __init__(self) -> None:
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

    worker = FakeWorker()
    track = StemTrack(index=0, name="DRUMS")
    job = ExportJob(
        song_name="Neon Tide",
        project_folder=tmp_path,
        stems_dir=tmp_path / "Stems",
        tracks=[track, StemTrack(index=1, name="BASS"), StemTrack(index=2, name="SYNTH")],
    )
    result = ExportResult(
        job=job,
        items=[ExportItemResult(track=track, output_path=tmp_path / "DRUMS.wav", status="success")],
    )
    window.export_worker = worker
    window.progress_bar.setRange(0, 3)
    window.progress_bar.setValue(1)

    window.cancel_export()
    window._handle_export_finished(result)

    assert worker.cancelled is True
    assert window.progress_label.text() == "Export cancelled"
    assert window.progress_card.property("progressState") == "cancelled"
    assert window.progress_bar.value() == 1
    assert "Cancelled after exporting 1/3 stems" in window.summary_label.text()


# --- Responsive design tests ---


def test_compact_mode_stacks_form_rows(window, app):
    window.resize(300, 380)
    window.show()
    app.processEvents()

    for rw in window.current_row_widgets:
        assert isinstance(rw.layout(), QVBoxLayout), "Current set rows should stack vertically in compact mode"

    for rw in window.export_row_widgets:
        assert isinstance(rw.layout(), QVBoxLayout), "Export rows should stack vertically in compact mode"


def test_responsive_layout_uses_readable_minimum_and_breakpoint(window):
    assert window.minimumSize() == QSize(*main_window_module.MIN_WINDOW_SIZE)
    assert main_window_module._uses_compact_layout(QSize(300, 380)) is True
    assert main_window_module._uses_compact_layout(QSize(520, 650)) is False


def test_compact_mode_restores_horizontal_rows(window, app):
    window.resize(300, 380)
    window.show()
    app.processEvents()

    window.resize(540, 680)
    app.processEvents()

    for rw in window.current_row_widgets:
        assert isinstance(rw.layout(), QHBoxLayout), "Current set rows should be horizontal at normal size"

    for rw in window.export_row_widgets:
        assert isinstance(rw.layout(), QHBoxLayout), "Export rows should be horizontal at normal size"


def test_action_bar_becomes_grid_in_compact_mode(window, app):
    window.resize(300, 380)
    window.show()
    app.processEvents()

    assert isinstance(window.action_layout, QGridLayout), "Action bar should use grid layout in compact mode"


def test_elided_label_shows_tooltip(app):
    label = ElidedLabel("A very long song name that should definitely get truncated at some point")
    label.setFixedWidth(80)
    label.show()
    app.processEvents()

    assert label.fullText() == "A very long song name that should definitely get truncated at some point"
    assert label.toolTip() != ""


def test_preferences_dialog_accepts_scale(app):
    prefs = Preferences(sticky_panel_position=False)
    dialog = main_window_module.PreferencesDialog(prefs, scale=0.6)
    assert dialog.minimumWidth() == max(280, round(440 * 0.6))
    dialog.close()


def test_preferences_dialog_naming_editor_round_trips_format(app):
    prefs = Preferences(
        stem_name_format="{song}_{track}.wav",
        folder_name_format="{song} - Stems",
        sticky_panel_position=False,
    )
    dialog = main_window_module.PreferencesDialog(prefs, scale=0.6)

    dialog.stem_name_format.add_piece("text", " - ")
    dialog.stem_name_format.add_piece("token", "bpm")

    updated = dialog.to_preferences()

    assert updated.stem_name_format == "{song}_{track}.wav - {bpm}"
    assert updated.folder_name_format == "{song} - Stems"
    assert "128" in dialog.stem_preview_label.text()
    assert dialog.folder_preview_label.text() == "MySong - Stems"
    dialog.close()


def test_close_is_deferred_while_scan_thread_is_running(window):
    event = SimpleNamespace(ignored=False)
    event.ignore = lambda: setattr(event, "ignored", True)
    window.scan_thread = object()
    window.show()

    window.closeEvent(event)

    assert event.ignored is True
    assert window._close_requested is True
    assert window.isVisible() is False

    window.scan_thread = None


def test_deferred_close_runs_after_workers_finish(window, monkeypatch):
    callbacks = []
    monkeypatch.setattr(
        main_window_module.QTimer,
        "singleShot",
        staticmethod(lambda _delay, callback: callbacks.append(callback)),
    )
    window._close_requested = True

    window._finish_deferred_close()

    assert len(callbacks) == 1
    assert callbacks[0] == window.close


def test_app_quit_waits_for_active_worker_threads(window):
    class FakeThread:
        def __init__(self):
            self.quit_called = False
            self.wait_called = False

        def isRunning(self):
            return True

        def quit(self):
            self.quit_called = True

        def wait(self):
            self.wait_called = True

    scan_thread = FakeThread()
    export_thread = FakeThread()
    window.scan_thread = scan_thread
    window.export_thread = export_thread

    window.shutdown_workers()

    assert scan_thread.quit_called is True
    assert scan_thread.wait_called is True
    assert export_thread.quit_called is True
    assert export_thread.wait_called is True

    window.scan_thread = None
    window.export_thread = None
