from __future__ import annotations

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QInputDialog,
    QLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..naming import TOKEN_PATTERN


class FlowLayout(QLayout):
    """Left-to-right layout that wraps onto new rows when out of width."""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)
        self.invalidate()

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        self.invalidate()
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(QRect(0, 0, max(width, 1), 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        size = size.expandedTo(QSize(420, 0))
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect, apply):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, row_height = area.x(), area.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > area.right() + 1 and row_height > 0:
                x = area.x()
                y += row_height + self._spacing
                row_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + m.top() + m.bottom()


class NameBuilder(QWidget):
    """Block-based editor for a name format such as ``{song}_{track}``.

    ``self.line`` is the single source of truth; blocks are a view of it.
    """

    BLOCK_HEIGHT = 28

    def __init__(self, kind: str, tokens, labels: dict, examples: dict, initial: str = "", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.tokens = tuple(tokens)
        self.labels = dict(labels)
        self.examples = dict(examples)

        self.line = QLineEdit(initial)
        self.line.setObjectName("exportInput")
        self.line.setFixedHeight(36)
        self.line.hide()

        self._strip = QWidget()
        self._flow = FlowLayout(self._strip, spacing=8)
        self._strip.setMinimumWidth(420)
        self._strip.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        self.add_button = QPushButton("+")
        self.add_button.setObjectName("nameBlockAdd")
        self.add_button.setFocusPolicy(Qt.NoFocus)
        self.add_button.setToolTip("Add a part")
        self.add_button.clicked.connect(self._show_add_menu)

        self.toggle_button = QPushButton("Edit as Text")
        self.toggle_button.setObjectName("nameBuilderTextToggle")
        self.toggle_button.setFocusPolicy(Qt.NoFocus)
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.clicked.connect(self._toggle_text)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._strip)

        self._buttons: list[QPushButton] = []
        self.line.textChanged.connect(self._rebuild)
        self._rebuild()

    # ---- model -------------------------------------------------------
    def blocks(self) -> list[tuple[str, str]]:
        text = self.line.text()
        result: list[tuple[str, str]] = []
        pos = 0
        for match in TOKEN_PATTERN.finditer(text):
            if match.start() > pos:
                result.append(("text", text[pos:match.start()]))
            result.append(("token", match.group(1)))
            pos = match.end()
        if pos < len(text):
            result.append(("text", text[pos:]))
        return result

    @staticmethod
    def _serialize(blocks) -> str:
        return "".join("{" + v + "}" if k == "token" else v for k, v in blocks)

    def _write(self, blocks) -> None:
        self.line.setText(self._serialize(blocks))

    def add_token(self, name: str) -> None:
        self._write(self.blocks() + [("token", name)])

    def add_text(self, text: str) -> None:
        if text:
            self._write(self.blocks() + [("text", text)])

    def remove_block(self, index: int) -> None:
        blocks = self.blocks()
        if 0 <= index < len(blocks):
            del blocks[index]
            self._write(blocks)

    def move_block(self, index: int, delta: int) -> None:
        blocks = self.blocks()
        target = index + delta
        if 0 <= index < len(blocks) and 0 <= target < len(blocks):
            blocks[index], blocks[target] = blocks[target], blocks[index]
            self._write(blocks)

    def change_text(self, index: int, text: str) -> None:
        blocks = self.blocks()
        if 0 <= index < len(blocks) and blocks[index][0] == "text":
            blocks[index] = ("text", text)
            self._write(blocks)

    # ---- view --------------------------------------------------------
    def _rebuild(self, *_args) -> None:
        for button in self._buttons:
            self._flow.removeWidget(button)
            button.hide()
            button.deleteLater()
        self._buttons = []
        self._flow.removeWidget(self.add_button)
        for index, (kind, value) in enumerate(self.blocks()):
            if kind == "token":
                label = self.labels.get(value, value.title())
                button = QPushButton(label)
                button.setObjectName("nameBlockToken")
                button.setToolTip(f"{label}: e.g. {self.examples.get(value, value)}. Click to move or remove")
            else:
                shown = "Space" if value.strip() == "" else value.replace(" - ", " \u2013 ").strip()
                if shown in ("-", "- ", " -"):
                    shown = "\u2013"
                elif shown.startswith("- "):
                    shown = "\u2013" + shown[1:]
                if shown.endswith(" -"):
                    shown = shown[:-1] + "\u2013"
                button = QPushButton(shown)
                button.setObjectName("nameBlockText")
                button.setToolTip("Your own text. Click to change, move or remove")
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(self.BLOCK_HEIGHT)
            button.clicked.connect(lambda _=False, i=index, b=button: self._show_block_menu(i, b))
            self._flow.addWidget(button)
            self._buttons.append(button)
        self._flow.addWidget(self.add_button)
        self.add_button.show()
        self._flow.invalidate()
        self._strip.updateGeometry()
        self.updateGeometry()

    def _show_block_menu(self, index: int, button: QPushButton) -> None:
        blocks = self.blocks()
        if not 0 <= index < len(blocks):
            return
        menu = QMenu(self)
        left = menu.addAction("Move Left")
        left.setEnabled(index > 0)
        right = menu.addAction("Move Right")
        right.setEnabled(index < len(blocks) - 1)
        change = None
        if blocks[index][0] == "text":
            change = menu.addAction("Change Text…")
        remove = menu.addAction("Remove")
        chosen = menu.exec(button.mapToGlobal(QPoint(0, button.height())))
        if chosen is None:
            return
        if chosen is left:
            self.move_block(index, -1)
        elif chosen is right:
            self.move_block(index, 1)
        elif chosen is remove:
            self.remove_block(index)
        elif change is not None and chosen is change:
            text, ok = QInputDialog.getText(self, "Change text", "Text:", text=blocks[index][1])
            if ok and text:
                self.change_text(index, text)

    def _show_add_menu(self) -> None:
        used = {v for k, v in self.blocks() if k == "token"}
        menu = QMenu(self)
        for token in self.tokens:
            action = menu.addAction(self.labels.get(token, token.title()))
            action.setData(("token", token))
            action.setEnabled(token not in used)
        menu.addSeparator()
        for title, text in (("Space", " "), ("Dash (\u2013)", " - "), ("Underscore (_)", "_")):
            menu.addAction(title).setData(("text", text))
        own = menu.addAction("Your Own Text…")
        chosen = menu.exec(self.add_button.mapToGlobal(QPoint(0, self.add_button.height())))
        if chosen is None:
            return
        if chosen is own:
            text, ok = QInputDialog.getText(self, "Your own text", "Text:")
            if ok:
                self.add_text(text)
            return
        data = chosen.data()
        if data and data[0] == "token":
            self.add_token(data[1])
        elif data:
            self.add_text(data[1])

    def _toggle_text(self) -> None:
        show = self.line.isHidden()
        self.line.setVisible(show)
        self.toggle_button.setText("Hide Text" if show else "Edit as Text")
