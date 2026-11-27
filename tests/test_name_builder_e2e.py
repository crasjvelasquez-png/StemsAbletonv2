"""E2E tests for the block-based name builder in the real PreferencesDialog.

Failure modes considered:
- bad parse round-trip: blocks serialize to a different string than the preset.
- edit not saved: block edits do not reach preferences_changed / the saved format.
- preset not syncing: picking a preset leaves stale blocks, or edits keep a preset selected.
- invalid name accepted: removing {track}/{index} is saved instead of rejected.
- duplicate token: the same part can be added twice from the Add menu.
"""
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from stems.preferences import BUILTIN_FOLDER_NAMING_PRESETS, BUILTIN_STEM_NAMING_PRESETS, Preferences
from stems.ui.preferences_dialog import PreferencesDialog

ARTIFACTS = Path(__file__).parent / "artifacts"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(app):
    dlg = PreferencesDialog(Preferences())
    dlg.show()
    app.processEvents()
    yield dlg
    dlg.close()


def test_every_builtin_preset_round_trips(dialog):
    for builder, presets in ((dialog.stem_builder, BUILTIN_STEM_NAMING_PRESETS),
                             (dialog.folder_builder, BUILTIN_FOLDER_NAMING_PRESETS)):
        for preset in presets:
            builder.line.setText(preset.format_string)
            assert builder._serialize(builder.blocks()) == preset.format_string


def test_preset_rebuilds_blocks_and_edits_switch_to_my_own(dialog, app):
    saved = []
    dialog.preferences_changed.connect(saved.append)
    compact = dialog.stem_choice.findText("Compact")
    dialog.stem_choice.setCurrentIndex(compact)
    assert dialog.stem_builder.blocks() == [("token", "song"), ("text", "_"), ("token", "track")]
    assert len(dialog.stem_builder._buttons) == 3

    dialog.stem_builder.add_text("_")
    dialog.stem_builder.add_token("bpm")
    assert dialog.stem_choice.currentText() == "Custom"
    assert saved[-1].stem_name_format == "{song}_{track}_{bpm}"


def test_add_move_remove_and_looks_like(dialog):
    b = dialog.stem_builder
    dialog.stem_choice.setCurrentIndex(dialog.stem_choice.findText("Compact"))
    b.add_text(" - ")
    b.add_token("artist")
    assert dialog.stem_format.text() == "{song}_{track} - {artist}"
    assert dialog.stem_looks_like.text() == "MySong_DRUMS - Artist Name"
    b.move_block(4, -1)
    assert dialog.stem_format.text() == "{song}_{track}{artist} - "
    b.move_block(2, 1)
    assert dialog.stem_format.text() == "{song}_{artist}{track} - "
    b.remove_block(4)
    b.move_block(2, 1)
    assert dialog.stem_format.text() == "{song}_{track}{artist}"
    assert dialog.stem_looks_like.text() == "MySong_DRUMSArtist Name"


def test_folder_looks_like(dialog):
    dialog.folder_choice.setCurrentIndex(dialog.folder_choice.findText("Compact"))
    assert dialog.folder_looks_like.text() == "MySong - Stems"


def test_invalid_stem_name_shows_error_and_keeps_last_valid(dialog):
    b = dialog.stem_builder
    dialog.stem_choice.setCurrentIndex(dialog.stem_choice.findText("Compact"))
    saved = []
    dialog.preferences_changed.connect(saved.append)
    b.remove_block(2)  # {track}
    assert not dialog.stem_error.isHidden()
    assert saved[-1].stem_name_format == "{song}_{track}"
    assert dialog.preferences.stem_name_format == "{song}_{track}"
    b.add_token("index")
    assert dialog.stem_error.isHidden()
    assert saved[-1].stem_name_format == "{song}_{index}"


def test_add_menu_disables_used_tokens(dialog, monkeypatch):
    from PySide6.QtWidgets import QMenu
    from stems.ui import name_builder
    seen = {}

    class FakeMenu(QMenu):
        def exec(self, *_a, **_k):
            seen.update({a.text(): a.isEnabled() for a in self.actions() if a.text()})
            return None

    monkeypatch.setattr(name_builder, "QMenu", FakeMenu)
    dialog.stem_choice.setCurrentIndex(dialog.stem_choice.findText("Compact"))
    dialog.stem_builder._show_add_menu()
    assert seen["Song"] is False and seen["Track"] is False and seen["Artist"] is True
    assert "Your Own Text…" in seen


def test_text_toggle_and_screenshot(dialog, app):
    b = dialog.stem_builder
    assert b.line.isHidden()
    b.toggle_button.click()
    assert not b.line.isHidden() and b.toggle_button.text() == "Hide Text"
    b.toggle_button.click()
    assert b.line.isHidden()

    dialog.stem_choice.setCurrentIndex(dialog.stem_choice.findText("Artist first"))
    b.add_text(" - ")
    b.add_token("bpm")
    b.add_token("key")
    app.processEvents()
    ARTIFACTS.mkdir(exist_ok=True)
    assert dialog.grab().save(str(ARTIFACTS / "name_builder.png"))
    (ARTIFACTS / "name_builder.json").write_text(json.dumps({
        "stem_format": dialog.stem_format.text(),
        "folder_format": dialog.folder_format.text(),
        "stem_blocks": b.blocks(),
        "stem_looks_like": dialog.stem_looks_like.text(),
        "folder_looks_like": dialog.folder_looks_like.text(),
        "dialog_size": [dialog.width(), dialog.height()],
    }, indent=2))
