import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox, QTabWidget

from stems.models import ExportItemResult, ExportJob, ExportResult, ProjectContext, StemTrack
from stems.naming import stems_folder_name
from stems.preferences import Preferences
from stems.state import AppState
from stems.ui import main_window as main_window_module
from stems.ui.preferences_dialog import PreferencesDialog


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


def test_selected_count_updates_and_context_actions_only_show_when_useful(window, app):
    track = StemTrack(index=0, name="DRUMS")
    window.state.detected_tracks = [track]
    window._populate_tracks([track])
    row = window.track_list.itemWidget(window.track_list.item(0))

    row.checkbox.setChecked(False)
    assert window.selection_count_label.text() == "0 selected"

    assert window.open_button.isHidden() is True
    assert window.cancel_button.isHidden() is True
    window._set_open_available(True)
    window._set_cancel_available(True)
    app.processEvents()
    assert window.open_button.isHidden() is False
    assert window.cancel_button.isHidden() is False


def test_saved_window_size_restores_clamps_and_persists(window):
    window.preferences.panel_width = 535
    window.preferences.panel_height = 605
    window._apply_preferences_to_ui()
    assert window.size() == QSize(535, 605)

    window.preferences.panel_width = -1
    window.preferences.panel_height = 0
    window._apply_preferences_to_ui()
    assert window.size() == QSize(*main_window_module.REFERENCE_WINDOW_SIZE)

    window.preferences.panel_width = 100_000
    window.preferences.panel_height = 100_000
    window._apply_preferences_to_ui()
    available = window.screen().availableGeometry()
    assert window.width() == available.width()
    assert window.height() == available.height()

    window.resize(600, 700)
    window.close()
    assert window.preferences.panel_width == 600
    assert window.preferences.panel_height == 700


def test_preferences_reset_restores_defaults(window, app, monkeypatch):
    dialog = PreferencesDialog(Preferences(auto_open_folder=False, menubar_mode=True), window)
    saved = []
    dialog.preferences_changed.connect(saved.append)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.Reset)

    dialog.reset_button.click()
    app.processEvents()

    assert saved[-1].auto_open_folder is True
    assert saved[-1].menubar_mode is False
    assert dialog.saved_label.text() == "Saved"


def test_preferences_changes_save_immediately(window, app):
    dialog = PreferencesDialog(Preferences(), window)
    saved = []
    dialog.preferences_changed.connect(saved.append)

    dialog.auto_open_folder.setChecked(False)
    app.processEvents()

    assert saved[-1].auto_open_folder is False
    assert dialog.saved_label.property("saveState") == "saved"


def test_naming_preferences_use_separate_presets_and_target_specific_tokens(window, app):
    dialog = PreferencesDialog(Preferences(), window)
    dialog.findChild(QTabWidget, "preferencesTabs").setCurrentIndex(1)
    dialog.show()
    app.processEvents()

    assert dialog.stem_editor.preset_combo.count() == 3
    assert dialog.folder_editor.preset_combo.count() == 3
    assert [button.text() for button in dialog.stem_editor.token_buttons] == [
        "{song}", "{track}", "{bpm}", "{key}", "{date}", "{index}",
    ]
    assert [button.text() for button in dialog.folder_editor.token_buttons] == [
        "{song}", "{bpm}", "{key}", "{date}",
    ]
    assert dialog.stem_editor.default_badge.isVisible()
    assert dialog.folder_editor.default_badge.isVisible()


def test_naming_token_inserts_at_cursor_and_invalid_format_disables_ok(window, app):
    dialog = PreferencesDialog(Preferences(), window)
    dialog.stem_name_format.setText(".wav")
    dialog.stem_name_format.setCursorPosition(0)
    dialog.stem_editor.token_buttons[1].click()
    app.processEvents()

    assert dialog.stem_name_format.text() == "{track}.wav"
    assert dialog.saved_label.property("saveState") == "pending"
    dialog.stem_name_format.setText("{song}.wav")
    assert "unique name" in dialog.stem_editor.error_label.text()
    assert dialog.saved_label.property("saveState") == "pending"


def test_custom_naming_presets_can_be_created_and_defaulted(window, app, monkeypatch):
    names = iter([("Client Delivery", True), ("Project Folder", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: next(names))
    dialog = PreferencesDialog(Preferences(), window)

    dialog.stem_name_format.setText("{index}_{track}_{song}.wav")
    dialog.stem_editor._save_preset()
    dialog.stem_editor._set_default()
    dialog.folder_name_format.setText("{song} - Delivery")
    dialog.folder_editor._save_preset()
    dialog.folder_editor._set_default()
    updated = dialog.to_preferences()

    assert updated.stem_name_presets[0].name == "Client Delivery"
    assert updated.folder_name_presets[0].name == "Project Folder"
    assert updated.stem_name_format == "{index}_{track}_{song}.wav"
    assert updated.folder_name_format == "{song} - Delivery"
    assert updated.default_stem_name_preset_id.startswith("custom-stem-")
    assert updated.default_folder_name_preset_id.startswith("custom-folder-")


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

    assert window.song_value.text() == "Neon Tide"
    assert window.bpm_value.text() == "128 BPM"
    assert window.path_value.toolTip() == str(project.project_folder)
    assert window.progress_label.text() == "Scan complete"
    assert window.progress_card.property("progressState") == "idle"
    assert window.progress_card.isHidden() is True
    assert window.summary_label.text() == "Detected 2 stems"
    assert window.export_button.isEnabled() is True
    assert window.export_button.objectName() == "primaryAction"
    assert window.scan_button.objectName() == "secondary"


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


def test_incremental_project_and_key_preview_updates_do_not_create_folders(window, app, tmp_path):
    project_folder = tmp_path / "Project"
    project_folder.mkdir()
    project = ProjectContext(song_name="Song", project_folder=project_folder, bpm=128)
    state = AppState(object())
    state.project = project
    state.detected_tracks = [StemTrack(index=0, name="DRUMS")]
    window._handle_scan_success(state, project)

    previews = []
    for project_name, key in (("Q", ""), ("Quer", "C"), ("Querida", "C Minor")):
        window.project_name_input.setText(project_name)
        window.key_input.setText(key)
        app.processEvents()
        previews.append(window.destination_value.text())
        assert window.destination_value.text() == stems_folder_name(project_name, key or None, 128)

    assert len(set(previews)) == 3
    assert list(project_folder.iterdir()) == []


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

    assert window.song_value.text() == "Existing Song"
    assert window.bpm_value.text() == "121"
    assert window.path_value.text() == "/Users/c4milo/Music/Ableton/Projects/Existing Song"
    assert window.progress_label.text() == "Scan failed"
    assert window.progress_card.property("progressState") == "scan-failed"
    assert window.progress_card.isHidden() is False
    assert window.progress_bar.property("progressState") == "scan-failed"
    assert window.progress_percent_label.text() == "0%"
    assert window.progress_bar.isHidden() is True
    assert window.progress_percent_label.isHidden() is True
    assert window.summary_label.text() == message
    assert window.summary_label.toolTip() == message
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
    assert window.progress_card.isHidden() is False
    assert window.summary_label.text() == message
    assert window.summary_label.wordWrap() is True
    assert window.summary_label.toolTip() == message
    assert window.progress_bar.isHidden() is True
    assert window.progress_percent_label.isHidden() is True
    assert warnings == [("Export failed", message)]


def test_export_progress_shows_current_stem_count_destination_and_percent(window, tmp_path):
    tracks = [StemTrack(index=index, name=name) for index, name in enumerate(("KICK", "DRUMS", "BASS", "SYNTH"))]
    window.current_job = ExportJob(
        song_name="Neon Tide",
        project_folder=tmp_path,
        stems_dir=tmp_path / "Stems",
        tracks=tracks,
    )
    window.progress_bar.setRange(0, 4)
    window.progress_bar.setValue(0)

    window._handle_export_progress("stem", "2/4 DRUMS")

    assert window.progress_card.isHidden() is False
    assert window.progress_label.text() == "Exporting DRUMS"
    assert window.progress_percent_label.text() == "25%"
    assert window.progress_percent_label.isHidden() is False
    assert window.progress_bar.isHidden() is False
    assert window.summary_label.text() == f"1 of 4 stems · Saving to {tmp_path / 'Stems'}"


def test_completed_export_persists_without_redundant_meter_until_next_operation(window, tmp_path):
    tracks = [StemTrack(index=0, name="DRUMS"), StemTrack(index=1, name="BASS")]
    job = ExportJob(
        song_name="Neon Tide",
        project_folder=tmp_path,
        stems_dir=tmp_path / "Stems",
        tracks=tracks,
    )
    result = ExportResult(
        job=job,
        items=[
            ExportItemResult(track=track, output_path=tmp_path / f"{track.name}.wav", status="success")
            for track in tracks
        ],
    )
    window.current_job = job
    window.progress_bar.setRange(0, 2)

    window._handle_export_finished(result)

    assert window.progress_card.isHidden() is False
    assert window.progress_card.property("progressState") == "export-complete"
    assert window.progress_label.text() == "Export complete"
    assert window.summary_label.text() == f"Exported 2/2 stems to {tmp_path / 'Stems'}."
    assert window.progress_bar.isHidden() is True
    assert window.progress_percent_label.isHidden() is True

    window._set_progress_state("scanning")
    assert window.progress_card.isHidden() is False
    assert window.progress_card.property("progressState") == "scanning"

    window._set_progress_state("idle")
    assert window.progress_card.isHidden() is True


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
    window.current_job = job
    window.progress_bar.setRange(0, 3)
    window.progress_bar.setValue(1)

    window.cancel_export()
    window._handle_export_finished(result)

    assert worker.cancelled is True
    assert window.progress_label.text() == "Export cancelled"
    assert window.progress_card.property("progressState") == "cancelled"
    assert window.progress_bar.value() == 1
    assert window.progress_bar.isHidden() is False
    assert window.progress_percent_label.text() == "33%"
    assert "Cancelled after exporting 1/3 stems" in window.summary_label.text()


@pytest.mark.parametrize("dialog_result, should_start", [(0, False), (1, True)])
def test_confirm_export_starts_only_after_dialog_acceptance(window, tmp_path, monkeypatch, dialog_result, should_start):
    track = StemTrack(index=0, name="DRUMS")
    window.current_job = ExportJob(
        song_name="Neon Tide",
        project_folder=tmp_path,
        stems_dir=tmp_path / "Stems",
        tracks=[track],
    )
    monkeypatch.setattr(window, "update_destination_preview", lambda: None)
    starts: list[int] = []
    monkeypatch.setattr(window, "start_export", lambda: starts.append(1))

    class FakeConfirmationDialog:
        Accepted = 1

        def __init__(self, job, parent, *, scale):
            assert job is window.current_job
            assert parent is window
            assert scale == window.ui_scale

        def exec(self):
            return dialog_result

    monkeypatch.setattr(main_window_module, "ExportConfirmationDialog", FakeConfirmationDialog)

    window.confirm_export()

    assert len(starts) == (1 if should_start else 0)
