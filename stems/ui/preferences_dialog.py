from __future__ import annotations

import re

try:
    from PySide6.QtCore import QMimeData, QPoint, Qt
    from PySide6.QtGui import QDrag
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSizePolicy,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

from ..naming import render_name
from ..preferences import Preferences
from .theme import DESIGN_TOKENS, stylesheet_for_scale


NAMING_TOKENS = ("song", "track", "bpm", "key", "date", "index")
COMMON_TEXT_PIECES = ("_", " - ", " ", " BPM", ".wav", "Stems")
TOKEN_MIME = "application/x-stems-naming-piece"
TOKEN_LABELS = {
    "song": "Song name",
    "track": "Stem name",
    "bpm": "Tempo",
    "key": "Key",
    "date": "Date",
    "index": "Number",
}
TEXT_LABELS = {
    "_": "_",
    " - ": "-",
    " ": " ",
    " BPM": "BPM",
    ".wav": ".wav",
    "Stems": "Stems",
}


def piece_label(kind: str, value: str) -> str:
    if kind == "token":
        return TOKEN_LABELS.get(value, value.title())
    return TEXT_LABELS.get(value, value)


class NamingPieceButton(QPushButton):
    def __init__(
        self,
        text: str,
        *,
        kind: str,
        value: str,
        scale: float,
        editor: "NamingFormatEditor | None" = None,
        index: int | None = None,
    ) -> None:
        super().__init__(text)
        self.kind = kind
        self.value = value
        self.editor = editor
        self.index = index
        self._scale = scale
        self._drag_start: QPoint | None = None
        self.setCursor(Qt.OpenHandCursor)
        self.setMinimumHeight(max(24, round(28 * scale)))
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setToolTip("Click to add. Drag to move. Double-click a placed item to remove it.")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if not (event.buttons() & Qt.LeftButton) or self._drag_start is None:
            super().mouseMoveEvent(event)
            return
        distance = (event.position().toPoint() - self._drag_start).manhattanLength()
        if distance < 6:
            super().mouseMoveEvent(event)
            return

        source = "palette"
        if self.editor is not None and self.index is not None:
            source = f"editor:{id(self.editor)}:{self.index}"
        data = QMimeData()
        data.setData(TOKEN_MIME, f"{source}|{self.kind}|{self.value}".encode())
        drag = QDrag(self)
        drag.setMimeData(data)
        drag.exec(Qt.MoveAction | Qt.CopyAction)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if self.editor is not None and self.index is not None:
            self.editor.remove_piece(self.index)
            return
        super().mouseDoubleClickEvent(event)


class NamingDropZone(QFrame):
    def __init__(self, editor: "NamingFormatEditor") -> None:
        super().__init__()
        self.editor = editor
        self.setAcceptDrops(True)
        self.setObjectName("namingDropZone")
        self.setMinimumHeight(editor._s(46))

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasFormat(TOKEN_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasFormat(TOKEN_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        raw = bytes(event.mimeData().data(TOKEN_MIME)).decode()
        source, kind, value = raw.split("|", 2)
        self.editor.drop_piece(kind, value, self.editor.drop_index_for_x(event.position().toPoint().x()), source)
        event.acceptProposedAction()


class NamingFormatEditor(QWidget):
    def __init__(self, format_string: str, *, scale: float, parent=None) -> None:
        super().__init__(parent)
        self._scale = scale
        self._pieces: list[tuple[str, str]] = []
        self._on_changed = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._s(7))

        self.drop_zone = NamingDropZone(self)
        self.drop_zone.setStyleSheet(
            f"QFrame#namingDropZone {{ background: {DESIGN_TOKENS['field']}; "
            f"border: 1px solid {DESIGN_TOKENS['border']}; border-radius: 8px; }}"
        )
        self.piece_layout = QHBoxLayout(self.drop_zone)
        self.piece_layout.setContentsMargins(self._s(10), self._s(8), self._s(10), self._s(8))
        self.piece_layout.setSpacing(self._s(6))
        self.placeholder = QLabel("Build the name here")
        self.placeholder.setObjectName("muted")
        self.piece_layout.addWidget(self.placeholder)
        self.piece_layout.addStretch(1)
        layout.addWidget(self.drop_zone)

        session_label = QLabel("Song details")
        session_label.setObjectName("muted")
        layout.addWidget(session_label)

        session_parts = QWidget()
        session_layout = QHBoxLayout(session_parts)
        session_layout.setContentsMargins(0, 0, 0, 0)
        session_layout.setSpacing(self._s(6))
        for token in NAMING_TOKENS:
            chip = self._make_palette_chip(piece_label("token", token), "token", token)
            chip.clicked.connect(lambda _checked=False, t=token: self.add_piece("token", t))
            session_layout.addWidget(chip)
        session_layout.addStretch(1)
        layout.addWidget(session_parts)

        separator_label = QLabel("Spacing and words")
        separator_label.setObjectName("muted")
        layout.addWidget(separator_label)

        text_parts = QWidget()
        text_layout = QHBoxLayout(text_parts)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(self._s(6))
        for text in COMMON_TEXT_PIECES:
            chip = self._make_palette_chip(piece_label("text", text), "text", text)
            chip.clicked.connect(lambda _checked=False, value=text: self.add_piece("text", value))
            text_layout.addWidget(chip)
        text_layout.addStretch(1)
        layout.addWidget(text_parts)

        custom_row = QWidget()
        custom_layout = QHBoxLayout(custom_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(self._s(6))
        self.custom_text = QLineEdit()
        self.custom_text.setPlaceholderText("Type words to add")
        self.custom_text.setMinimumHeight(self._s(28))
        self.custom_text.returnPressed.connect(self._add_custom_text)
        add_text = QPushButton("Add")
        add_text.clicked.connect(self._add_custom_text)
        custom_layout.addWidget(self.custom_text, 1)
        custom_layout.addWidget(add_text)
        layout.addWidget(custom_row)

        self.set_format(format_string)

    def _s(self, value: int) -> int:
        return max(1, round(value * self._scale))

    def _make_palette_chip(self, label: str, kind: str, value: str) -> NamingPieceButton:
        chip = NamingPieceButton(label, kind=kind, value=value, scale=self._scale)
        chip.setStyleSheet(self._chip_style(palette=True))
        return chip

    def _make_piece_chip(self, label: str, kind: str, value: str, index: int) -> NamingPieceButton:
        chip = NamingPieceButton(
            label,
            kind=kind,
            value=value,
            scale=self._scale,
            editor=self,
            index=index,
        )
        chip.setStyleSheet(self._chip_style(palette=False))
        return chip

    def _chip_style(self, *, palette: bool) -> str:
        bg = "rgba(124, 196, 240, 0.16)" if palette else "rgba(238, 244, 255, 0.10)"
        border = "rgba(124, 196, 240, 0.36)" if palette else DESIGN_TOKENS["border_strong"]
        return (
            f"QPushButton {{ background: {bg}; color: {DESIGN_TOKENS['text_strong']}; "
            f"border: 1px solid {border}; border-radius: 8px; padding: 4px 9px; "
            "font-weight: 600; }}"
            f"QPushButton:hover {{ background: {DESIGN_TOKENS['field_hover']}; }}"
        )

    def set_on_changed(self, callback) -> None:
        self._on_changed = callback

    def set_format(self, format_string: str) -> None:
        pieces: list[tuple[str, str]] = []
        pattern = re.compile(r"\{(" + "|".join(NAMING_TOKENS) + r")\}")
        position = 0
        for match in pattern.finditer(format_string):
            if match.start() > position:
                pieces.append(("text", format_string[position : match.start()]))
            pieces.append(("token", match.group(1)))
            position = match.end()
        if position < len(format_string):
            pieces.append(("text", format_string[position:]))
        self._pieces = [(kind, value) for kind, value in pieces if value]
        self._rebuild()

    def format_text(self) -> str:
        values: list[str] = []
        for kind, value in self._pieces:
            values.append("{" + value + "}" if kind == "token" else value)
        return "".join(values).strip()

    def add_piece(self, kind: str, value: str) -> None:
        self._pieces.append((kind, value))
        self._rebuild()
        self._emit_changed()

    def drop_piece(self, kind: str, value: str, index: int, source: str) -> None:
        if source.startswith(f"editor:{id(self)}:"):
            old_index = int(source.rsplit(":", 1)[1])
            if old_index < len(self._pieces):
                self._pieces.pop(old_index)
                if old_index < index:
                    index -= 1
        self._pieces.insert(max(0, min(index, len(self._pieces))), (kind, value))
        self._rebuild()
        self._emit_changed()

    def remove_piece(self, index: int) -> None:
        if 0 <= index < len(self._pieces):
            self._pieces.pop(index)
            self._rebuild()
            self._emit_changed()

    def drop_index_for_x(self, x: int) -> int:
        index = 0
        for i in range(self.piece_layout.count()):
            item = self.piece_layout.itemAt(i)
            widget = item.widget()
            if not isinstance(widget, NamingPieceButton):
                continue
            center_x = widget.x() + widget.width() / 2
            if x < center_x:
                return index
            index += 1
        return len(self._pieces)

    def _add_custom_text(self) -> None:
        value = self.custom_text.text()
        if not value:
            return
        self.add_piece("text", value)
        self.custom_text.clear()

    def _rebuild(self) -> None:
        while self.piece_layout.count():
            item = self.piece_layout.takeAt(0)
            widget = item.widget()
            if widget is self.placeholder:
                widget.setParent(None)
            elif widget is not None:
                widget.deleteLater()
        if not self._pieces:
            self.piece_layout.addWidget(self.placeholder)
        for index, (kind, value) in enumerate(self._pieces):
            self.piece_layout.addWidget(self._make_piece_chip(piece_label(kind, value), kind, value, index))
        self.piece_layout.addStretch(1)

    def _emit_changed(self) -> None:
        if self._on_changed is not None:
            self._on_changed()


class PreferencesDialog(QDialog):
    def __init__(self, preferences: Preferences, parent=None, *, scale: float = 1.0) -> None:
        super().__init__(parent)
        self._scale = scale
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(max(280, self._s(440)))
        self.setStyleSheet(stylesheet_for_scale(scale))
        self.preferences = preferences

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._s(16), self._s(16), self._s(16), self._s(14))
        layout.setSpacing(self._s(14))

        tabs = QTabWidget(self)

        # ---- General tab ----
        general = QWidget()
        gen_layout = QVBoxLayout(general)
        form = QFormLayout()
        form.setHorizontalSpacing(self._s(14))
        form.setVerticalSpacing(self._s(9))

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
        nam_layout.setContentsMargins(0, self._s(8), 0, 0)
        nam_layout.setSpacing(self._s(10))

        stem_preview_title = QLabel("Stem file preview")
        stem_preview_title.setStyleSheet("font-weight: bold;")
        self.stem_preview_label = QLabel()
        self.stem_preview_label.setStyleSheet(self._preview_style())
        self.stem_preview_label.setWordWrap(True)
        self.stem_preview_label.setMinimumHeight(self._s(42))

        stem_label = QLabel("Stem file name")
        stem_label.setStyleSheet("font-weight: bold;")
        self.stem_name_format = NamingFormatEditor(
            preferences.stem_name_format,
            scale=scale,
            parent=self,
        )
        self.stem_name_format.set_on_changed(self._update_preview)

        folder_preview_title = QLabel("Output folder preview")
        folder_preview_title.setStyleSheet("font-weight: bold;")
        self.folder_preview_label = QLabel()
        self.folder_preview_label.setStyleSheet(self._preview_style())
        self.folder_preview_label.setWordWrap(True)
        self.folder_preview_label.setMinimumHeight(self._s(42))

        folder_label = QLabel("Output folder name")
        folder_label.setStyleSheet("font-weight: bold;")
        self.folder_name_format = NamingFormatEditor(
            preferences.folder_name_format,
            scale=scale,
            parent=self,
        )
        self.folder_name_format.set_on_changed(self._update_preview)

        nam_layout.addWidget(stem_preview_title)
        nam_layout.addWidget(self.stem_preview_label)
        nam_layout.addWidget(stem_label)
        nam_layout.addWidget(self.stem_name_format)
        nam_layout.addSpacing(self._s(10))
        nam_layout.addWidget(folder_preview_title)
        nam_layout.addWidget(self.folder_preview_label)
        nam_layout.addWidget(folder_label)
        nam_layout.addWidget(self.folder_name_format)
        nam_layout.addStretch(1)
        tabs.addTab(naming, "Naming")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _s(self, value: int) -> int:
        return max(1, round(value * self._scale))

    def _preview_style(self) -> str:
        return (
            f"background: {DESIGN_TOKENS['field']}; color: {DESIGN_TOKENS['text']}; "
            "padding: 10px; border-radius: 4px; font-family: monospace; "
            "font-size: 14px;"
        )

    def _update_preview(self) -> None:
        stem_fmt = self.stem_name_format.format_text()
        folder_fmt = self.folder_name_format.format_text()
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
        self.stem_preview_label.setText(stem_out)
        self.folder_preview_label.setText(folder_out)

    def to_preferences(self) -> Preferences:
        updated = Preferences(**self.preferences.__dict__)
        updated.replace_mode = self.replace_mode.currentData()
        updated.auto_open_folder = self.auto_open_folder.isChecked()
        updated.menubar_mode = self.menubar_mode.isChecked()
        updated.launch_at_login = self.launch_at_login.isChecked()
        updated.copy_summary_to_clipboard = self.copy_summary.isChecked()
        updated.sticky_panel_position = self.sticky_position.isChecked()
        updated.stem_name_format = self.stem_name_format.format_text()
        updated.folder_name_format = self.folder_name_format.format_text()
        return updated
