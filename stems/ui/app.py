from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

    from .main_window import MainWindow
    from .motion import effective_duration, fade_window_opacity
    from .theme import DURATION_REBUILD

    app = QApplication.instance() or QApplication(sys.argv)
    from ..permissions import request_accessibility_prompt

    request_accessibility_prompt()
    window = MainWindow()
    if effective_duration(DURATION_REBUILD) > 0:
        window.setWindowOpacity(0.0)
    window.show()
    fade_window_opacity(window, 1.0, DURATION_REBUILD)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
