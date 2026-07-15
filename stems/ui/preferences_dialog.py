from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QFrame,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMenu,
        QMessageBox,
        QPushButton,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

from ..naming import (
    FOLDER_NAME_TOKENS,
    STEM_NAME_TOKENS,
    render_name,
    validate_name_format,
)
from ..preferences import (
    BUILTIN_FOLDER_NAMING_PRESETS,
    BUILTIN_STEM_NAMING_PRESETS,
    NamingPreset,
    Preferences,
    all_naming_presets,
    normalize_naming_preferences,
)
from .theme import stylesheet_for_scale


class NamingPresetEditor(QFrame):
    state_changed = Signal()

    def __init__(
        self,
        kind: str,
        title: str,
        presets: list[NamingPreset],
        default_preset_id: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.presets = deepcopy(presets)
        self.default_preset_id = default_preset_id
        self.builtin_ids = {preset.preset_id for preset in self.presets if preset.preset_id.startswith("builtin-")}
        self._loading = False
        self._dirty = False
        self._previous_preset_id = default_preset_id

        self.setObjectName("namingPresetCard")
        self.setAccessibleName(title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("preferencesFieldTitle")
        self.default_badge = QLabel("Default")
        self.default_badge.setObjectName("presetDefaultBadge")
        header.addWidget(heading)
        header.addStretch(1)
        header.addWidget(self.default_badge)
        layout.addLayout(header)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        self.preset_combo = QComboBox()
        self.preset_combo.setObjectName(f"{kind}PresetCombo")
        self.preset_combo.setAccessibleName(f"{title} preset")
        self.preset_combo.setMinimumHeight(36)
        preset_row.addWidget(self.preset_combo, 1)

        self.save_button = QPushButton("Save Preset")
        self.save_button.setObjectName("presetSecondaryAction")
        self.save_button.setAccessibleName(f"Save {title.lower()} preset")
        self.save_button.clicked.connect(self._save_preset)
        preset_row.addWidget(self.save_button)

        self.more_button = QPushButton("More")
        self.more_button.setObjectName("presetSecondaryAction")
        self.more_button.setAccessibleName(f"More {title.lower()} preset actions")
        self.more_menu = QMenu(self.more_button)
        self.new_action = self.more_menu.addAction("New preset")
        self.duplicate_action = self.more_menu.addAction("Duplicate preset")
        self.rename_action = self.more_menu.addAction("Rename preset")
        self.delete_action = self.more_menu.addAction("Delete preset")
        self.new_action.triggered.connect(self._new_preset)
        self.duplicate_action.triggered.connect(self._duplicate_preset)
        self.rename_action.triggered.connect(self._rename_preset)
        self.delete_action.triggered.connect(self._delete_preset)
        self.more_button.setMenu(self.more_menu)
        preset_row.addWidget(self.more_button)
        layout.addLayout(preset_row)

        template_label = QLabel("Template")
        template_label.setObjectName("preferencesSubLabel")
        layout.addWidget(template_label)
        self.format_input = QLineEdit()
        self.format_input.setObjectName(f"{kind}FormatInput")
        self.format_input.setAccessibleName(f"{title} template")
        self.format_input.setMinimumHeight(40)
        self.format_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.format_input)

        token_row = QHBoxLayout()
        token_row.setSpacing(6)
        token_label = QLabel("Insert")
        token_label.setObjectName("preferencesHint")
        token_row.addWidget(token_label)
        tokens = STEM_NAME_TOKENS if kind == "stem" else FOLDER_NAME_TOKENS
        self.token_buttons: list[QPushButton] = []
        for token in tokens:
            button = QPushButton("{" + token + "}")
            button.setObjectName("tokenButton")
            button.setAccessibleName(f"Insert {token} token")
            button.setMinimumHeight(36)
            button.clicked.connect(lambda _checked=False, value=token: self._insert_token(value))
            token_row.addWidget(button)
            self.token_buttons.append(button)
        token_row.addStretch(1)
        layout.addLayout(token_row)

        self.error_label = QLabel()
        self.error_label.setObjectName("preferencesError")
        self.error_label.setWordWrap(True)
        self.error_label.setAccessibleName(f"{title} validation error")
        layout.addWidget(self.error_label)

        footer = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setObjectName("preferencesHint")
        footer.addWidget(self.status_label)
        footer.addStretch(1)
        self.default_button = QPushButton("Set as Default")
        self.default_button.setObjectName("presetDefaultAction")
        self.default_button.setAccessibleName(f"Set {title.lower()} preset as default")
        self.default_button.clicked.connect(self._set_default)
        footer.addWidget(self.default_button)
        layout.addLayout(footer)

        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self._refresh_combo(default_preset_id)

    @property
    def selected_preset_id(self) -> str:
        return str(self.preset_combo.currentData() or "")

    @property
    def selected_preset(self) -> NamingPreset | None:
        return next((preset for preset in self.presets if preset.preset_id == self.selected_preset_id), None)

    @property
    def is_valid(self) -> bool:
        return validate_name_format(self.format_input.text(), self.kind) is None

    @property
    def can_accept(self) -> bool:
        return self.is_valid and not (self._dirty and self.selected_preset_id in self.builtin_ids)

    def _refresh_combo(self, selected_id: str) -> None:
        self._loading = True
        self.preset_combo.clear()
        for preset in self.presets:
            suffix = " — Default" if preset.preset_id == self.default_preset_id else ""
            self.preset_combo.addItem(preset.name + suffix, preset.preset_id)
        index = self.preset_combo.findData(selected_id)
        self.preset_combo.setCurrentIndex(max(index, 0))
        self._loading = False
        self._load_selected_preset()

    def _load_selected_preset(self) -> None:
        preset = self.selected_preset
        if preset is None:
            return
        self._loading = True
        self.format_input.setText(preset.format_string)
        self._loading = False
        self._dirty = False
        self._previous_preset_id = preset.preset_id
        self._update_state()

    def _on_preset_changed(self) -> None:
        if self._loading:
            return
        if self._dirty:
            answer = QMessageBox.question(
                self,
                "Discard template changes?",
                "Switching presets will discard the unsaved template changes.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self._refresh_combo(self._previous_preset_id)
                return
        self._load_selected_preset()
        self.state_changed.emit()

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        preset = self.selected_preset
        self._dirty = preset is None or self.format_input.text().strip() != preset.format_string
        self._update_state()
        self.state_changed.emit()

    def _update_state(self) -> None:
        preset = self.selected_preset
        error = validate_name_format(self.format_input.text(), self.kind)
        self.error_label.setText(error or "")
        self.error_label.setVisible(bool(error))
        is_builtin = self.selected_preset_id in self.builtin_ids
        is_default = self.selected_preset_id == self.default_preset_id
        self.default_badge.setVisible(is_default)
        self.default_button.setVisible(not is_default)
        self.default_button.setEnabled(not is_default and not self._dirty and error is None)
        self.save_button.setEnabled(self._dirty and error is None)
        self.save_button.setText("Save as Preset" if is_builtin else "Save Changes")
        self.rename_action.setEnabled(not is_builtin)
        self.delete_action.setEnabled(not is_builtin)
        if error:
            self.status_label.setText("Fix the template before saving.")
        elif self._dirty and is_builtin:
            self.status_label.setText("Save as a custom preset to keep these changes.")
        elif self._dirty:
            self.status_label.setText("Unsaved preset changes")
        elif is_builtin:
            self.status_label.setText("Built-in preset")
        else:
            self.status_label.setText("Custom preset")

    def _insert_token(self, token: str) -> None:
        value = "{" + token + "}"
        cursor = self.format_input.cursorPosition()
        text = self.format_input.text()
        self.format_input.setText(text[:cursor] + value + text[cursor:])
        self.format_input.setCursorPosition(cursor + len(value))
        self.format_input.setFocus()

    def _prompt_name(self, title: str, initial: str = "") -> str | None:
        name, accepted = QInputDialog.getText(self, title, "Preset name", text=initial)
        name = name.strip()
        if not accepted or not name:
            return None
        if any(preset.name.casefold() == name.casefold() for preset in self.presets):
            QMessageBox.warning(self, "Preset name already used", "Choose a unique preset name.")
            return None
        return name

    def _create_custom(self, name: str, format_string: str) -> None:
        preset = NamingPreset(f"custom-{self.kind}-{uuid4().hex}", name, format_string.strip())
        self.presets.append(preset)
        self._refresh_combo(preset.preset_id)
        self.state_changed.emit()

    def _save_preset(self) -> None:
        if not self.is_valid:
            return
        preset = self.selected_preset
        if preset is None:
            return
        if preset.preset_id in self.builtin_ids:
            name = self._prompt_name("Save Naming Preset", preset.name + " Copy")
            if name:
                self._create_custom(name, self.format_input.text())
            return
        preset.format_string = self.format_input.text().strip()
        self._dirty = False
        self._update_state()
        self.state_changed.emit()

    def _new_preset(self) -> None:
        name = self._prompt_name("New Naming Preset")
        if name:
            self._create_custom(name, self.format_input.text())

    def _duplicate_preset(self) -> None:
        preset = self.selected_preset
        if preset is None:
            return
        name = self._prompt_name("Duplicate Naming Preset", preset.name + " Copy")
        if name:
            self._create_custom(name, self.format_input.text())

    def _rename_preset(self) -> None:
        preset = self.selected_preset
        if preset is None or preset.preset_id in self.builtin_ids:
            return
        old_name = preset.name
        preset.name = ""
        name = self._prompt_name("Rename Naming Preset", old_name)
        preset.name = name or old_name
        if name:
            self._refresh_combo(preset.preset_id)
            self.state_changed.emit()

    def _delete_preset(self) -> None:
        preset = self.selected_preset
        if preset is None or preset.preset_id in self.builtin_ids:
            return
        if preset.preset_id == self.default_preset_id:
            QMessageBox.information(
                self,
                "Default preset",
                "Set another preset as the default before deleting this one.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Delete preset?",
            f'Delete “{preset.name}”? This cannot be undone after you press OK.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.presets = [item for item in self.presets if item.preset_id != preset.preset_id]
            self._refresh_combo(self.default_preset_id)
            self.state_changed.emit()

    def _set_default(self) -> None:
        if not self.is_valid or self._dirty:
            return
        self.default_preset_id = self.selected_preset_id
        self._refresh_combo(self.default_preset_id)
        self.state_changed.emit()

    def apply_to_preferences(self, preferences: Preferences) -> None:
        preset = self.selected_preset
        if self._dirty and preset is not None and preset.preset_id not in self.builtin_ids:
            preset.format_string = self.format_input.text().strip()
            self._dirty = False
        custom = [deepcopy(item) for item in self.presets if item.preset_id not in self.builtin_ids]
        if self.kind == "stem":
            preferences.stem_name_presets = custom
            preferences.default_stem_name_preset_id = self.default_preset_id
        else:
            preferences.folder_name_presets = custom
            preferences.default_folder_name_preset_id = self.default_preset_id


class PreferencesDialog(QDialog):
    def __init__(self, preferences: Preferences, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumSize(680, 720)
        self.setStyleSheet(stylesheet_for_scale(1.0))
        self.preferences = normalize_naming_preferences(deepcopy(preferences))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(14)

        tabs = QTabWidget(self)
        tabs.setObjectName("preferencesTabs")

        general = QWidget()
        general.setObjectName("preferencesGeneral")
        gen_layout = QVBoxLayout(general)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(9)

        self.replace_mode = QComboBox()
        self.replace_mode.addItem("Replace existing files", "replace")
        self.replace_mode.addItem("Skip existing files", "keep")
        self.replace_mode.setCurrentIndex(0 if self.preferences.replace_mode == "replace" else 1)
        self.auto_open_folder = QCheckBox()
        self.auto_open_folder.setChecked(self.preferences.auto_open_folder)
        self.menubar_mode = QCheckBox()
        self.menubar_mode.setChecked(self.preferences.menubar_mode)
        self.launch_at_login = QCheckBox()
        self.launch_at_login.setChecked(self.preferences.launch_at_login)
        self.copy_summary = QCheckBox()
        self.copy_summary.setChecked(self.preferences.copy_summary_to_clipboard)
        self.sticky_position = QCheckBox()
        self.sticky_position.setChecked(self.preferences.sticky_panel_position)

        form.addRow("Default replace mode", self.replace_mode)
        form.addRow("Auto-open folder", self.auto_open_folder)
        form.addRow("Menubar mode", self.menubar_mode)
        form.addRow("Launch at login", self.launch_at_login)
        form.addRow("Copy summary to clipboard", self.copy_summary)
        form.addRow("Sticky panel position", self.sticky_position)
        gen_layout.addLayout(form)
        gen_layout.addStretch(1)
        tabs.addTab(general, "General")

        naming = QWidget()
        naming.setObjectName("preferencesNaming")
        nam_layout = QVBoxLayout(naming)
        nam_layout.setContentsMargins(8, 10, 8, 8)
        nam_layout.setSpacing(10)

        self.stem_editor = NamingPresetEditor(
            "stem",
            "Stem file names",
            all_naming_presets(self.preferences, "stem"),
            self.preferences.default_stem_name_preset_id,
        )
        self.folder_editor = NamingPresetEditor(
            "folder",
            "Output folder names",
            all_naming_presets(self.preferences, "folder"),
            self.preferences.default_folder_name_preset_id,
        )
        self.stem_name_format = self.stem_editor.format_input
        self.folder_name_format = self.folder_editor.format_input
        self.stem_editor.state_changed.connect(self._update_preview)
        self.folder_editor.state_changed.connect(self._update_preview)
        nam_layout.addWidget(self.stem_editor)
        nam_layout.addWidget(self.folder_editor)

        preview_title = QLabel("Live preview")
        preview_title.setObjectName("preferencesFieldTitle")
        nam_layout.addWidget(preview_title)
        self.preview_label = QLabel()
        self.preview_label.setObjectName("preferencesPreview")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(66)
        self.preview_label.setAccessibleName("Naming preview")
        nam_layout.addWidget(self.preview_label)
        nam_layout.addStretch(1)
        tabs.addTab(naming, "Naming")

        layout.addWidget(tabs)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setObjectName("primaryAction")
        self.buttons.button(QDialogButtonBox.Cancel).setObjectName("secondary")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._update_preview()

    def _update_preview(self) -> None:
        stem_out = render_name(
            self.stem_name_format.text().strip(),
            song="MySong",
            track="DRUMS",
            key="F# Minor",
            bpm="128",
            date="May 05 2026",
            index=1,
        )
        folder_out = render_name(
            self.folder_name_format.text().strip(),
            song="MySong",
            key="F# Minor",
            bpm="128",
            date="May 05 2026",
        )
        self.preview_label.setText(f"Stem file   {stem_out}\nFolder      {folder_out}")
        self.ok_button.setEnabled(self.stem_editor.can_accept and self.folder_editor.can_accept)

    def to_preferences(self) -> Preferences:
        updated = deepcopy(self.preferences)
        updated.replace_mode = self.replace_mode.currentData()
        updated.auto_open_folder = self.auto_open_folder.isChecked()
        updated.menubar_mode = self.menubar_mode.isChecked()
        updated.launch_at_login = self.launch_at_login.isChecked()
        updated.copy_summary_to_clipboard = self.copy_summary.isChecked()
        updated.sticky_panel_position = self.sticky_position.isChecked()
        self.stem_editor.apply_to_preferences(updated)
        self.folder_editor.apply_to_preferences(updated)

        stem_default = next(
            preset
            for preset in all_naming_presets(updated, "stem")
            if preset.preset_id == updated.default_stem_name_preset_id
        )
        folder_default = next(
            preset
            for preset in all_naming_presets(updated, "folder")
            if preset.preset_id == updated.default_folder_name_preset_id
        )
        updated.stem_name_format = stem_default.format_string
        updated.folder_name_format = folder_default.format_string
        return updated
