"""Finder-style folder trail: [folder icon] Name  ›  [folder icon] Name."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFileIconProvider, QLabel, QLayout, QSizePolicy, QWidget

ICON_POINTS = 16


def friendly_parts(path: str | Path) -> list[str]:
    """Folder names a person cares about: no leading slash, no 'Volumes'."""
    p = Path(path)
    parts = [x for x in p.parts if x != "/"]
    home = [x for x in Path.home().parts if x != "/"]
    if home and parts[: len(home)] == home:
        parts = ["Home"] + parts[len(home) :]
    elif parts and parts[0] == "Volumes":
        parts = parts[1:]
    return parts or [str(path)]


class _FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, h_spacing: int = 4, v_spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._h = h_spacing
        self._v = v_spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _layout(self, rect: QRect, *, apply: bool) -> int:
        x, y, row_h = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and row_h > 0:
                x = rect.x()
                y += row_h + self._v
                row_h = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._h
            row_h = max(row_h, hint.height())
        return y + row_h - rect.y()


class PathTrail(QWidget):
    """Read-only folder trail. Click anywhere to open the folder."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("pathTrail")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setCursor(Qt.PointingHandCursor)
        self._flow = _FlowLayout(self)
        self._plain = "-"
        self._icon = None

    def text(self) -> str:
        return self._plain

    def setText(self, text: str) -> None:
        self._clear()
        self._plain = text
        label = QLabel(text)
        label.setObjectName("pathTrailEmpty")
        self._flow.addWidget(label)

    def setPath(self, path: str | Path, *, existing: bool = False) -> None:
        self._clear()
        parts = friendly_parts(path)
        self._plain = " › ".join(parts) + (" · existing folder" if existing else "")
        for i, name in enumerate(parts):
            if i:
                chevron = QLabel("\u25B6\uFE0E")
                chevron.setObjectName("pathTrailChevron")
                chevron.setAlignment(Qt.AlignCenter)
                chevron.setFixedHeight(ICON_POINTS)
                self._flow.addWidget(chevron)
            self._flow.addWidget(self._crumb(name, last=i == len(parts) - 1))
        if existing:
            note = QLabel("Existing folder")
            note.setObjectName("pathTrailNote")
            self._flow.addWidget(note)

    def _crumb(self, name: str, *, last: bool) -> QWidget:
        box = QWidget()
        box.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        from PySide6.QtWidgets import QHBoxLayout

        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        icon = QLabel()
        icon.setPixmap(self._folder_pixmap())
        icon.setFixedSize(ICON_POINTS, ICON_POINTS)
        text = QLabel(name)
        text.setObjectName("pathTrailLast" if last else "pathTrailName")
        lay.addWidget(icon)
        lay.addWidget(text)
        return box

    def _folder_pixmap(self):
        if self._icon is None:
            pm = QFileIconProvider().icon(QFileIconProvider.IconType.Folder).pixmap(
                QSize(ICON_POINTS * 2, ICON_POINTS * 2)
            )
            pm.setDevicePixelRatio(2)
            self._icon = pm
        return self._icon

    def _clear(self) -> None:
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
