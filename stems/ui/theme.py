from __future__ import annotations

import re

DESIGN_TOKENS = {
    "bg_top": "#22252e",
    "bg_mid": "#1e2129",
    "bg_bottom": "#1a1d24",
    "panel": "rgba(35, 38, 50, 0.48)",
    "panel_soft": "rgba(30, 33, 44, 0.40)",
    "panel_hover": "rgba(50, 54, 68, 0.38)",
    "field": "rgba(24, 27, 36, 0.58)",
    "field_hover": "rgba(32, 36, 48, 0.68)",
    "border": "rgba(220, 230, 255, 0.10)",
    "border_strong": "rgba(220, 230, 255, 0.18)",
    "separator": "rgba(220, 230, 255, 0.08)",
    "text": "rgba(244, 248, 252, 0.90)",
    "text_strong": "rgba(250, 252, 255, 0.96)",
    "text_muted": "rgba(221, 231, 242, 0.58)",
    "text_faint": "rgba(221, 231, 242, 0.38)",
    "accent": "#7cc4f0",
    "accent_hover": "#8dd0f5",
    "accent_pressed": "#6ab8e8",
    "success": "#72e39d",
    "warning": "#f5d56e",
    "danger": "#e85d5d",
    "accent_text": "#071522",
    "menu": "#1e2129",
    "radius_panel": "10px",
    "radius_control": "8px",
    "radius_pill": "11px",
    "font_family": '".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue"',
}


DARK_STYLESHEET = f"""
/* Core windows */
QMainWindow,
QDialog {{
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 {DESIGN_TOKENS["bg_top"]},
        stop: 0.52 {DESIGN_TOKENS["bg_mid"]},
        stop: 1 {DESIGN_TOKENS["bg_bottom"]}
    );
    font-family: {DESIGN_TOKENS["font_family"]};
    font-size: 13px;
}}

/* Central widget reference */
QWidget#centralWidget {{
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 {DESIGN_TOKENS["bg_top"]},
        stop: 0.52 {DESIGN_TOKENS["bg_mid"]},
        stop: 1 {DESIGN_TOKENS["bg_bottom"]}
    );
}}

QScrollArea#mainScrollArea,
QScrollArea#mainScrollArea > QWidget,
QWidget#mainScrollContent {{
    background-color: transparent;
    border: none;
}}

/* In-window header */
QWidget#appHeader {{
    background-color: transparent;
}}

/* Glass panels */
QWidget#card,
QWidget#progressCard {{
    background-color: {DESIGN_TOKENS["panel"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_panel"]};
}}

QWidget#card:hover,
QWidget#progressCard:hover {{
    border-color: {DESIGN_TOKENS["border_strong"]};
}}

/* Section titles inside panels */
QLabel#cardTitle,
QLabel#progressTitle {{
    color: {DESIGN_TOKENS["text"]};
    font-size: 14px;
    font-weight: 500;
}}

/* General labels */
QLabel {{
    color: {DESIGN_TOKENS["text"]};
    background-color: transparent;
}}

QLabel#muted {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 13px;
    font-weight: 400;
}}

QLabel#destinationPath {{
    color: {DESIGN_TOKENS["text"]};
    font-weight: 400;
    font-size: 13px;
}}

QLabel#currentSetLabel {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 15px;
    font-weight: 400;
}}

QLabel#currentSetValue {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-size: 15px;
    font-weight: 500;
}}

QLabel#currentSetPathValue {{
    color: {DESIGN_TOKENS["text"]};
    font-size: 13px;
    font-weight: 400;
}}

/* Inputs */
QLineEdit {{
    background-color: {DESIGN_TOKENS["field"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 7px 10px;
    color: {DESIGN_TOKENS["text_strong"]};
    selection-background-color: {DESIGN_TOKENS["accent"]};
    selection-color: {DESIGN_TOKENS["accent_text"]};
    font-size: 13px;
}}

QLineEdit:hover {{
    background-color: {DESIGN_TOKENS["field_hover"]};
    border-color: {DESIGN_TOKENS["border_strong"]};
}}

QLineEdit:focus {{
    border: 1px solid rgba(124, 196, 240, 0.72);
}}

QLineEdit:disabled {{
    background-color: rgba(24, 27, 36, 0.22);
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: rgba(220, 230, 255, 0.06);
}}

QLineEdit#exportInput,
QComboBox#exportInput {{
    min-height: 32px;
    padding: 7px 10px;
}}

/* Dropdowns */
QComboBox {{
    background-color: {DESIGN_TOKENS["field"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 7px 10px;
    color: {DESIGN_TOKENS["text_strong"]};
    min-width: 124px;
    font-size: 13px;
}}

QComboBox:hover {{
    background-color: {DESIGN_TOKENS["field_hover"]};
    border-color: {DESIGN_TOKENS["border_strong"]};
}}

QComboBox:focus {{
    border: 1px solid rgba(124, 196, 240, 0.72);
}}

QComboBox:disabled {{
    background-color: rgba(24, 27, 36, 0.22);
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: rgba(220, 230, 255, 0.06);
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid rgba(220, 230, 255, 0.08);
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {DESIGN_TOKENS["text_muted"]};
    width: 0px;
    height: 0px;
    margin-right: 9px;
}}

QComboBox QAbstractItemView {{
    background-color: {DESIGN_TOKENS["menu"]};
    border: 1px solid {DESIGN_TOKENS["border_strong"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    selection-background-color: rgba(124, 196, 240, 0.22);
    selection-color: {DESIGN_TOKENS["text_strong"]};
    padding: 5px;
    outline: none;
}}

/* Buttons */
QPushButton {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    color: {DESIGN_TOKENS["text"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {DESIGN_TOKENS["panel_hover"]};
    border-color: {DESIGN_TOKENS["border_strong"]};
    color: {DESIGN_TOKENS["text_strong"]};
}}

QPushButton:pressed {{
    background-color: rgba(24, 27, 36, 0.68);
    border-color: rgba(124, 196, 240, 0.24);
}}

QPushButton:disabled {{
    background-color: rgba(32, 36, 48, 0.24);
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: rgba(220, 230, 255, 0.055);
}}

QPushButton#primaryAction {{
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {DESIGN_TOKENS["accent_hover"]},
        stop: 1 {DESIGN_TOKENS["accent_pressed"]}
    );
    color: {DESIGN_TOKENS["accent_text"]};
    border: 1px solid rgba(196, 232, 255, 0.62);
    font-weight: 600;
}}

QPushButton#primaryAction:hover {{
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #a1dcfb,
        stop: 1 {DESIGN_TOKENS["accent"]}
    );
    border-color: rgba(220, 244, 255, 0.72);
}}

QPushButton#primaryAction:pressed {{
    background-color: {DESIGN_TOKENS["accent_pressed"]};
    border-color: rgba(124, 196, 240, 0.58);
}}

QPushButton#primaryAction:disabled {{
    background-color: rgba(124, 196, 240, 0.20);
    color: rgba(230, 244, 255, 0.44);
    border-color: rgba(124, 196, 240, 0.16);
}}

QPushButton#secondary {{
    background-color: rgba(34, 37, 49, 0.44);
    color: {DESIGN_TOKENS["text"]};
    border-color: {DESIGN_TOKENS["border"]};
}}

QPushButton[actionBarButton="true"] {{
    min-height: 34px;
    max-height: 34px;
    border-radius: 7px;
    padding: 0 16px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton#primaryAction[actionBarButton="true"] {{
    background-color: {DESIGN_TOKENS["accent"]};
    color: {DESIGN_TOKENS["accent_text"]};
    border-color: rgba(196, 232, 255, 0.46);
    font-weight: 600;
}}

QPushButton#primaryAction[actionBarButton="true"]:hover {{
    background-color: {DESIGN_TOKENS["accent_hover"]};
    border-color: rgba(220, 244, 255, 0.58);
}}

QPushButton#primaryAction[actionBarButton="true"]:pressed {{
    background-color: {DESIGN_TOKENS["accent_pressed"]};
    border-color: rgba(160, 218, 252, 0.54);
}}

QPushButton#primaryAction[actionBarButton="true"]:disabled {{
    background-color: rgba(124, 196, 240, 0.16);
    color: rgba(230, 244, 255, 0.42);
    border-color: rgba(124, 196, 240, 0.22);
}}

QPushButton#secondary[actionBarButton="true"] {{
    background-color: rgba(22, 24, 32, 0.22);
    color: rgba(244, 248, 252, 0.78);
    border-color: rgba(220, 230, 255, 0.105);
    font-weight: 500;
}}

QPushButton#secondary[actionBarButton="true"]:hover {{
    background-color: rgba(50, 54, 68, 0.40);
    color: {DESIGN_TOKENS["text_strong"]};
    border-color: rgba(220, 230, 255, 0.20);
}}

QPushButton#secondary[actionBarButton="true"]:pressed {{
    background-color: rgba(24, 27, 36, 0.54);
    border-color: rgba(124, 196, 240, 0.22);
}}

QPushButton#secondary[actionBarButton="true"]:disabled {{
    background-color: rgba(16, 24, 32, 0.24);
    color: rgba(221, 231, 242, 0.42);
    border-color: rgba(220, 230, 255, 0.13);
}}

QPushButton#headerAction {{
    background-color: transparent;
    color: {DESIGN_TOKENS["text_muted"]};
    border: none;
    border-radius: 7px;
    padding: 0px;
    font-size: 16px;
    font-weight: 400;
    min-width: 28px;
    min-height: 28px;
    max-width: 28px;
    max-height: 28px;
}}

QPushButton#headerAction:hover {{
    background-color: rgba(220, 230, 255, 0.055);
    color: {DESIGN_TOKENS["text"]};
}}

/* Lists */
QWidget#detectedStemsSection {{
    background-color: transparent;
}}

QWidget#stemListPanel {{
    background-color: rgba(35, 38, 50, 0.34);
    border: 1px solid rgba(220, 230, 255, 0.105);
    border-radius: {DESIGN_TOKENS["radius_panel"]};
}}

QListWidget {{
    background-color: transparent;
    border: none;
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 0px;
    outline: none;
}}

QListWidget::item {{
    background-color: transparent;
}}

QWidget#stemTrackRowContent {{
    background-color: transparent;
    border-radius: 6px;
}}

QWidget#stemTrackRowContent:hover {{
    background-color: rgba(220, 230, 255, 0.035);
}}

QFrame#stemTrackRowSeparator {{
    color: rgba(220, 230, 255, 0.095);
    background-color: rgba(220, 230, 255, 0.095);
    border: none;
    max-height: 1px;
}}

QLabel#stemRowIndex {{
    color: rgba(221, 231, 242, 0.72);
    font-size: 13px;
    font-weight: 400;
}}

QLabel#stemRowName {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-size: 14px;
    font-weight: 500;
}}

QLabel#stemRowStatus {{
    border: none;
    border-radius: 0px;
    font-size: 13px;
    font-weight: 400;
    padding: 0px;
}}

QLabel#stemRowStatus[statusState="detected"] {{
    color: {DESIGN_TOKENS["accent"]};
    background-color: transparent;
}}

QLabel#stemRowStatus[statusState="success"] {{
    color: {DESIGN_TOKENS["success"]};
    background-color: transparent;
    border: none;
}}

QLabel#stemRowStatus[statusState="skipped"] {{
    color: {DESIGN_TOKENS["warning"]};
    background-color: transparent;
    border: none;
}}

QLabel#stemRowStatus[statusState="failed"] {{
    color: {DESIGN_TOKENS["danger"]};
    background-color: transparent;
    border: none;
}}

/* Progress */
QWidget#progressStatusModule {{
    background-color: rgba(24, 27, 36, 0.28);
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
}}

QWidget#progressStatusModule[progressState="scan-failed"],
QWidget#progressStatusModule[progressState="export-failed"] {{
    background-color: rgba(232, 93, 93, 0.045);
    border-color: rgba(232, 93, 93, 0.22);
}}

QWidget#progressStatusModule[progressState="export-complete"] {{
    border-color: rgba(114, 227, 157, 0.18);
}}

QWidget#progressStatusModule[progressState="cancelling"],
QWidget#progressStatusModule[progressState="cancelled"] {{
    border-color: rgba(245, 213, 110, 0.20);
}}

QLabel#progressStatusIcon {{
    color: {DESIGN_TOKENS["text_muted"]};
    background-color: rgba(220, 230, 255, 0.055);
    border: 1px solid rgba(220, 230, 255, 0.13);
    border-radius: 13px;
    font-size: 12px;
    font-weight: 600;
}}

QLabel#progressStatusIcon[progressState="scanning"],
QLabel#progressStatusIcon[progressState="export-starting"],
QLabel#progressStatusIcon[progressState="export-in-progress"] {{
    color: {DESIGN_TOKENS["accent"]};
    background-color: rgba(124, 196, 240, 0.08);
    border-color: rgba(124, 196, 240, 0.34);
}}

QLabel#progressStatusIcon[progressState="export-complete"] {{
    color: {DESIGN_TOKENS["success"]};
    background-color: rgba(114, 227, 157, 0.08);
    border-color: rgba(114, 227, 157, 0.30);
}}

QLabel#progressStatusIcon[progressState="scan-failed"],
QLabel#progressStatusIcon[progressState="export-failed"] {{
    color: {DESIGN_TOKENS["danger"]};
    background-color: rgba(232, 93, 93, 0.08);
    border-color: rgba(232, 93, 93, 0.38);
}}

QLabel#progressStatusIcon[progressState="cancelling"],
QLabel#progressStatusIcon[progressState="cancelled"] {{
    color: {DESIGN_TOKENS["warning"]};
    background-color: rgba(245, 213, 110, 0.08);
    border-color: rgba(245, 213, 110, 0.30);
}}

QLabel#progressStatePill {{
    border: none;
    border-radius: {DESIGN_TOKENS["radius_pill"]};
    font-size: 14px;
    font-weight: 500;
    padding: 2px 0px;
}}

QLabel#progressStatePill[progressState="idle"] {{
    color: {DESIGN_TOKENS["text_muted"]};
    background-color: transparent;
}}

QLabel#progressStatePill[progressState="scanning"],
QLabel#progressStatePill[progressState="export-starting"],
QLabel#progressStatePill[progressState="export-in-progress"] {{
    color: {DESIGN_TOKENS["accent"]};
    background-color: transparent;
}}

QLabel#progressStatePill[progressState="export-complete"] {{
    color: {DESIGN_TOKENS["success"]};
    background-color: transparent;
}}

QLabel#progressStatePill[progressState="scan-failed"],
QLabel#progressStatePill[progressState="export-failed"] {{
    color: {DESIGN_TOKENS["danger"]};
    background-color: transparent;
}}

QLabel#progressStatePill[progressState="cancelling"],
QLabel#progressStatePill[progressState="cancelled"] {{
    color: {DESIGN_TOKENS["warning"]};
    background-color: transparent;
}}

QLabel#progressPercent {{
    color: {DESIGN_TOKENS["text"]};
    background-color: transparent;
    font-size: 14px;
    font-weight: 500;
}}

QLabel#progressPercent[progressState="idle"] {{
    color: {DESIGN_TOKENS["text_muted"]};
}}

QLabel#progressPercent[progressState="scan-failed"],
QLabel#progressPercent[progressState="export-failed"] {{
    color: rgba(244, 248, 252, 0.82);
}}

QProgressBar#progressBar {{
    background-color: rgba(220, 230, 255, 0.10);
    border: 1px solid rgba(220, 230, 255, 0.075);
    border-radius: 3px;
    color: transparent;
    min-height: 4px;
    max-height: 4px;
}}

QProgressBar#progressBar::chunk {{
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {DESIGN_TOKENS["accent_hover"]},
        stop: 1 {DESIGN_TOKENS["accent_pressed"]}
    );
    border-radius: 3px;
}}

QProgressBar#progressBar[progressState="idle"]::chunk {{
    background-color: rgba(220, 230, 255, 0.24);
}}

QProgressBar#progressBar[progressState="export-complete"]::chunk {{
    background-color: {DESIGN_TOKENS["success"]};
}}

QProgressBar#progressBar[progressState="scan-failed"]::chunk,
QProgressBar#progressBar[progressState="export-failed"]::chunk {{
    background-color: rgba(232, 93, 93, 0.74);
}}

QProgressBar#progressBar[progressState="cancelling"]::chunk,
QProgressBar#progressBar[progressState="cancelled"]::chunk {{
    background-color: {DESIGN_TOKENS["warning"]};
}}

QScrollArea#progressSummaryArea,
QWidget#progressSummaryBody {{
    background-color: transparent;
    border: none;
}}

QLabel#progressSummary {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 13px;
    font-weight: 400;
}}

QLabel#progressSummary[progressState="scan-failed"],
QLabel#progressSummary[progressState="export-failed"] {{
    color: rgba(221, 231, 242, 0.72);
}}

/* Checkboxes */
QCheckBox {{
    color: {DESIGN_TOKENS["text"]};
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 9px;
    border: 1px solid rgba(124, 196, 240, 0.62);
    background-color: rgba(124, 196, 240, 0.05);
}}

QCheckBox::indicator:hover {{
    border-color: rgba(161, 220, 251, 0.78);
    background-color: rgba(124, 196, 240, 0.11);
}}

QCheckBox::indicator:checked {{
    background-color: rgba(124, 196, 240, 0.22);
    border-color: {DESIGN_TOKENS["accent"]};
}}

QCheckBox::indicator:disabled {{
    border-color: rgba(220, 230, 255, 0.13);
    background-color: rgba(220, 230, 255, 0.04);
}}

QCheckBox#stemRowCheckbox {{
    background-color: rgba(124, 196, 240, 0.10);
    border: 1px solid rgba(124, 196, 240, 0.74);
    border-radius: 11px;
    color: {DESIGN_TOKENS["accent_hover"]};
    font-size: 13px;
    font-weight: 600;
    padding-left: 4px;
    padding-top: 0px;
    spacing: 0px;
}}

QCheckBox#stemRowCheckbox:hover {{
    background-color: rgba(124, 196, 240, 0.15);
    border-color: rgba(161, 220, 251, 0.86);
}}

QCheckBox#stemRowCheckbox:unchecked {{
    background-color: transparent;
    border-color: rgba(124, 196, 240, 0.46);
    color: transparent;
}}

QCheckBox#stemRowCheckbox::indicator {{
    width: 0px;
    height: 0px;
    border: none;
    background-color: transparent;
}}

/* Menus and dialogs */
QMenu {{
    background-color: {DESIGN_TOKENS["menu"]};
    border: 1px solid {DESIGN_TOKENS["border_strong"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 5px;
}}

QMenu::item {{
    padding: 6px 22px;
    border-radius: 6px;
    background-color: transparent;
    color: {DESIGN_TOKENS["text"]};
    font-size: 13px;
}}

QMenu::item:selected {{
    background-color: rgba(124, 196, 240, 0.20);
    color: {DESIGN_TOKENS["text_strong"]};
}}

QDialogButtonBox QPushButton {{
    min-width: 82px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 2px 0px 2px 0px;
}}

QScrollBar::handle:vertical {{
    background-color: rgba(220, 230, 255, 0.16);
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: rgba(220, 230, 255, 0.26);
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""


def _compact_stylesheet() -> str:
    replacements = [
        ("padding: 7px 10px;", "padding: 5px 8px;"),
        ("padding: 8px 16px;", "padding: 5px 10px;"),
        ("padding: 0 16px;", "padding: 0 10px;"),
        ("padding: 6px 22px;", "padding: 4px 16px;"),
        ("min-height: 32px;", "min-height: 26px;"),
        ("min-height: 34px;", "min-height: 28px;"),
        ("max-height: 34px;", "max-height: 28px;"),
        ("min-width: 124px;", "min-width: 100px;"),
        ("width: 28px;", "width: 22px;"),
        ("margin-right: 9px;", "margin-right: 7px;"),
        ("border-radius: 6px;", "border-radius: 5px;"),
        ("border-radius: 7px;", "border-radius: 6px;"),
        ("border-radius: 8px;", "border-radius: 6px;"),
        ("border-radius: 9px;", "border-radius: 7px;"),
        ("border-radius: 10px;", "border-radius: 8px;"),
        ("border-radius: 11px;", "border-radius: 9px;"),
        ("border-radius: 13px;", "border-radius: 10px;"),
        ("width: 17px;", "width: 14px;"),
        ("height: 17px;", "height: 14px;"),
        ("padding-left: 4px;", "padding-left: 3px;"),
        ("padding: 5px;", "padding: 4px;"),
        ("min-width: 82px;", "min-width: 68px;"),
        ("width: 8px;", "width: 6px;"),
        ("min-height: 30px;", "min-height: 24px;"),
    ]
    stylesheet = DARK_STYLESHEET
    for old, new in replacements:
        stylesheet = stylesheet.replace(old, new)
    return stylesheet


BASE_STYLESHEET = _compact_stylesheet()


_stylesheet_cache: dict[float, str] = {}


def stylesheet_for_scale(scale: float) -> str:
    key = round(scale, 2)
    if key not in _stylesheet_cache:
        def replace_px(match: re.Match[str]) -> str:
            value = int(match.group(1))
            if value == 0:
                return "0px"
            return f"{max(1, round(value * key))}px"
        _stylesheet_cache[key] = re.sub(r"(\d+)px", replace_px, BASE_STYLESHEET)
    return _stylesheet_cache[key]
