import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from stems.models import ExportJob, StemTrack
from stems.ui.export_confirmation_dialog import ExportConfirmationDialog


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def make_job(destination: Path, count: int = 6, replace_mode: str = "replace") -> ExportJob:
    tracks = [StemTrack(index=index, name=f"TRACK_{index + 1}") for index in range(count)]
    return ExportJob(
        song_name="Neon Tide",
        project_folder=destination.parent,
        stems_dir=destination,
        tracks=tracks,
        replace_mode=replace_mode,
    )


def test_plural_copy_and_replace_mode(app, tmp_path):
    destination = tmp_path / "External Volume" / "Exports" / "Neon Tide Stems"
    dialog = ExportConfirmationDialog(make_job(destination), scale=1.0)

    assert dialog.heading_label.text() == "Ready to export 6 stems"
    assert dialog.export_button.text() == "Export 6 Stems"
    assert dialog.mode_label.text() == "Replace matching files"
    assert dialog.mode_label.property("modeState") == "replace"
    assert dialog.mode_label.objectName() == "exportConfirmationMode"


def test_singular_copy_and_skip_mode(app, tmp_path):
    destination = tmp_path / "Exports" / "Neon Tide Stems"
    dialog = ExportConfirmationDialog(make_job(destination, count=1, replace_mode="keep"), scale=1.0)

    assert dialog.heading_label.text() == "Ready to export 1 stem"
    assert dialog.export_button.text() == "Export 1 Stem"
    assert dialog.mode_label.text() == "Skip matching files"
    assert dialog.mode_label.property("modeState") == "keep"


def test_destination_shows_folder_and_parent_but_keeps_full_path_available(app, tmp_path):
    destination = tmp_path / "External Volume" / "Client Exports" / "Neon Tide Stems"
    dialog = ExportConfirmationDialog(make_job(destination), scale=1.0)
    full_path = str(destination.resolve())

    assert dialog.destination_label.text() == destination.name
    assert dialog.destination_parent_label.text() == destination.parent.name
    assert dialog.destination_label.toolTip() == full_path
    assert dialog.destination_label.accessibleDescription() == full_path


def test_track_count_names_and_direct_layout_for_eight_or_fewer(app, tmp_path):
    destination = tmp_path / "Exports" / "Stems"
    dialog = ExportConfirmationDialog(make_job(destination, count=8), scale=1.0)

    assert dialog.tracks_heading.text() == "Tracks (8)"
    assert dialog.tracks_label.text() == " · ".join(f"TRACK_{index}" for index in range(1, 9))
    assert dialog.tracks_label.isHidden() is False
    assert dialog.track_scroll_area.isHidden() is True


def test_track_list_caps_and_scrolls_above_eight(app, tmp_path):
    destination = tmp_path / "Exports" / "Stems"
    dialog = ExportConfirmationDialog(make_job(destination, count=12), scale=1.0)

    assert dialog.tracks_heading.text() == "Tracks (12)"
    assert dialog.tracks_label.isHidden() is True
    assert dialog.track_scroll_area.isHidden() is False
    assert dialog.track_scroll_area.maximumHeight() == 112
    assert dialog.track_scroll_area.widget().text().startswith("TRACK_1 · TRACK_2")


def test_buttons_have_explicit_hierarchy_and_escape_rejects(app, tmp_path):
    dialog = ExportConfirmationDialog(make_job(tmp_path / "Exports" / "Stems"), scale=1.0)
    dialog.show()
    app.processEvents()

    assert dialog.cancel_button.objectName() == "secondary"
    assert dialog.export_button.objectName() == "primaryAction"
    assert dialog.export_button.isDefault() is True

    QTest.keyClick(dialog, Qt.Key_Escape)
    app.processEvents()
    assert dialog.result() == QDialog.Rejected


def test_export_button_accepts_dialog(app, tmp_path):
    dialog = ExportConfirmationDialog(make_job(tmp_path / "Exports" / "Stems"), scale=1.0)

    dialog.export_button.click()

    assert dialog.result() == QDialog.Accepted


def test_dialog_uses_compact_minimum_width(app, tmp_path):
    dialog = ExportConfirmationDialog(make_job(tmp_path / "Exports" / "Stems"), scale=0.6)
    assert dialog.width() == 380
    assert dialog.layout().contentsMargins().left() >= 16
