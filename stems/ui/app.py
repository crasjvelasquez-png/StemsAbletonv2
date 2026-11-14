from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

    from .main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    from ..permissions import request_accessibility_prompt

    request_accessibility_prompt()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
