from __future__ import annotations

try:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

from ..naming import render_name, stem_file_name, stems_folder_name
from ..preferences import Preferences
from .theme import stylesheet_for_scale


TOKEN_HELP = (
    "Available tokens: {song}, {track}, {bpm}, {key}, {date}, {index}"
)


class PreferencesDialog(QDialog):
    def __init__(self, preferences: Preferences, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(440)
        self.setStyleSheet(stylesheet_for_scale(1.0))
        self.preferences = preferences

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(14)

        tabs = QTabWidget(self)

        # ---- General tab ----
        general = QWidget()
        gen_layout = QVBoxLayout(general)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(9)

        self.replace_mode = QComboBox()
        self.replace_mode.addItem("Replace existing files", "replace")
        self.replace_mode.addItem("Skip existing files", "keep")
        self.replace_mode.setCurrentIndex(0 if preferences.replace_mode == "replace" else 1)
        self.auto_open_folder = QCheckBox()
        self.auto_open_folder.setChecked(preferences.auto_open_folder)
        self.menubar_mode = QCheckBox()
        self.menubar_mode.setChecked(preferences.menubar_mode)
        self.launch_at_login = QCheckBox()
        self.launch_at_login.setChecked(preferences.launch_at_login)
        self.copy_summary = QCheckBox()
        self.copy_summary.setChecked(preferences.copy_summary_to_clipboard)
        self.sticky_position = QCheckBox()
        self.sticky_position.setChecked(preferences.sticky_panel_position)

        form.addRow("Default replace mode", self.replace_mode)
        form.addRow("Auto-open folder", self.auto_open_folder)
        form.addRow("Menubar mode", self.menubar_mode)
        form.addRow("Launch at login", self.launch_at_login)
        form.addRow("Copy summary to clipboard", self.copy_summary)
        form.addRow("Sticky panel position", self.sticky_position)
        gen_layout.addLayout(form)
        gen_layout.addStretch(1)
        tabs.addTab(general, "General")

        # ---- Naming tab ----
        naming = QWidget()
        nam_layout = QVBoxLayout(naming)
        nam_layout.setContentsMargins(0, 8, 0, 0)
        nam_layout.setSpacing(10)

        stem_label = QLabel("Stem file name format")
        stem_label.setStyleSheet("font-weight: bold;")
        self.stem_name_format = QLineEdit(preferences.stem_name_format)
        self.stem_name_format.setMinimumHeight(30)
        self.stem_name_format.textChanged.connect(self._update_preview)

        stem_token_hint = QLabel(TOKEN_HELP)
        stem_token_hint.setStyleSheet("color: #888; font-size: 11px;")

        folder_label = QLabel("Output folder name format")
        folder_label.setStyleSheet("font-weight: bold;")
        self.folder_name_format = QLineEdit(preferences.folder_name_format)
        self.folder_name_format.setMinimumHeight(30)
        self.folder_name_format.textChanged.connect(self._update_preview)

        folder_token_hint = QLabel(TOKEN_HELP)
        folder_token_hint.setStyleSheet("color: #888; font-size: 11px;")

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet(
            "background: #1e1e1e; color: #ccc; padding: 10px; border-radius: 4px;"
            "font-family: monospace; font-size: 12px;"
        )
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(60)

        nam_layout.addWidget(stem_label)
        nam_layout.addWidget(self.stem_name_format)
        nam_layout.addWidget(stem_token_hint)
        nam_layout.addSpacing(6)
        nam_layout.addWidget(folder_label)
        nam_layout.addWidget(self.folder_name_format)
        nam_layout.addWidget(folder_token_hint)
        nam_layout.addSpacing(8)
        nam_layout.addWidget(QLabel("Preview (example values)"))
        nam_layout.addWidget(self.preview_label)
        nam_layout.addStretch(1)
        tabs.addTab(naming, "Naming")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _update_preview(self) -> None:
        stem_fmt = self.stem_name_format.text().strip()
        folder_fmt = self.folder_name_format.text().strip()
        sample_song = "MySong"
        sample_track = "DRUMS"
        sample_key = "F# Minor"
        sample_bpm = 128

        stem_out = render_name(
            stem_fmt,
            song=sample_song,
            track=sample_track,
            key=sample_key,
            bpm=str(sample_bpm),
            index=1,
        )
        folder_out = render_name(
            folder_fmt,
            song=sample_song,
            key=sample_key,
            bpm=str(sample_bpm),
            date="May 05 2026",
        )
        self.preview_label.setText(f"Stem file:  {stem_out}\nFolder:     {folder_out}")

    def to_preferences(self) -> Preferences:
        updated = Preferences(**self.preferences.__dict__)
        updated.replace_mode = self.replace_mode.currentData()
        updated.auto_open_folder = self.auto_open_folder.isChecked()
        updated.menubar_mode = self.menubar_mode.isChecked()
        updated.launch_at_login = self.launch_at_login.isChecked()
        updated.copy_summary_to_clipboard = self.copy_summary.isChecked()
        updated.sticky_panel_position = self.sticky_position.isChecked()
        updated.stem_name_format = self.stem_name_format.text().strip()
        updated.folder_name_format = self.folder_name_format.text().strip()
        return updated
