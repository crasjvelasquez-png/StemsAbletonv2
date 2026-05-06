from __future__ import annotations

try:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLineEdit,
        QVBoxLayout,
    )
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

from ..preferences import Preferences
from .theme import DARK_STYLESHEET


class PreferencesDialog(QDialog):
    def __init__(self, preferences: Preferences, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(420)
        self.setStyleSheet(DARK_STYLESHEET)
        self.preferences = preferences

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(18)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.default_key = QLineEdit(preferences.default_key)
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

        form.addRow("Default key", self.default_key)
        form.addRow("Default replace mode", self.replace_mode)
        form.addRow("Auto-open folder", self.auto_open_folder)
        form.addRow("Menubar mode", self.menubar_mode)
        form.addRow("Launch at login", self.launch_at_login)
        form.addRow("Copy summary to clipboard", self.copy_summary)
        form.addRow("Sticky panel position", self.sticky_position)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def to_preferences(self) -> Preferences:
        updated = Preferences(**self.preferences.__dict__)
        updated.default_key = self.default_key.text().strip()
        updated.replace_mode = self.replace_mode.currentData()
        updated.auto_open_folder = self.auto_open_folder.isChecked()
        updated.menubar_mode = self.menubar_mode.isChecked()
        updated.launch_at_login = self.launch_at_login.isChecked()
        updated.copy_summary_to_clipboard = self.copy_summary.isChecked()
        updated.sticky_panel_position = self.sticky_position.isChecked()
        return updated
