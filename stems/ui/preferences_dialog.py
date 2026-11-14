from __future__ import annotations

from copy import deepcopy
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout)
from ..naming import render_name
from ..preferences import Preferences, BUILTIN_STEM_NAMING_PRESETS, BUILTIN_FOLDER_NAMING_PRESETS


class PreferencesDialog(QDialog):
    preferences_changed = Signal(object)

    def __init__(self, preferences: Preferences, parent=None):
        super().__init__(parent)
        self.preferences = deepcopy(preferences)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(460)
        self.resize(520, 320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(20)
        form = QFormLayout()
        form.setSpacing(14)
        self.stem_choice = QComboBox()
        self.folder_choice = QComboBox()
        for combo, presets, current in (
            (self.stem_choice, BUILTIN_STEM_NAMING_PRESETS, preferences.stem_name_format),
            (self.folder_choice, BUILTIN_FOLDER_NAMING_PRESETS, preferences.folder_name_format),
        ):
            for preset in presets:
                combo.addItem(preset.name, preset.format_string)
            combo.setCurrentIndex(max(0, combo.findData(current)))
        form.addRow("File names", self.stem_choice)
        form.addRow("Folder names", self.folder_choice)
        layout.addLayout(form)
        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.preview_label)
        self.auto_open_folder = QCheckBox("Open the folder after export")
        self.auto_open_folder.setChecked(preferences.auto_open_folder)
        layout.addWidget(self.auto_open_folder)
        layout.addStretch()
        footer = QHBoxLayout()
        self.reset_button = QPushButton("Reset to defaults")
        self.saved_label = QLabel("Saved")
        self.close_button = QPushButton("Done")
        self.close_button.setDefault(True)
        footer.addWidget(self.reset_button)
        footer.addStretch()
        footer.addWidget(self.saved_label)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)
        self.close_button.clicked.connect(self.accept)
        self.reset_button.clicked.connect(self._reset_to_defaults)
        self.stem_choice.currentIndexChanged.connect(self._save_immediately)
        self.folder_choice.currentIndexChanged.connect(self._save_immediately)
        self.auto_open_folder.toggled.connect(self._save_immediately)
        self._update_preview()

    def _update_preview(self):
        values = dict(song="MySong", track="DRUMS", key="F# Minor", bpm="128", date="May 05 2026", index=1)
        stem = render_name(self.stem_choice.currentData(), **values)
        folder = render_name(self.folder_choice.currentData(), **values)
        self.preview_label.setText(f"Example file: {stem}\nExample folder: {folder}")

    def to_preferences(self):
        updated = deepcopy(self.preferences)
        updated.stem_name_format = self.stem_choice.currentData()
        updated.folder_name_format = self.folder_choice.currentData()
        updated.auto_open_folder = self.auto_open_folder.isChecked()
        return updated

    def _save_immediately(self):
        self.preferences = self.to_preferences()
        self._update_preview()
        self.saved_label.setProperty("saveState", "saved")
        self.saved_label.setText("Saved")
        self.preferences_changed.emit(deepcopy(self.preferences))

    def _reset_to_defaults(self):
        if QMessageBox.question(self, "Reset preferences?", "Reset naming and folder settings to their defaults?",
                                QMessageBox.Reset | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Reset:
            return
        self.stem_choice.setCurrentIndex(0)
        self.folder_choice.setCurrentIndex(0)
        self.auto_open_folder.setChecked(True)
        self._save_immediately()
