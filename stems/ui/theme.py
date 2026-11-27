from __future__ import annotations

import re
import sys
from pathlib import Path

_ASSET_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
_CHEVRON_PATH = (_ASSET_ROOT / "assets/ui/chevron-down.svg").as_posix()
_CHECK_PATH = (_ASSET_ROOT / "assets/ui/check.svg").as_posix()

CLIP_COLORS = ("#ff5a5c", "#55c7f2", "#9483f2", "#ffd23f")

DURATION_TWEEN = 140
DURATION_FAST = 150
DURATION_DIALOG = 160
DURATION_REBUILD = 180
DURATION_BASE = 200
DURATION_SUCCESS = 220
SCAN_COMPLETE_HOLD_MS = 1200

DESIGN_TOKENS = {
    "background": "#141415",
    "panel": "#1b1b1d",
    "panel_soft": "#232325",
    "panel_soft_hover": "#2a2a2d",
    "panel_hover": "#232325",
    "field": "#19191b",
    "field_hover": "#1f1f22",
    "field_disabled": "#161618",
    "border": "rgba(237, 237, 237, 0.10)",
    "border_subtle": "rgba(237, 237, 237, 0.06)",
    "border_pressed": "rgba(237, 237, 237, 0.14)",
    "border_strong": "rgba(237, 237, 237, 0.20)",
    "separator": "rgba(237, 237, 237, 0.08)",
    "checkbox_border": "#55555a",
    "chip_bg": "rgba(237, 237, 237, 0.06)",
    "chip_hover": "rgba(237, 237, 237, 0.10)",
    "ruler_muted": "rgba(237, 237, 237, 0.22)",
    "scrollbar_handle": "rgba(237, 237, 237, 0.16)",
    "scrollbar_handle_hover": "rgba(237, 237, 237, 0.26)",
    "text": "#ededed",
    "text_strong": "#ededed",
    "text_muted": "#a1a1a6",
    "text_faint": "#85858b",
    "accent": "#ededed",
    "accent_hover": "#ffffff",
    "accent_pressed": "#d4d4d6",
    "success": "#4cc38a",
    "warning": "#e8b84a",
    "danger": "#e5484d",
    "danger_hover": "#f2555a",
    "danger_pressed": "#c93b40",
    "danger_text": "#ffffff",
    "accent_text": "#141415",
    "clip_ink_dark": "#141415",
    "clip_ink_light": "#f4f4f5",
    "menu": "#1b1b1d",
    "radius_card": "12px",
    "radius_control": "8px",
    "radius_chip": "6px",
    "radius_micro": "4px",
    "font_family": '".AppleSystemUIFont", "Helvetica Neue"',
    "font_mono": '"SF Mono", "Menlo", monospace',
}


DARK_STYLESHEET = f"""
/* Core windows */
QWidget {{
    font-family: {DESIGN_TOKENS["font_family"]};
}}

QMainWindow,
QDialog,
QMessageBox {{
    background-color: {DESIGN_TOKENS["background"]};
    color: {DESIGN_TOKENS["text"]};
    font-family: {DESIGN_TOKENS["font_family"]};
    font-size: 13px;
}}

QMessageBox QLabel {{
    color: {DESIGN_TOKENS["text"]};
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
    font-family: ".AppleSystemUIFont", "Helvetica Neue";
    font-size: 18px;
    font-weight: 600;
}}

QLabel#dialogTitle {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-family: ".AppleSystemUIFont", "Helvetica Neue";
    font-size: 18px;
    font-weight: 600;
}}

/* Product surfaces */
QWidget#card,
QWidget#currentSetSection,
QWidget#progressCard {{
    background-color: transparent;
    border: none;
}}

QWidget#exportConfirmCard {{
    background-color: {DESIGN_TOKENS["panel"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_card"]};
}}

QFrame#exportConfirmSeparator {{
    background-color: {DESIGN_TOKENS["separator"]};
    color: {DESIGN_TOKENS["separator"]};
    border: none;
    min-height: 1px;
    max-height: 1px;
}}

QWidget#exportRangeBanner {{
    background-color: {DESIGN_TOKENS["panel"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_card"]};
}}

QWidget#footerDock {{
    background-color: {DESIGN_TOKENS["background"]};
    border-top: 1px solid {DESIGN_TOKENS["separator"]};
}}

/* General labels */
QLabel {{
    color: {DESIGN_TOKENS["text"]};
    background-color: transparent;
}}

QLabel#muted {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 12px;
    font-weight: 400;
}}

QLabel#exportConfirmLabel {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-size: 12px;
    font-weight: 400;
}}

QLabel#exportConfirmValue {{
    color: {DESIGN_TOKENS["text"]};
    font-family: {DESIGN_TOKENS["font_mono"]};
    font-size: 13px;
    font-weight: 400;
}}

QLabel#exportConfirmConflict {{
    color: {DESIGN_TOKENS["warning"]};
    font-size: 12px;
    font-weight: 500;
}}

QLabel#exportRangeLabel {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-size: 12px;
    font-weight: 400;
}}

QLabel#exportRangeHeadline {{
    color: {DESIGN_TOKENS["text"]};
    font-family: {DESIGN_TOKENS["font_family"]};
    font-size: 18px;
    font-weight: 500;
}}

QLabel#exportRangeMeta {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-family: {DESIGN_TOKENS["font_mono"]};
    font-size: 12px;
    font-weight: 400;
}}

QLabel#preferencesSavedLabel,
QLabel[saveState="saved"] {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-family: {DESIGN_TOKENS["font_family"]};
    font-size: 12px;
    font-weight: 400;
    padding-right: 4px;
}}

QLabel#pathTrailName {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 13px;
    font-weight: 400;
}}

QLabel#pathTrailLast {{
    color: {DESIGN_TOKENS["text"]};
    font-size: 13px;
    font-weight: 500;
}}

QLabel#pathTrailChevron {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-size: 12px;
    padding: 0px 4px;
}}

QLabel#pathTrailEmpty {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-size: 13px;
    font-weight: 500;
}}

QLabel#pathTrailNote {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-size: 12px;
    font-weight: 400;
    padding-left: 8px;
}}

QLabel#currentSetValue {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-family: {DESIGN_TOKENS["font_family"]};
    font-size: 30px;
    font-weight: 600;
}}

QLabel#currentSetBpm,
QLabel#currentSetMetaSep,
QLabel#selectionCount {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-family: {DESIGN_TOKENS["font_mono"]};
    font-size: 12px;
    font-weight: 400;
}}

QLabel#emptyStems {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 13px;
    padding: 0px;
}}

/* Inputs */
QLineEdit {{
    background-color: {DESIGN_TOKENS["field"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 0px 12px;
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
    border: 1px solid {DESIGN_TOKENS["accent"]};
}}

QLineEdit:disabled {{
    background-color: {DESIGN_TOKENS["field_disabled"]};
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: {DESIGN_TOKENS["border_subtle"]};
}}

QLineEdit#exportInput {{
    min-height: 36px;
    max-height: 36px;
    padding: 0px 12px;
}}

/* Dropdowns */
QComboBox {{
    background-color: {DESIGN_TOKENS["field"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 4px 32px 4px 12px;
    color: {DESIGN_TOKENS["text_strong"]};
    min-width: 124px;
    min-height: 22px;
    font-size: 13px;
}}

QComboBox:hover {{
    background-color: {DESIGN_TOKENS["field_hover"]};
    border-color: {DESIGN_TOKENS["border_strong"]};
}}

QComboBox:focus {{
    border: 1px solid {DESIGN_TOKENS["accent"]};
}}

QComboBox:disabled {{
    background-color: {DESIGN_TOKENS["field_disabled"]};
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: {DESIGN_TOKENS["border_subtle"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
}}

QComboBox::down-arrow {{
    image: url("{_CHEVRON_PATH}");
    width: 12px;
    height: 12px;
}}

QComboBox QAbstractItemView {{
    background-color: {DESIGN_TOKENS["menu"]};
    border: 1px solid {DESIGN_TOKENS["border_strong"]};
    border-radius: {DESIGN_TOKENS["radius_card"]};
    selection-background-color: {DESIGN_TOKENS["panel_hover"]};
    selection-color: {DESIGN_TOKENS["text_strong"]};
    color: {DESIGN_TOKENS["text"]};
    padding: 4px;
    outline: none;
}}

/* Buttons */
QPushButton {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    color: {DESIGN_TOKENS["text"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 0px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 36px;
}}

QPushButton:hover {{
    background-color: {DESIGN_TOKENS["panel_soft_hover"]};
    border-color: {DESIGN_TOKENS["border_strong"]};
    color: {DESIGN_TOKENS["text_strong"]};
}}

QPushButton:pressed {{
    background-color: {DESIGN_TOKENS["panel"]};
    border-color: {DESIGN_TOKENS["border_pressed"]};
}}

QPushButton:focus {{
    border: 1px solid {DESIGN_TOKENS["accent"]};
}}

QPushButton:disabled {{
    background-color: transparent;
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: {DESIGN_TOKENS["border"]};
}}

QPushButton:default,
QPushButton#primaryAction {{
    background-color: {DESIGN_TOKENS["accent"]};
    color: {DESIGN_TOKENS["accent_text"]};
    border: 1px solid {DESIGN_TOKENS["accent"]};
    font-weight: 500;
}}

QPushButton:default:hover,
QPushButton#primaryAction:hover {{
    background-color: {DESIGN_TOKENS["accent_hover"]};
    border-color: {DESIGN_TOKENS["accent_hover"]};
    color: {DESIGN_TOKENS["accent_text"]};
}}

QPushButton:default:pressed,
QPushButton#primaryAction:pressed {{
    background-color: {DESIGN_TOKENS["accent_pressed"]};
    border-color: {DESIGN_TOKENS["accent_pressed"]};
    color: {DESIGN_TOKENS["accent_text"]};
}}

QPushButton:default:focus,
QPushButton#primaryAction:focus {{
    border: 1px solid {DESIGN_TOKENS["accent"]};
}}

QPushButton:default:disabled,
QPushButton#primaryAction:disabled {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: {DESIGN_TOKENS["border"]};
}}

QPushButton#dangerAction {{
    background-color: {DESIGN_TOKENS["danger"]};
    color: {DESIGN_TOKENS["danger_text"]};
    border: 1px solid {DESIGN_TOKENS["danger"]};
    border-radius: {DESIGN_TOKENS["radius_control"]};
    font-weight: 500;
}}

QPushButton#dangerAction:hover {{
    background-color: {DESIGN_TOKENS["danger_hover"]};
    border-color: {DESIGN_TOKENS["danger_hover"]};
    color: {DESIGN_TOKENS["danger_text"]};
}}

QPushButton#dangerAction:pressed {{
    background-color: {DESIGN_TOKENS["danger_pressed"]};
    border-color: {DESIGN_TOKENS["danger_pressed"]};
    color: {DESIGN_TOKENS["danger_text"]};
}}

QPushButton#dangerAction:focus {{
    border: 1px solid {DESIGN_TOKENS["accent"]};
}}

QPushButton#dangerAction:disabled {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: {DESIGN_TOKENS["border"]};
}}

QPushButton#secondary {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    color: {DESIGN_TOKENS["text"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    font-weight: 500;
}}

QPushButton#secondary:hover {{
    background-color: {DESIGN_TOKENS["panel_soft_hover"]};
    border-color: {DESIGN_TOKENS["border_strong"]};
    color: {DESIGN_TOKENS["text_strong"]};
}}

QPushButton#secondary:pressed {{
    background-color: {DESIGN_TOKENS["panel"]};
    border-color: {DESIGN_TOKENS["border_pressed"]};
}}

QPushButton#secondary:focus {{
    border: 1px solid {DESIGN_TOKENS["accent"]};
}}

QPushButton#secondary:disabled {{
    background-color: transparent;
    color: {DESIGN_TOKENS["text_faint"]};
    border-color: {DESIGN_TOKENS["border"]};
}}

QPushButton[actionBarButton="true"] {{
    min-height: 36px;
    max-height: 36px;
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 0px 16px;
    font-size: 13px;
}}

QPushButton#headerAction {{
    background-color: transparent;
    color: {DESIGN_TOKENS["text_muted"]};
    border: 1px solid transparent;
    border-radius: {DESIGN_TOKENS["radius_control"]};
    padding: 0px;
    font-size: 16px;
    font-weight: 400;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

QPushButton#headerAction:hover {{
    background-color: {DESIGN_TOKENS["panel_hover"]};
    color: {DESIGN_TOKENS["text"]};
}}

QPushButton#headerAction:pressed {{
    background-color: {DESIGN_TOKENS["panel"]};
}}

QPushButton#headerAction:focus {{
    border: 1px solid {DESIGN_TOKENS["accent"]};
}}

/* Preferences dialog */
QDialog#preferencesDialog QLabel#dialogTitle {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-family: {DESIGN_TOKENS["font_family"]};
    font-size: 18px;
    font-weight: 600;
}}

QLabel#prefsSubtitle {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 12px;
    font-weight: 400;
}}

QLabel#prefsGroupTitle {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-size: 13px;
    font-weight: 500;
    padding-left: 4px;
}}

QWidget#prefsGroup {{
    background-color: {DESIGN_TOKENS["panel"]};
    border: 1px solid {DESIGN_TOKENS["border"]};
    border-radius: {DESIGN_TOKENS["radius_card"]};
}}

QFrame#prefsRowSeparator {{
    background-color: {DESIGN_TOKENS["separator"]};
    border: none;
    max-height: 1px;
}}

QLabel#prefsRowLabel {{
    color: {DESIGN_TOKENS["text"]};
    font-size: 13px;
    font-weight: 400;
}}

QLabel#prefsRowHint {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-size: 11px;
    font-weight: 400;
}}

QPushButton#nameBlockToken {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    color: {DESIGN_TOKENS["text_strong"]};
    border: 1px solid {DESIGN_TOKENS["border_strong"]};
    border-radius: {DESIGN_TOKENS["radius_chip"]};
    padding: 0px 12px;
    min-height: 28px;
    max-height: 28px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton#nameBlockToken:hover {{
    background-color: {DESIGN_TOKENS["panel_soft_hover"]};
}}

QPushButton#nameBlockText {{
    background-color: {DESIGN_TOKENS["chip_bg"]};
    color: {DESIGN_TOKENS["text_muted"]};
    border: none;
    border-radius: {DESIGN_TOKENS["radius_chip"]};
    padding: 0px 8px;
    min-height: 28px;
    max-height: 28px;
    font-size: 13px;
    font-weight: 400;
}}

QPushButton#nameBlockText:hover {{
    color: {DESIGN_TOKENS["text_strong"]};
    background-color: {DESIGN_TOKENS["chip_hover"]};
}}

QPushButton#nameBlockAdd {{
    background-color: transparent;
    color: {DESIGN_TOKENS["text_muted"]};
    border: 1px dashed {DESIGN_TOKENS["border_strong"]};
    border-radius: {DESIGN_TOKENS["radius_chip"]};
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0px;
    font-size: 16px;
    font-weight: 500;
}}

QPushButton#nameBlockAdd:hover {{
    background-color: {DESIGN_TOKENS["panel_soft"]};
    color: {DESIGN_TOKENS["text_strong"]};
}}

QPushButton#nameBuilderTextToggle {{
    background-color: transparent;
    color: {DESIGN_TOKENS["text_muted"]};
    border: none;
    padding: 0px;
    font-size: 12px;
    text-decoration: none;
}}

QPushButton#nameBuilderTextToggle:hover {{
    color: {DESIGN_TOKENS["text_strong"]};
    background-color: transparent;
}}

QLabel#nameLooksLike {{
    color: {DESIGN_TOKENS["text_strong"]};
    font-family: {DESIGN_TOKENS["font_mono"]};
    font-size: 13px;
    font-weight: 500;
}}

QLabel#nameLooksLikeCaption {{
    color: {DESIGN_TOKENS["text_faint"]};
    font-size: 11px;
    font-weight: 400;
}}

QLabel#prefsError {{
    color: {DESIGN_TOKENS["danger"]};
    font-size: 12px;
    font-weight: 400;
}}

QWidget#prefsGroup QComboBox {{
    min-width: 180px;
}}

/* Lists */
QWidget#detectedStemsSection,
QWidget#stemListPanel {{
    background-color: transparent;
    border: none;
}}

QListWidget,
QListWidget#stemTrackList {{
    background-color: transparent;
    border: none;
    padding: 0px;
    outline: none;
}}

QListWidget::item {{
    background-color: transparent;
    border: none;
    padding: 0px;
}}

QWidget#stemTrackRow {{
    background-color: transparent;
}}

QLabel#stemRowStatus {{
    border: none;
    border-radius: 0px;
    font-size: 12px;
    font-weight: 500;
    padding: 0px;
    background-color: transparent;
}}

QLabel#stemRowStatus[statusState="detected"] {{
    color: {DESIGN_TOKENS["text_muted"]};
}}

QLabel#stemRowStatus[statusState="exporting"] {{
    color: {DESIGN_TOKENS["text"]};
}}

QLabel#stemRowStatus[statusState="success"] {{
    color: {DESIGN_TOKENS["accent_text"]};
}}

QLabel#stemRowStatus[statusState="skipped"] {{
    color: {DESIGN_TOKENS["warning"]};
}}

QLabel#stemRowStatus[statusState="failed"] {{
    color: {DESIGN_TOKENS["danger"]};
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
    font-family: {DESIGN_TOKENS["font_mono"]};
    font-size: 12px;
    font-weight: 400;
}}

QProgressBar#progressBar {{
    background-color: {DESIGN_TOKENS["border"]};
    border: none;
    border-radius: 0px;
    color: transparent;
    min-height: 2px;
    max-height: 2px;
}}

QProgressBar#progressBar::chunk {{
    background-color: {DESIGN_TOKENS["accent"]};
    border-radius: 0px;
}}

QLabel#progressDetail {{
    color: {DESIGN_TOKENS["text_muted"]};
    font-size: 12px;
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

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: {DESIGN_TOKENS["radius_micro"]};
}}

QCheckBox::indicator:unchecked {{
    background-color: transparent;
    border: 1.5px solid {DESIGN_TOKENS["checkbox_border"]};
}}

QCheckBox::indicator:unchecked:hover {{
    border-color: {DESIGN_TOKENS["text_muted"]};
}}

QCheckBox::indicator:checked {{
    background-color: {DESIGN_TOKENS["accent"]};
    border: 1.5px solid {DESIGN_TOKENS["accent"]};
    image: url("{_CHECK_PATH}");
}}

QCheckBox::indicator:checked:hover {{
    background-color: {DESIGN_TOKENS["accent_hover"]};
    border-color: {DESIGN_TOKENS["accent_hover"]};
    image: url("{_CHECK_PATH}");
}}

QCheckBox#stemRowCheckbox {{
    background-color: transparent;
    border: none;
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

/* Menus */
QMenu {{
    background-color: {DESIGN_TOKENS["menu"]};
    border: 1px solid {DESIGN_TOKENS["border_strong"]};
    border-radius: {DESIGN_TOKENS["radius_card"]};
    padding: 4px;
}}

QMenu::item {{
    padding: 8px 16px;
    border-radius: {DESIGN_TOKENS["radius_control"]};
    background-color: transparent;
    color: {DESIGN_TOKENS["text"]};
    font-size: 13px;
}}

QMenu::item:selected {{
    background-color: {DESIGN_TOKENS["panel_hover"]};
    color: {DESIGN_TOKENS["text_strong"]};
}}

QDialogButtonBox QPushButton {{
    min-width: 82px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 4px 0px 4px 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {DESIGN_TOKENS["scrollbar_handle"]};
    border-radius: {DESIGN_TOKENS["radius_micro"]};
    min-height: 32px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {DESIGN_TOKENS["scrollbar_handle_hover"]};
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
        _stylesheet_cache[key] = re.sub(r"(font-size:\s*)?(?<![\d.])(\d+)px", replace_px, BASE_STYLESHEET)
    return _stylesheet_cache[key]
