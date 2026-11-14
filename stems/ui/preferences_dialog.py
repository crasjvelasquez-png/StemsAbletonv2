from __future__ import annotations

from copy import deepcopy
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from ..naming import render_name
from ..preferences import Preferences, BUILTIN_STEM_NAMING_PRESETS, BUILTIN_FOLDER_NAMING_PRESETS
from .theme import stylesheet_for_scale


class PreferencesDialog(QDialog):
    preferences_changed = Signal(object)

    def __init__(self, preferences: Preferences, parent=None):
        super().__init__(parent)
        self.preferences = deepcopy(preferences)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(500)
        self.resize(540, 360)
        self.setStyleSheet(stylesheet_for_scale(1.0))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("preferencesContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(18)

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        title_label = QLabel("Preferences")
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Default naming format and post-export behavior")
        subtitle_label.setObjectName("muted")
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        content_layout.addLayout(header_layout)

        naming_grid = QGridLayout()
        naming_grid.setContentsMargins(0, 0, 0, 0)
        naming_grid.setHorizontalSpacing(12)
        naming_grid.setVerticalSpacing(0)
        naming_grid.setColumnStretch(0, 1)
        naming_grid.setColumnStretch(1, 1)

        self.stem_choice = QComboBox()
        self.folder_choice = QComboBox()
        for combo, presets, current in (
            (self.stem_choice, BUILTIN_STEM_NAMING_PRESETS, preferences.stem_name_format),
            (self.folder_choice, BUILTIN_FOLDER_NAMING_PRESETS, preferences.folder_name_format),
        ):
            for preset in presets:
                combo.addItem(preset.name, preset.format_string)
            combo.setCurrentIndex(max(0, combo.findData(current)))
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            combo.setFixedHeight(36)

        for column, (label_text, combo) in enumerate(
            (("File names", self.stem_choice), ("Folder names", self.folder_choice))
        ):
            pair_layout = QVBoxLayout()
            pair_layout.setContentsMargins(0, 0, 0, 0)
            pair_layout.setSpacing(6)
            field_label = QLabel(label_text)
            field_label.setObjectName("muted")
            pair_layout.addWidget(field_label)
            pair_layout.addWidget(combo)
            naming_grid.addLayout(pair_layout, 0, column)

        content_layout.addLayout(naming_grid)

        preview_card = QWidget()
        preview_card.setObjectName("preferencesPreviewCard")
        preview_card.setAttribute(Qt.WA_StyledBackground, True)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 12, 14, 12)
        preview_layout.setSpacing(6)

        preview_header = QLabel("Preview")
        preview_header.setObjectName("muted")
        self.preview_label = QLabel()
        self.preview_label.setObjectName("preferencesPreviewText")
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        preview_layout.addWidget(preview_header)
        preview_layout.addWidget(self.preview_label)
        content_layout.addWidget(preview_card)

        self.auto_open_folder = QCheckBox("Open the folder after export")
        self.auto_open_folder.setChecked(preferences.auto_open_folder)
        content_layout.addWidget(self.auto_open_folder)
        content_layout.addStretch(1)

        root_layout.addWidget(content, 1)

        footer = QWidget()
        footer.setObjectName("footerDock")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(12)

        self.reset_button = QPushButton("Reset to defaults")
        self.reset_button.setObjectName("secondary")
        self.reset_button.setProperty("actionBarButton", True)
        self.reset_button.setFixedHeight(36)

        self.saved_label = QLabel("Saved")
        self.saved_label.setObjectName("preferencesSavedLabel")
        self.saved_label.setProperty("saveState", "saved")

        self.close_button = QPushButton("Done")
        self.close_button.setObjectName("primaryAction")
        self.close_button.setProperty("actionBarButton", True)
        self.close_button.setDefault(True)
        self.close_button.setFixedHeight(36)
        self.close_button.setMinimumWidth(96)

        footer_layout.addWidget(self.reset_button)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.saved_label)
        footer_layout.addWidget(self.close_button)
        root_layout.addWidget(footer)

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
        self.preview_label.setText(f"Example file:   {stem}\nExample folder: {folder}")

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
