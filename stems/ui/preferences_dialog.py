from __future__ import annotations

from copy import deepcopy
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
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
from .name_builder import NameBuilder
from .theme import stylesheet_for_scale


REPLACE_CHOICES = (
    ("Ask each time", "ask"),
    ("Replace them", "replace"),
    ("Skip them", "keep"),
    ("Keep both", "keep_both"),
)

PREVIEW_VALUES = dict(song="MySong", track="DRUMS", artist="Artist Name", key="F# Minor",
                      bpm="128", date="May 05 2026", index="01")

CHIP_LABELS = {"song": "Song", "track": "Track", "artist": "Artist", "key": "Key",
               "bpm": "BPM", "date": "Date", "index": "Number"}


class PreferencesDialog(QDialog):
    preferences_changed = Signal(object)

    def __init__(self, preferences: Preferences, parent=None):
        super().__init__(parent)
        self.preferences = deepcopy(preferences)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(500)
        self.resize(560, 600)
        self.setStyleSheet(stylesheet_for_scale(1.0))

        self.setObjectName("preferencesDialog")
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("preferencesContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(20)

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        title_label = QLabel("Preferences")
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Choose how your stems are named.")
        subtitle_label.setObjectName("prefsSubtitle")
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        content_layout.addLayout(header_layout)

        self.stem_choice, self.stem_format, self.stem_error = None, None, None
        self.folder_choice, self.folder_format, self.folder_error = None, None, None
        sections = (
            ("File Names", "stem", BUILTIN_STEM_NAMING_PRESETS, preferences.stem_name_format, STEM_NAME_TOKENS),
            ("Folder Names", "folder", BUILTIN_FOLDER_NAMING_PRESETS, preferences.folder_name_format, FOLDER_NAME_TOKENS),
        )
        for title, kind, presets, current, tokens in sections:
            combo, line, error = self._build_naming_section(content_layout, title, kind, presets, current, tokens)
            setattr(self, f"{kind}_choice", combo)
            setattr(self, f"{kind}_format", line)
            setattr(self, f"{kind}_error", error)

        self.preview_label = QLabel()
        self.preview_label.hide()

        self.replace_choice = QComboBox()
        for text, value in REPLACE_CHOICES:
            self.replace_choice.addItem(text, value)
        self.replace_choice.setCurrentIndex(max(0, self.replace_choice.findData(preferences.replace_mode)))
        self._style_combo(self.replace_choice)

        self.auto_open_folder = QCheckBox()
        self.auto_open_folder.setChecked(preferences.auto_open_folder)

        card, card_layout = self._group(content_layout, "After Export")
        card_layout.addLayout(self._row("When stems already exist", self.replace_choice))
        card_layout.addWidget(self._separator())
        card_layout.addLayout(self._row("Open the folder after export", self.auto_open_folder))
        content_layout.addStretch(1)

        root_layout.addWidget(content, 1)

        footer = QWidget()
        footer.setObjectName("footerDock")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(12)

        self.reset_button = QPushButton("Reset to Defaults")
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
        self.replace_choice.currentIndexChanged.connect(self._save_immediately)
        self._update_preview()

    @staticmethod
    def _style_combo(combo):
        combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        combo.setFixedSize(200, 28)

    @staticmethod
    def _separator():
        sep = QFrame()
        sep.setObjectName("prefsRowSeparator")
        sep.setFrameShape(QFrame.NoFrame)
        sep.setFixedHeight(1)
        return sep

    @staticmethod
    def _row(text, control):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        label = QLabel(text)
        label.setObjectName("prefsRowLabel")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
        return row

    @staticmethod
    def _group(parent_layout, title):
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName("prefsGroupTitle")
        heading.setContentsMargins(2, 0, 0, 0)
        card = QWidget()
        card.setObjectName("prefsGroup")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)
        box.addWidget(heading)
        box.addWidget(card)
        parent_layout.addLayout(box)
        return card, card_layout

    def _build_naming_section(self, parent_layout, title, kind, presets, current, tokens):
        combo = QComboBox()
        for preset in presets:
            combo.addItem(preset.name, preset.format_string)
        combo.addItem("My Own", None)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else combo.count() - 1)
        self._style_combo(combo)

        builder = NameBuilder(kind, tokens, CHIP_LABELS, PREVIEW_VALUES, current)
        line = builder.line
        setattr(self, f"{kind}_builder", builder)

        caption = QLabel("Example")
        caption.setObjectName("nameLooksLikeCaption")
        looks_like = QLabel("")
        looks_like.setObjectName("nameLooksLike")
        looks_like.setWordWrap(True)
        looks_like.setMinimumWidth(300)
        setattr(self, f"{kind}_looks_like", looks_like)

        error = QLabel("")
        error.setObjectName("prefsError")
        error.setWordWrap(True)
        error.setMinimumWidth(300)
        error.hide()

        _card, card_layout = self._group(parent_layout, title)
        card_layout.addLayout(self._row("Style", combo))
        card_layout.addWidget(self._separator())
        card_layout.addWidget(builder)

        example = QVBoxLayout()
        example.setContentsMargins(0, 0, 0, 0)
        example.setSpacing(2)
        example.addWidget(caption)
        example.addWidget(looks_like)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(12)
        footer.addLayout(example, 1)
        footer.addWidget(builder.toggle_button, 0, Qt.AlignRight | Qt.AlignBottom)
        card_layout.addLayout(footer)
        card_layout.addWidget(line)
        card_layout.addWidget(error)

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
        values = dict(PREVIEW_VALUES, index=1)
        for kind in ("stem", "folder"):
            message = validate_name_format(getattr(self, f"{kind}_format").text(), kind)
            error = getattr(self, f"{kind}_error")
            error.setText(message or "")
            error.setVisible(bool(message))
        stem = render_name(self._format_for("stem"), **values)
        folder = render_name(self._format_for("folder"), **values)
        self.stem_looks_like.setText(stem)
        self.folder_looks_like.setText(folder)
        self.preview_label.setText(f"Example file:   {stem} (file type set in Ableton)\nExample folder: {folder}")

    def to_preferences(self):
        updated = deepcopy(self.preferences)
        updated.stem_name_format = self._format_for("stem")
        updated.folder_name_format = self._format_for("folder")
        updated.auto_open_folder = self.auto_open_folder.isChecked()
        updated.replace_mode = self.replace_choice.currentData()
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
        self.replace_choice.setCurrentIndex(0)
        self._save_immediately()
