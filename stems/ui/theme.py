from __future__ import annotations

import re

DESIGN_TOKENS = {
    "background": "#15171b",
    "panel": "#1d2026",
    "panel_soft": "#242930",
    "panel_hover": "#2a3038",
    "field": "#171a1f",
    "field_hover": "#1d2127",
    "border": "#353b45",
    "border_strong": "#4a525e",
    "separator": "#30363f",
    "text": "#dfe3e8",
    "text_strong": "#f2f4f7",
    "text_muted": "#aab2be",
    "text_faint": "#737c89",
    "accent": "#69c7bc",
    "accent_hover": "#78d3c7",
    "accent_pressed": "#58b9ae",
    "success": "#74c991",
    "warning": "#f5d56e",
    "danger": "#e85d5d",
    "accent_text": "#071614",
    "menu": "#1d2026",
    "radius_panel": "8px",
    "radius_control": "7px",
    "radius_pill": "10px",
    "font_family": '".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue"',
}


DARK_STYLESHEET = f"""
/* Core windows */
QMainWindow,
QDialog {{
    background-color: {DESIGN_TOKENS["background"]};
    font-family: {DESIGN_TOKENS["font_family"]};
    font-size: 13px;
}}

/* Central widget reference */
QWidget#centralWidget {{
    background-color: {DESIGN_TOKENS["background"]};
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

QLabel#appTitle {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-family: "SF Pro Display", ".AppleSystemUIFont", "Helvetica Neue";
    font-size: 18px;
    font-weight: 600;
}}

/* Product surfaces */
QWidget#card,
QWidget#progressCard,
QWidget#currentSetSection {{
    background-color: {DESIGN_TOKENS["panel"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_panel"]};
}}

/* Section titles inside panels */
QLabel#cardTitle {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-size: 14px;
    font-weight: 600;
}}

/* General labels */
QLabel {{
    color: {DESIGN_TOKENS["text"]};
    background-color: transparent;
}}

QLabel#muted {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 11px;
    font-weight: 500;
}}

QLabel#destinationPath {{
    color: {DESIGN_TOKENS["text"]};
    font-weight: 400;
    font-size: 13px;
}}

QLabel#currentSetEyebrow {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-family: "SF Mono", Menlo, monospace;
    font-size: 10px;
    font-weight: 500;
}}

QLabel#currentSetValue {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-family: "SF Pro Display", ".AppleSystemUIFont", "Helvetica Neue";
    font-size: 17px;
    font-weight: 600;
}}

QLabel#currentSetBpm {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-family: "SF Mono", Menlo, monospace;
    font-size: 11px;
    font-weight: 500;
}}

QLabel#currentSetPathValue {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 12px;
    font-weight: 400;
}}

QLabel#selectionCount {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-family: "SF Mono", Menlo, monospace;
    font-size: 11px;
    font-weight: 500;
}}

/* Export confirmation */
QLabel#exportConfirmationHeading {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-size: 20px;
    font-weight: 600;
}}

QLabel#exportConfirmationSupporting {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 13px;
    font-weight: 400;
}}

QLabel#exportConfirmationMetadataLabel {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 12px;
    font-weight: 500;
}}

QLabel#exportConfirmationDestination {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-size: 16px;
    font-weight: 600;
}}

QLabel#exportConfirmationDestinationParent {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 12px;
    font-weight: 400;
}}

QLabel#exportConfirmationMode {{
    color: {DESIGN_TOKENS["text"]};
    font-size: 13px;
    font-weight: 500;
}}

QLabel#exportConfirmationMode[modeState="replace"] {{
    color: {DESIGN_TOKENS["warning"]};
}}

QLabel#exportConfirmationTrackList {{
    color: {DESIGN_TOKENS["text"]};
    font-size: 13px;
    font-weight: 400;
}}

QScrollArea#exportConfirmationTrackScroll {{
    background-color: transparent;
    border: none;
}}

QFrame#exportConfirmationSeparator {{
    background-color: {DESIGN_TOKENS["separator"]};
    color: {DESIGN_TOKENS["separator"]};
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
    border: 2px solid {DESIGN_TOKENS["accent"]};
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
    border: 2px solid {DESIGN_TOKENS["accent"]};
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

QPushButton:focus {{
    border: 2px solid {DESIGN_TOKENS["accent"]};
}}

QPushButton:disabled {{
    background-color: rgba(32, 36, 48, 0.24);
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: rgba(220, 230, 255, 0.055);
}}

QPushButton#primaryAction {{
    background-color: {DESIGN_TOKENS["accent"]};
    color: {DESIGN_TOKENS["accent_text"]};
    border: 1px solid rgba(196, 232, 255, 0.62);
    font-weight: 600;
}}

QPushButton#primaryAction:hover {{
    background-color: {DESIGN_TOKENS["accent_hover"]};
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
    background-color: {DESIGN_TOKENS["panel"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
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
    color: {DESIGN_TOKENS["text_faint"]};
    font-family: "SF Mono", Menlo, monospace;
    font-size: 11px;
    font-weight: 500;
}}

QLabel#stemRowName {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-size: 14px;
    font-weight: 500;
}}

QLabel#stemRowStatus {{
    border: none;
    border-radius: 0px;
    font-size: 12px;
    font-weight: 500;
    padding: 0px;
}}

QLabel#stemRowStatus[statusState="detected"] {{
    color: {DESIGN_TOKENS["text_muted"]};
    background-color: transparent;
}}

QLabel#stemRowStatus[statusState="exporting"] {{
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
QLabel#progressStatus {{
    color: {DESIGN_TOKENS["text_strong"]};
    background-color: transparent;
    border: none;
    font-size: 14px;
    font-weight: 500;
}}

QLabel#progressStatus[progressState="scan-failed"],
QLabel#progressStatus[progressState="export-failed"] {{
    color: {DESIGN_TOKENS["danger"]};
}}

QLabel#progressPercent {{
    color: {DESIGN_TOKENS["text_muted"]};
    background-color: transparent;
    font-size: 13px;
    font-weight: 400;
}}

QProgressBar#progressBar {{
    background-color: rgba(220, 230, 255, 0.09);
    border: none;
    border-radius: 2px;
    color: transparent;
    min-height: 4px;
    max-height: 4px;
}}

QProgressBar#progressBar::chunk {{
    background-color: {DESIGN_TOKENS["accent"]};
    border-radius: 2px;
}}

QLabel#progressDetail {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 13px;
    font-weight: 400;
}}

QLabel#progressDetail[progressState="scan-failed"],
QLabel#progressDetail[progressState="export-failed"] {{
    color: {DESIGN_TOKENS["text_muted"]};
}}

/* Checkboxes */
QCheckBox {{
    color: {DESIGN_TOKENS["text"]};
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox:focus {{
    color: {DESIGN_TOKENS["text_strong"]};
}}

QCheckBox#stemRowCheckbox {{
    background-color: rgba(105, 199, 188, 0.11);
    border: 1px solid rgba(105, 199, 188, 0.78);
    border-radius: 6px;
    color: {DESIGN_TOKENS["accent_hover"]};
    font-size: 13px;
    font-weight: 600;
    padding-left: 7px;
    padding-top: 0px;
    spacing: 0px;
}}

QCheckBox#stemRowCheckbox:hover {{
    background-color: rgba(105, 199, 188, 0.18);
    border-color: rgba(120, 211, 199, 0.92);
}}

QCheckBox#stemRowCheckbox:unchecked {{
    background-color: transparent;
    border-color: rgba(170, 178, 190, 0.42);
    color: transparent;
}}

QCheckBox#stemRowCheckbox::indicator {{
    width: 0px;
    height: 0px;
    border: none;
    background-color: transparent;
}}

QWidget#destinationControl {{
    background-color: transparent;
}}

/* Menus and dialogs */
QTabWidget::pane {{
    background-color: {DESIGN_TOKENS["panel"]};
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 10px;
    top: -1px;
}}

QWidget#preferencesGeneral,
QWidget#preferencesNaming {{
    background-color: transparent;
}}

QFrame#preferencesGroup {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 10px;
}}

QLabel#preferencesGroupTitle {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-family: "SF Mono", Menlo, monospace;
    font-size: 10px;
    font-weight: 600;
    padding-bottom: 4px;
}}

QWidget#preferencesSettingRow {{
    background-color: transparent;
}}

QLabel#preferencesSettingLabel {{
    color: {DESIGN_TOKENS["text"]};
    font-size: 13px;
    font-weight: 500;
}}

QFrame#preferencesSeparator {{
    background-color: {DESIGN_TOKENS["separator"]};
    border: none;
    max-height: 1px;
}}

QComboBox#preferencesReplaceMode {{
    min-width: 192px;
    min-height: 24px;
    padding-top: 6px;
    padding-bottom: 6px;
}}

QCheckBox#preferencesToggle {{
    min-width: 40px;
    min-height: 40px;
    spacing: 0px;
}}

QCheckBox#preferencesToggle::indicator {{
    width: 18px;
    height: 18px;
}}

QPushButton#preferencesUtilityAction,
QPushButton#preferencesResetAction {{
    min-height: 30px;
    padding: 4px 12px;
}}

QPushButton#preferencesUtilityAction {{
    color: {DESIGN_TOKENS["accent_hover"]};
}}

QPushButton#preferencesResetAction {{
    background-color: transparent;
    color: {DESIGN_TOKENS["text_muted"]};
    border-color: transparent;
}}

QPushButton#preferencesResetAction:hover {{
    background-color: rgba(232, 93, 93, 0.10);
    color: #ffaaa4;
    border-color: rgba(232, 93, 93, 0.24);
}}

QLabel#preferencesSaveStatus {{
    color: {DESIGN_TOKENS["success"]};
    font-size: 12px;
    font-weight: 500;
    padding: 0 4px;
}}

QLabel#preferencesSaveStatus[saveState="pending"] {{
    color: {DESIGN_TOKENS["warning"]};
}}

QFrame#namingPresetCard {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
}}

QLabel#preferencesFieldTitle {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-weight: 600;
}}

QLabel#preferencesSubLabel {{
    color: {DESIGN_TOKENS["text"]};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#preferencesHint {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 13px;
}}

QLabel#preferencesError {{
    color: #ffaaa4;
    font-size: 12px;
}}

QLabel#presetDefaultBadge {{
    background-color: rgba(124, 196, 240, 0.16);
    color: {DESIGN_TOKENS["accent_hover"]};
    border: 1px solid rgba(124, 196, 240, 0.42);
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QPushButton#tokenButton {{
    min-width: 54px;
    padding: 5px 9px;
    background-color: {DESIGN_TOKENS["field"]};
    color: {DESIGN_TOKENS["accent_hover"]};
    border: 1px solid {DESIGN_TOKENS["border_strong"]};
    border-radius: 7px;
    font-family: "SF Mono", Menlo, monospace;
    font-size: 12px;
}}

QPushButton#tokenButton:hover {{
    background-color: rgba(124, 196, 240, 0.14);
    border-color: rgba(161, 220, 251, 0.72);
}}

QPushButton#tokenButton:pressed {{
    background-color: rgba(124, 196, 240, 0.24);
}}

QPushButton#tokenButton:focus,
QPushButton#presetSecondaryAction:focus,
QPushButton#presetDefaultAction:focus {{
    border-color: {DESIGN_TOKENS["accent"]};
}}

QPushButton#presetSecondaryAction,
QPushButton#presetDefaultAction {{
    min-height: 34px;
    padding: 0 12px;
}}

QPushButton#presetDefaultAction {{
    color: {DESIGN_TOKENS["accent_hover"]};
    border-color: rgba(124, 196, 240, 0.56);
}}

QLabel#preferencesPreview {{
    background-color: {DESIGN_TOKENS["field"]};
    color: {DESIGN_TOKENS["text"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: 6px;
    padding: 10px;
    font-family: "SF Mono", Menlo, monospace;
    font-size: 13px;
}}

QTabBar::tab {{
    background-color: {DESIGN_TOKENS["background"]};
    color: {DESIGN_TOKENS["text_muted"]};
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-bottom: none;
    min-width: 94px;
    min-height: 28px;
    padding: 5px 12px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {DESIGN_TOKENS["panel"]};
    color: {DESIGN_TOKENS["text_strong"]};
}}

QTabBar::tab:hover:!selected {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    color: {DESIGN_TOKENS["text"]};
}}

QTabBar::tab:focus {{
    border-color: {DESIGN_TOKENS["accent"]};
}}

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


BASE_STYLESHEET = DARK_STYLESHEET


_stylesheet_cache: dict[float, str] = {}


def stylesheet_for_scale(scale: float) -> str:
    key = round(scale, 2)
    if key not in _stylesheet_cache:
        def replace_px(match: re.Match[str]) -> str:
            property_name = match.group(1) or ""
            value = int(match.group(2))
            if value == 0:
                return f"{property_name}0px"
            applied_scale = max(0.9, key) if property_name else key
            return f"{property_name}{max(1, round(value * applied_scale))}px"
        _stylesheet_cache[key] = re.sub(r"(font-size:\s*)?(\d+)px", replace_px, BASE_STYLESHEET)
    return _stylesheet_cache[key]
