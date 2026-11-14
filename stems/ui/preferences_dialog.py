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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from ..naming import FOLDER_NAME_TOKENS, STEM_NAME_TOKENS, render_name, validate_name_format
from ..preferences import Preferences, BUILTIN_STEM_NAMING_PRESETS, BUILTIN_FOLDER_NAMING_PRESETS
from .theme import stylesheet_for_scale


CHIP_LABELS = {"song": "Song", "track": "Track", "artist": "Artist", "key": "Key",
               "bpm": "BPM", "date": "Date", "index": "Number"}


class PreferencesDialog(QDialog):
    preferences_changed = Signal(object)

    def __init__(self, preferences: Preferences, parent=None):
        super().__init__(parent)
        self.preferences = deepcopy(preferences)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(500)
        self.resize(560, 560)
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
        subtitle_label = QLabel("Pick a style, or click the pieces to build your own name")
        subtitle_label.setObjectName("muted")
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        content_layout.addLayout(header_layout)

        self.stem_choice, self.stem_format, self.stem_error = None, None, None
        self.folder_choice, self.folder_format, self.folder_error = None, None, None
        sections = (
            ("File names", "stem", BUILTIN_STEM_NAMING_PRESETS, preferences.stem_name_format, STEM_NAME_TOKENS),
            ("Folder names", "folder", BUILTIN_FOLDER_NAMING_PRESETS, preferences.folder_name_format, FOLDER_NAME_TOKENS),
        )
        for title, kind, presets, current, tokens in sections:
            combo, line, error = self._build_naming_section(content_layout, title, kind, presets, current, tokens)
            setattr(self, f"{kind}_choice", combo)
            setattr(self, f"{kind}_format", line)
            setattr(self, f"{kind}_error", error)

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
        self.auto_open_folder.toggled.connect(self._save_immediately)
        self._update_preview()

    def _build_naming_section(self, parent_layout, title, kind, presets, current, tokens):
        label = QLabel(title)
        label.setObjectName("muted")

        combo = QComboBox()
        for preset in presets:
            combo.addItem(preset.name, preset.format_string)
        combo.addItem("Custom", None)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else combo.count() - 1)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setFixedHeight(36)

        line = QLineEdit(current)
        line.setObjectName("exportInput")
        line.setFixedHeight(36)

        error = QLabel("")
        error.setObjectName("muted")
        error.setStyleSheet("color: #ff6b6b;")
        error.hide()

        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        for token in tokens:
            chip = QPushButton(CHIP_LABELS.get(token, token.title()))
            chip.setObjectName("secondary")
            chip.setFocusPolicy(Qt.NoFocus)
            chip.setFixedHeight(28)
            chip.setToolTip(f"Add {{{token}}} to the name")
            chip.clicked.connect(lambda _=False, t=token, l=line: l.insert("{" + t + "}"))
            chips.addWidget(chip)
        chips.addStretch(1)

        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        box.addWidget(label)
        box.addWidget(combo)
        box.addWidget(line)
        box.addLayout(chips)
        box.addWidget(error)
        parent_layout.addLayout(box)

        combo.currentIndexChanged.connect(lambda _i, c=combo, l=line: self._on_preset_picked(c, l))
        line.textChanged.connect(lambda _t, c=combo, l=line, k=kind: self._on_format_edited(k, c, l))
        return combo, line, error

    def _on_preset_picked(self, combo, line):
        fmt = combo.currentData()
        if fmt is not None and line.text() != fmt:
            line.setText(fmt)  # triggers _on_format_edited

    def _on_format_edited(self, kind, combo, line):
        index = combo.findData(line.text())
        combo.blockSignals(True)
        combo.setCurrentIndex(index if index >= 0 else combo.count() - 1)
        combo.blockSignals(False)
        self._save_immediately()

    def _format_for(self, kind: str) -> str:
        line = getattr(self, f"{kind}_format")
        text = line.text().strip()
        if validate_name_format(text, kind) is None:
            return text
        return getattr(self.preferences, f"{kind}_name_format")

    def _update_preview(self):
        values = dict(song="MySong", track="DRUMS", artist="Artist Name", key="F# Minor",
                      bpm="128", date="May 05 2026", index=1)
        for kind in ("stem", "folder"):
            message = validate_name_format(getattr(self, f"{kind}_format").text(), kind)
            error = getattr(self, f"{kind}_error")
            error.setText(message or "")
            error.setVisible(bool(message))
        stem = render_name(self._format_for("stem"), **values)
        folder = render_name(self._format_for("folder"), **values)
        self.preview_label.setText(f"Example file:   {stem}\nExample folder: {folder}")

    def to_preferences(self):
        updated = deepcopy(self.preferences)
        updated.stem_name_format = self._format_for("stem")
        updated.folder_name_format = self._format_for("folder")
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
        self.stem_format.setText(BUILTIN_STEM_NAMING_PRESETS[0].format_string)
        self.folder_format.setText(BUILTIN_FOLDER_NAMING_PRESETS[0].format_string)
        self.auto_open_folder.setChecked(True)
        self._save_immediately()
