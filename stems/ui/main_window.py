from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from ..ableton import AbletonClient
from ..models import ExportJob, ExportResult, StemTrack
from ..osc import OSCGateway
from ..preferences import Preferences, PreferencesStore, RecentExport, append_recent_export
from ..reporting import build_export_summary
from ..state import AppState

try:
    from PySide6.QtCore import QPointF, QSize, QThread, QTimer, Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QFrame,
        QGridLayout,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QScrollArea,
        QSizePolicy,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

from ..login_item import install_launch_agent, is_launch_agent_installed, remove_launch_agent
from .preferences_dialog import PreferencesDialog
from .export_confirmation_dialog import ExportConfirmationDialog
from .theme import stylesheet_for_scale
from .worker import ExportWorker, ScanWorker


REFERENCE_WINDOW_SIZE = (620, 760)
MINIMUM_WINDOW_SIZE = (480, 560)
COMPACT_LAYOUT_BREAKPOINT = 560


UI_BASE_SIZES = {
    "window_min": MINIMUM_WINDOW_SIZE,
    "window_default": REFERENCE_WINDOW_SIZE,
    "window_margins": (16, 8, 16, 16),
    "window_spacing": 12,
    "header_button": 36,
    "section_spacing": 8,
    "stem_panel_margins": (14, 10, 14, 10),
    "stem_list_min_height": 140,
    "stem_row_height": 44,
    "stem_row_margins": (16, 0, 16, 0),
    "stem_row_spacing": 12,
    "stem_index_width": 30,
    "stem_checkbox_size": 28,
    "stem_status_width": 68,
    # Includes stylesheet padding and borders; keep layout rows at the rendered control height.
    "field_height": 38,
    "card_margins": (14, 10, 14, 12),
    "card_spacing": 10,
    "progress_margins": (16, 10, 16, 10),
    "progress_spacing": 8,
    "progress_header_spacing": 10,
    "progress_percent_width": 34,
    "progress_bar_height": 4,
    "progress_detail_max_height": 34,
    "progress_min_height": 90,
    "progress_max_height": 110,
    "action_margins": (0, 8, 0, 0),
    "action_spacing": 12,
    "action_height": 36,
}


def _scaled_value(value: int | tuple[int, ...], scale: float) -> int | tuple[int, ...]:
    if isinstance(value, tuple):
        return tuple(max(0, round(item * scale)) for item in value)
    return max(1, round(value * scale))


def ui_sizes_for_scale(scale: float) -> dict[str, int | tuple[int, ...]]:
    sizes = {key: _scaled_value(value, scale) for key, value in UI_BASE_SIZES.items()}
    sizes["header_button"] = max(28, int(sizes["header_button"]))
    sizes["stem_checkbox_size"] = max(28, int(sizes["stem_checkbox_size"]))
    sizes["stem_row_height"] = max(36, int(sizes["stem_row_height"]))
    sizes["field_height"] = max(34, int(sizes["field_height"]))
    sizes["action_height"] = max(32, int(sizes["action_height"]))
    return sizes


def _resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*parts)


def _app_icon() -> QIcon:
    return QIcon(str(_resource_path("assets", "logo", "stems-tower.png")))


def _sliders_icon(size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#aab2be"))
    pen.setWidthF(1.5)
    painter.setPen(pen)
    painter.setBrush(QColor("#aab2be"))
    for y, knob_x in ((4.0, 10.5), (8.0, 5.5), (12.0, 9.0)):
        painter.drawLine(QPointF(2.0, y), QPointF(size - 2.0, y))
        painter.drawEllipse(QPointF(knob_x, y), 1.7, 1.7)
    painter.end()
    return QIcon(pixmap)


def _check_icon(size: int = 12) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#69c7bc"))
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(QPointF(2.0, 6.2), QPointF(5.0, 9.0))
    painter.drawLine(QPointF(5.0, 9.0), QPointF(10.2, 3.0))
    painter.end()
    return QIcon(pixmap)


class StemTrackRow(QWidget):
    def __init__(
        self,
        track: StemTrack,
        display_index: int,
        *,
        sizes: dict[str, int | tuple[int, ...]] | None = None,
        show_separator: bool = True,
    ) -> None:
        super().__init__()
        sizes = sizes or UI_BASE_SIZES
        self.setObjectName("stemTrackRow")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        self.content = QWidget()
        self.content.setObjectName("stemTrackRowContent")
        self.content.setAttribute(Qt.WA_StyledBackground, True)

        self.row_layout = QHBoxLayout(self.content)

        self.index_label = QLabel(f"{display_index:02d}")
        self.index_label.setObjectName("stemRowIndex")
        self.index_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.name_label = QLabel(track.name)
        self.name_label.setObjectName("stemRowName")
        self.name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.checkbox = QCheckBox()
        self.checkbox.setObjectName("stemRowCheckbox")
        self.checkbox.setChecked(track.selected)
        self.checkbox.setToolTip(f"Export {track.name}")
        self.checkbox.setAccessibleName(self.checkbox.toolTip())
        self.checkbox.toggled.connect(self._sync_check_icon)
        self._sync_check_icon(track.selected)

        self.status_label = QLabel("")
        self.status_label.setObjectName("stemRowStatus")
        self.status_label.setProperty("statusState", "detected")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.hide()
        self.apply_sizes(sizes)

        self.row_layout.addWidget(self.checkbox)
        self.row_layout.addWidget(self.index_label)
        self.row_layout.addWidget(self.name_label, 1)
        self.row_layout.addWidget(self.status_label)

        separator = QFrame()
        separator.setObjectName("stemTrackRowSeparator")
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setVisible(show_separator)

        self.outer_layout.addWidget(self.content)
        self.outer_layout.addWidget(separator)

    def apply_sizes(self, sizes: dict[str, int | tuple[int, ...]]) -> None:
        row_height = int(sizes["stem_row_height"])
        self.setMinimumHeight(row_height)
        self.setMaximumHeight(row_height)
        self.content.setMinimumHeight(row_height - 1)
        self.content.setMaximumHeight(row_height - 1)
        self.row_layout.setContentsMargins(*sizes["stem_row_margins"])
        self.row_layout.setSpacing(int(sizes["stem_row_spacing"]))
        self.index_label.setFixedWidth(int(sizes["stem_index_width"]))
        checkbox_size = int(sizes["stem_checkbox_size"])
        self.checkbox.setFixedSize(checkbox_size, checkbox_size)
        self.status_label.setMinimumWidth(int(sizes["stem_status_width"]))

    def _sync_check_icon(self, checked: bool) -> None:
        self.checkbox.setText("")
        self.checkbox.setIcon(_check_icon() if checked else QIcon())
        self.checkbox.setIconSize(QSize(12, 12))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Stems")
        self.setWindowIcon(_app_icon())
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        self.preferences_store = PreferencesStore()
        self.preferences = self.preferences_store.load()
        self.ui_scale = 1.0
        self.ui_sizes = ui_sizes_for_scale(self.ui_scale)
        self.setMinimumSize(*self.ui_sizes["window_min"])
        self.resize(*self.ui_sizes["window_default"])
        self.gateway = OSCGateway()
        self.gateway.start_listener()
        self.state = AppState(AbletonClient(self.gateway))
        self.project = None
        self.current_job: ExportJob | None = None
        self.current_result: ExportResult | None = None
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.export_thread: QThread | None = None
        self.export_worker: ExportWorker | None = None
        self.item_by_track_name: dict[str, QListWidgetItem] = {}
        self.status_by_track_name: dict[str, QLabel] = {}
        self.tray_icon: QSystemTrayIcon | None = None
        self.export_cancel_requested = False
        self._ui_ready = False
        self._startup_scan = False
        self._compact_layout: bool | None = None
        self._full_project_path = "-"

        self._build_ui()
        self._ui_ready = True
        self._apply_preferences_to_ui()
        self._build_tray()
        def _auto_scan():
            self._startup_scan = True
            self.scan_current_set()

        QTimer.singleShot(0, _auto_scan)

    def _build_ui(self) -> None:
        self.setStyleSheet(stylesheet_for_scale(self.ui_scale))
        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        self.window_layout = QVBoxLayout(central)
        self.window_layout.setContentsMargins(*self.ui_sizes["window_margins"])
        self.window_layout.setSpacing(int(self.ui_sizes["window_spacing"]))

        scroll_area = QScrollArea()
        scroll_area.setObjectName("mainScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setObjectName("mainScrollContent")
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(int(self.ui_sizes["window_spacing"]))

        self.content_layout.addWidget(self._build_header_section())
        self.content_layout.addWidget(self._build_current_set_section())
        self.content_layout.addWidget(self._build_detected_stems_section())
        self.content_layout.addWidget(self._build_export_section())
        self.content_layout.addWidget(self._build_progress_section())

        scroll_area.setWidget(scroll_content)
        self.window_layout.addWidget(scroll_area, 1)
        self.action_layout = self._build_action_row()
        self.window_layout.addLayout(self.action_layout)

    def _build_header_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("appHeader")
        layout = QHBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.preferences_button = QPushButton()
        self.preferences_button.setObjectName("headerAction")
        self.preferences_button.setToolTip("Preferences")
        self.preferences_button.setAccessibleName(self.preferences_button.toolTip())
        self.preferences_button.setIcon(_sliders_icon())
        self.preferences_button.setIconSize(QSize(16, 16))
        header_button = int(self.ui_sizes["header_button"])
        self.preferences_button.setFixedSize(QSize(header_button, header_button))
        self.preferences_button.clicked.connect(self.show_preferences)

        self.app_title = QLabel("Stems")
        self.app_title.setObjectName("appTitle")
        layout.addWidget(self.app_title)
        layout.addStretch(1)
        layout.addWidget(self.preferences_button)
        return section

    def _build_current_set_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("currentSetSection")
        section.setAttribute(Qt.WA_StyledBackground, True)
        self.current_body_layout = QVBoxLayout(section)
        self.current_body_layout.setContentsMargins(*self.ui_sizes["card_margins"])
        self.current_body_layout.setSpacing(5)

        eyebrow = QLabel("CURRENT SET")
        eyebrow.setObjectName("currentSetEyebrow")

        self.song_value = QLabel("Not scanned")
        self.song_value.setObjectName("currentSetValue")
        self.song_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.song_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.bpm_value = QLabel("-")
        self.bpm_value.setObjectName("currentSetBpm")
        self.bpm_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.path_value = QLabel("-")
        self.path_value.setObjectName("currentSetPathValue")
        self.path_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.path_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.path_value.setToolTip("-")

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(12)
        summary_row.addWidget(self.song_value, 1)
        summary_row.addWidget(self.bpm_value)

        self.current_body_layout.addWidget(eyebrow)
        self.current_body_layout.addLayout(summary_row)
        self.current_body_layout.addWidget(self.path_value)

        return section

    def _build_detected_stems_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("detectedStemsSection")
        self.stems_layout = QVBoxLayout(section)
        self.stems_layout.setContentsMargins(0, 0, 0, 0)
        self.stems_layout.setSpacing(int(self.ui_sizes["section_spacing"]))

        title_label = QLabel("Stems")
        title_label.setObjectName("cardTitle")
        self.selection_count_label = QLabel("0 selected")
        self.selection_count_label.setObjectName("selectionCount")

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.selection_count_label)

        list_panel = QWidget()
        list_panel.setObjectName("stemListPanel")
        list_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.stem_panel_layout = QVBoxLayout(list_panel)
        self.stem_panel_layout.setContentsMargins(*self.ui_sizes["stem_panel_margins"])
        self.stem_panel_layout.setSpacing(0)

        self.track_list = QListWidget()
        self.track_list.setObjectName("stemTrackList")
        self.track_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.track_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.track_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.track_list.setMinimumHeight(int(self.ui_sizes["stem_list_min_height"]))
        self.stem_panel_layout.addWidget(self.track_list)

        self.stems_layout.addLayout(title_row)
        self.stems_layout.addWidget(list_panel, 1)
        return section

    def _build_export_section(self) -> QWidget:
        section, body = self._build_card("Export options")
        self.export_section = section
        self.export_options_layout = QGridLayout(body)
        self.export_options_layout.setContentsMargins(0, 0, 0, 0)
        self.export_options_layout.setHorizontalSpacing(12)
        self.export_options_layout.setVerticalSpacing(6)

        self.project_name_input = QLineEdit()
        self.project_name_input.setObjectName("exportInput")
        self.project_name_input.setPlaceholderText("Override song name")
        self.project_name_input.setMinimumHeight(int(self.ui_sizes["field_height"]))
        self.project_name_input.textChanged.connect(self.update_destination_preview)

        self.key_input = QLineEdit()
        self.key_input.setObjectName("exportInput")
        self.key_input.setPlaceholderText("Optional key, e.g. F# Minor")
        self.key_input.setMinimumHeight(int(self.ui_sizes["field_height"]))
        self.key_input.textChanged.connect(self.update_destination_preview)
        self.replace_mode = QComboBox()
        self.replace_mode.setObjectName("exportInput")
        self.replace_mode.addItem("Replace existing files", "replace")
        self.replace_mode.addItem("Skip existing files", "keep")
        self.replace_mode.setMinimumHeight(int(self.ui_sizes["field_height"]))
        self.replace_mode.currentIndexChanged.connect(self.update_destination_preview)

        self.destination_value = QLabel("-")
        self.destination_value.setObjectName("destinationPath")
        self.destination_value.setMinimumHeight(int(self.ui_sizes["field_height"]))
        self.destination_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.destination_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.choose_destination_button = QPushButton("Choose...")
        self.choose_destination_button.setObjectName("secondary")
        self.choose_destination_button.setMinimumHeight(int(self.ui_sizes["field_height"]))
        self.choose_destination_button.clicked.connect(self.choose_destination_folder)

        project_label = self._build_field_label("Project")
        project_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        key_label = self._build_field_label("Key")
        key_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        mode_label = self._build_field_label("Mode")
        mode_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        dest_label = self._build_field_label("Destination")
        dest_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.export_labels = (project_label, key_label, mode_label, dest_label)
        self.destination_control = QWidget()
        self.destination_control.setObjectName("destinationControl")
        destination_layout = QHBoxLayout(self.destination_control)
        destination_layout.setContentsMargins(0, 0, 0, 0)
        destination_layout.setSpacing(8)
        destination_layout.addWidget(self.destination_value, 1)
        destination_layout.addWidget(self.choose_destination_button)

        self.export_field_pairs = (
            (project_label, self.project_name_input),
            (key_label, self.key_input),
            (mode_label, self.replace_mode),
            (dest_label, self.destination_control),
        )
        self._arrange_export_fields(compact=False)
        return section

    def _build_progress_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("progressCard")
        section.setAttribute(Qt.WA_StyledBackground, True)
        self.progress_card = section

        self.progress_layout = QVBoxLayout(section)
        self.progress_layout.setContentsMargins(*self.ui_sizes["progress_margins"])
        self.progress_layout.setSpacing(int(self.ui_sizes["progress_spacing"]))
        section.setMinimumHeight(int(self.ui_sizes["progress_min_height"]))
        section.setMaximumHeight(int(self.ui_sizes["progress_max_height"]))

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("progressStatus")
        self.progress_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.progress_status_row = QHBoxLayout()
        self.progress_status_row.setContentsMargins(0, 0, 0, 0)
        self.progress_status_row.setSpacing(int(self.ui_sizes["progress_header_spacing"]))

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setObjectName("progressPercent")
        self.progress_percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.progress_percent_label.setMinimumWidth(int(self.ui_sizes["progress_percent_width"]))

        self.progress_status_row.addWidget(self.progress_label)
        self.progress_status_row.addStretch(1)
        self.progress_status_row.addWidget(self.progress_percent_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(int(self.ui_sizes["progress_bar_height"]))
        self.progress_bar.valueChanged.connect(self._refresh_progress_percent)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("progressDetail")
        self.summary_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.summary_label.setMaximumHeight(int(self.ui_sizes["progress_detail_max_height"]))

        self.progress_layout.addLayout(self.progress_status_row)
        self.progress_layout.addWidget(self.progress_bar)
        self.progress_layout.addWidget(self.summary_label)
        self._set_progress_state("idle")
        return section

    def _build_action_row(self) -> QGridLayout:
        actions = QGridLayout()
        actions.setContentsMargins(*self.ui_sizes["action_margins"])
        actions.setSpacing(int(self.ui_sizes["action_spacing"]))
        self.scan_button = QPushButton("Scan Current Set")
        self.scan_button.setObjectName("primaryAction")
        self.scan_button.clicked.connect(self.scan_current_set)
        self.export_button = QPushButton("Export Stems")
        self.export_button.setObjectName("secondary")
        self.export_button.setToolTip("Scan a set and select at least one stem before exporting.")
        self.export_button.clicked.connect(self.confirm_export)
        self.export_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.clicked.connect(self.cancel_export)
        self.cancel_button.setEnabled(False)
        self.cancel_button.hide()
        self.open_button = QPushButton("Open Folder")
        self.open_button.setObjectName("secondary")
        self.open_button.clicked.connect(self.open_export_folder)
        self.open_button.setEnabled(False)
        self.open_button.hide()
        self.action_buttons = (self.scan_button, self.open_button, self.cancel_button, self.export_button)
        for button in self.action_buttons:
            button.setProperty("actionBarButton", True)
            button.setMinimumHeight(int(self.ui_sizes["action_height"]))
            button.setMaximumHeight(int(self.ui_sizes["action_height"]))
        actions.addWidget(self.scan_button, 0, 0)
        actions.addWidget(self.open_button, 0, 1)
        actions.addWidget(self.cancel_button, 0, 2)
        actions.addWidget(self.export_button, 0, 3)
        actions.setColumnStretch(0, 4)
        actions.setColumnStretch(1, 3)
        actions.setColumnStretch(2, 2)
        actions.setColumnStretch(3, 3)
        self._refresh_action_hierarchy()
        return actions

    def _arrange_action_buttons(self, compact: bool) -> None:
        for button in self.action_buttons:
            self.action_layout.removeWidget(button)
        visible_buttons = [button for button in self.action_buttons if not button.isHidden()]
        if compact:
            for index, button in enumerate(visible_buttons):
                self.action_layout.addWidget(button, index // 2, index % 2)
            self.action_layout.setColumnStretch(0, 1)
            self.action_layout.setColumnStretch(1, 1)
            self.action_layout.setColumnStretch(2, 0)
            self.action_layout.setColumnStretch(3, 0)
        else:
            for column, button in enumerate(visible_buttons):
                self.action_layout.addWidget(button, 0, column)
            for column in range(4):
                self.action_layout.setColumnStretch(column, 1 if column < len(visible_buttons) else 0)

    def _arrange_export_fields(self, compact: bool) -> None:
        for label, control in self.export_field_pairs:
            self.export_options_layout.removeWidget(label)
            self.export_options_layout.removeWidget(control)
        if compact:
            for index, (label, control) in enumerate(self.export_field_pairs):
                row = index * 2
                self.export_options_layout.addWidget(label, row, 0)
                self.export_options_layout.addWidget(control, row + 1, 0)
            self.export_options_layout.setColumnStretch(0, 1)
            self.export_options_layout.setColumnStretch(1, 0)
        else:
            positions = ((0, 0), (0, 1), (2, 0), (2, 1))
            for (label, control), (row, column) in zip(self.export_field_pairs, positions):
                self.export_options_layout.addWidget(label, row, column)
                self.export_options_layout.addWidget(control, row + 1, column)
            self.export_options_layout.setColumnStretch(0, 1)
            self.export_options_layout.setColumnStretch(1, 1)

    def _set_export_enabled(self, enabled: bool) -> None:
        self.export_button.setEnabled(enabled)
        self._refresh_action_hierarchy()

    def _set_open_available(self, available: bool) -> None:
        self.open_button.setEnabled(available)
        self.open_button.setVisible(available)
        if hasattr(self, "action_layout"):
            self._arrange_action_buttons(self.width() < COMPACT_LAYOUT_BREAKPOINT)

    def _set_cancel_available(self, available: bool) -> None:
        self.cancel_button.setEnabled(available)
        self.cancel_button.setVisible(available)
        if hasattr(self, "action_layout"):
            self._arrange_action_buttons(self.width() < COMPACT_LAYOUT_BREAKPOINT)

    def _refresh_action_hierarchy(self) -> None:
        export_is_primary = self.export_button.isEnabled()
        self.scan_button.setObjectName("secondary" if export_is_primary else "primaryAction")
        self.export_button.setObjectName("primaryAction" if export_is_primary else "secondary")
        for button in (self.scan_button, self.export_button):
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _build_card(self, title: str) -> tuple[QWidget, QWidget]:
        section = QWidget()
        section.setObjectName("card")
        section.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(*self.ui_sizes["card_margins"])
        layout.setSpacing(int(self.ui_sizes["card_spacing"]))
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        body = QWidget()
        layout.addWidget(title_label)
        layout.addWidget(body)
        return section, body

    def _build_field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().resizeEvent(event)
        if not getattr(self, "_ui_ready", False):
            return
        compact = event.size().width() < COMPACT_LAYOUT_BREAKPOINT
        if compact != self._compact_layout:
            self._compact_layout = compact
            self._arrange_export_fields(compact)
            self._arrange_action_buttons(compact)
        self._refresh_elided_project_path()

    def _apply_preferences_to_ui(self) -> None:
        width = self.preferences.panel_width
        height = self.preferences.panel_height
        if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
            available = self.screen().availableGeometry()
            self.resize(
                min(max(width, MINIMUM_WINDOW_SIZE[0]), available.width()),
                min(max(height, MINIMUM_WINDOW_SIZE[1]), available.height()),
            )
        else:
            self.resize(*REFERENCE_WINDOW_SIZE)
        compact = self.width() < COMPACT_LAYOUT_BREAKPOINT
        self._compact_layout = compact
        self._arrange_export_fields(compact)
        self._arrange_action_buttons(compact)
        index = 0 if self.preferences.replace_mode == "replace" else 1
        self.replace_mode.setCurrentIndex(index)
        if self.preferences.sticky_panel_position and self.preferences.panel_x is not None and self.preferences.panel_y is not None:
            self.move(self.preferences.panel_x, self.preferences.panel_y)

    def _set_project_path(self, path: str) -> None:
        self._full_project_path = path
        self.path_value.setToolTip(path)
        self._refresh_elided_project_path()

    def _refresh_elided_project_path(self) -> None:
        if not hasattr(self, "path_value"):
            return
        available_width = max(80, self.path_value.width())
        self.path_value.setText(
            self.path_value.fontMetrics().elidedText(
                self._full_project_path,
                Qt.ElideMiddle,
                available_width,
            )
        )

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        if not self.windowIcon().isNull():
            self.tray_icon.setIcon(self.windowIcon())
        self.tray_icon.setToolTip("Stems")
        menu = QMenu(self)
        show_action = menu.addAction("Show Panel")
        show_action.triggered.connect(self.showNormal)
        scan_action = menu.addAction("Scan Current Set")
        scan_action.triggered.connect(self.scan_current_set)
        preferences_action = menu.addAction("Preferences")
        preferences_action.triggered.connect(self.show_preferences)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._toggle_from_tray)
        self.tray_icon.show()

    def _toggle_from_tray(self, reason) -> None:
        if reason != QSystemTrayIcon.Trigger:
            return
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def scan_current_set(self) -> None:
        if self.scan_thread is not None:
            return
        self.scan_button.setEnabled(False)
        self._set_export_enabled(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("scanning")
        self.progress_label.setText("Scanning Ableton set")
        self._set_progress_detail("Looking up song, tempo, project, and stem tracks")

        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(self.state)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.finished.connect(self._handle_scan_success)
        self.scan_worker.failed.connect(self._handle_scan_failure)
        self.scan_worker.finished.connect(self._cleanup_scan_thread)
        self.scan_worker.failed.connect(self._cleanup_scan_thread)
        self.scan_thread.start()

    def _handle_scan_success(self, state, project) -> None:
        self.state = state
        self.project = project
        self.song_value.setText(project.song_name)
        self.project_name_input.setPlaceholderText(project.song_name)
        self.bpm_value.setText(f"{project.bpm} BPM" if project.bpm is not None else "BPM unknown")
        self._set_project_path(str(project.project_folder))
        self._populate_tracks(state.detected_tracks)
        self.update_destination_preview()
        count = len(state.detected_tracks)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_label.setText("Scan complete")
        self._set_progress_detail(f"Detected {count} stem{'s' if count != 1 else ''}")
        self._set_progress_state("idle")
        self._set_export_enabled(count > 0)
        self._set_open_available(self.current_job is not None or self.project is not None)

    def _handle_scan_failure(self, message: str) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("scan-failed")
        self.progress_label.setText("Scan failed")
        self._set_progress_detail(message)
        if not self._startup_scan:
            QMessageBox.warning(self, "Scan failed", message)
        self._startup_scan = False

    def _cleanup_scan_thread(self, *_args) -> None:
        if self.scan_thread is not None:
            self.scan_thread.quit()
            self.scan_thread.wait()
        self.scan_thread = None
        self.scan_worker = None
        self.scan_button.setEnabled(True)

    def _populate_tracks(self, tracks: list[StemTrack]) -> None:
        self.track_list.clear()
        self.item_by_track_name.clear()
        self.status_by_track_name.clear()
        for display_index, track in enumerate(tracks, start=1):
            item = QListWidgetItem(self.track_list)
            item.setSizeHint(QSize(0, int(self.ui_sizes["stem_row_height"])))
            row = StemTrackRow(
                track,
                display_index,
                sizes=self.ui_sizes,
                show_separator=display_index < len(tracks),
            )
            row.checkbox.toggled.connect(self._handle_track_selection_changed)
            self.track_list.setItemWidget(item, row)
            self.item_by_track_name[track.name] = item
            self.status_by_track_name[track.name] = row.status_label
        row_height = int(self.ui_sizes["stem_row_height"])
        list_height = max(int(self.ui_sizes["stem_list_min_height"]), len(tracks) * row_height + 2)
        self.track_list.setFixedHeight(list_height)
        self._refresh_selection_count()

    def _handle_track_selection_changed(self, *_args) -> None:
        self._refresh_selection_count()
        self.update_destination_preview()

    def _refresh_selection_count(self) -> None:
        selected = len(self._selected_tracks())
        self.selection_count_label.setText(f"{selected} selected")

    def _selected_tracks(self) -> list[StemTrack]:
        if self.state is None:
            return []
        selected: list[StemTrack] = []
        for track in self.state.detected_tracks:
            item = self.item_by_track_name.get(track.name)
            if item is None:
                continue
            row = self.track_list.itemWidget(item)
            checkbox = row.findChild(QCheckBox)
            if checkbox is not None and checkbox.isChecked():
                selected.append(replace(track, selected=True))
        return selected

    def update_destination_preview(self) -> None:
        if self.state is None or self.project is None:
            self.destination_value.setText("-")
            self._set_open_available(False)
            return
        tracks = self._selected_tracks()
        custom_song_name = self.project_name_input.text().strip() or None
        key = self.key_input.text().strip() or None
        replace_mode = self.replace_mode.currentData()
        destination_root = (self.preferences.export_destination_root or "").strip() or None
        job = self.state.build_export_job(
            key=key,
            replace_mode=replace_mode,
            destination_root=destination_root,
            custom_song_name=custom_song_name,
            stem_name_format=self.preferences.stem_name_format,
            folder_name_format=self.preferences.folder_name_format,
        )
        self.current_job = replace(job, tracks=tracks)
        self.destination_value.setText(self.current_job.stems_dir.name or "-")
        self._set_export_enabled(bool(self.current_job.selected_tracks))
        self._set_open_available(True)

    def choose_destination_folder(self) -> None:
        start_dir = (
            (self.preferences.export_destination_root or "").strip()
            or (str(self.project.project_folder) if self.project is not None else str(Path.home()))
        )
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Export Destination",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not selected:
            return
        self.preferences.export_destination_root = selected
        self.preferences_store.save(self.preferences)
        self.update_destination_preview()

    def show_preferences(self) -> None:
        dialog = PreferencesDialog(self.preferences, self)
        dialog.preferences_changed.connect(self._save_preferences_from_dialog)
        dialog.open_export_folder_requested.connect(self.open_export_folder)
        dialog.exec()
        if self.preferences.menubar_mode:
            self.hide()
        else:
            self.showNormal()

    def _save_preferences_from_dialog(self, updated: Preferences) -> None:
        launch_setting_changed = updated.launch_at_login != self.preferences.launch_at_login
        self.preferences = updated
        if launch_setting_changed:
            if self.preferences.launch_at_login:
                install_launch_agent(Path(__file__).resolve().parents[2] / "run_ui.py")
            else:
                remove_launch_agent()
        self.preferences_store.save(self.preferences)
        self._apply_preferences_to_ui()

    def confirm_export(self) -> None:
        self.update_destination_preview()
        if self.current_job is None or not self.current_job.selected_tracks:
            QMessageBox.information(self, "No stems selected", "Select at least one stem to export.")
            return

        confirm = ExportConfirmationDialog(self.current_job, self, scale=self.ui_scale)
        if confirm.exec() == QDialog.Accepted:
            self.start_export()

    def start_export(self) -> None:
        if self.current_job is None or self.export_thread is not None:
            return

        self.export_cancel_requested = False
        self.progress_bar.setRange(0, len(self.current_job.selected_tracks) or 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("export-starting")
        self.progress_label.setText("Preparing export")
        self._set_export_progress_detail(completed=0)
        self.scan_button.setEnabled(False)
        self._set_export_enabled(False)
        self._set_cancel_available(True)

        self.export_thread = QThread(self)
        self.export_worker = ExportWorker(self.state, self.current_job)
        self.export_worker.moveToThread(self.export_thread)
        self.export_thread.started.connect(self.export_worker.run)
        self.export_worker.progress.connect(self._handle_export_progress)
        self.export_worker.finished.connect(self._handle_export_finished)
        self.export_worker.failed.connect(self._handle_export_failed)
        self.export_worker.finished.connect(self._cleanup_export_thread)
        self.export_worker.failed.connect(self._cleanup_export_thread)
        self.export_thread.start()

    def _handle_export_progress(self, event: str, message: str) -> None:
        if event == "preflight":
            self._set_progress_state("export-starting")
            self.progress_label.setText("Preparing export")
        elif event == "cancelled":
            self._set_progress_state("cancelled")
            self.progress_label.setText("Export cancelled")
        else:
            self._set_progress_state("export-in-progress")
        if event == "stem":
            parts, _, track_name = message.partition(" ")
            current_index = int(parts.split("/")[0])
            self.progress_bar.setValue(current_index - 1)
            self.progress_label.setText(f"Exporting {track_name}")
            label = self.status_by_track_name.get(track_name)
            if label is not None:
                self._set_track_status(label, "exporting")
        elif event in {"success", "skipped", "failed"}:
            self.progress_bar.setValue(min(self.progress_bar.value() + 1, self.progress_bar.maximum()))
            if event == "success":
                track_name = message.replace("Exported ", "", 1)
            elif event == "skipped":
                track_name = message.replace("Skipped ", "", 1)
            else:
                track_name = message.split(":", 1)[0]
            label = self.status_by_track_name.get(track_name)
            if label is not None:
                self._set_track_status(label, event)
        self._set_export_progress_detail()

    def _set_track_status(self, label: QLabel, status: str) -> None:
        label.setText(
            {
                "exporting": "Exporting",
                "success": "Exported",
                "skipped": "Skipped",
                "failed": "Failed",
            }.get(status, status.title())
        )
        label.setProperty("statusState", status)
        label.show()
        label.style().unpolish(label)
        label.style().polish(label)

    def _set_progress_state(self, status: str) -> None:
        for widget in (
            self.progress_card,
            self.progress_label,
            self.progress_percent_label,
            self.progress_bar,
            self.summary_label,
        ):
            widget.setProperty("progressState", status)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        show_meter = status in {"export-starting", "export-in-progress", "cancelling", "cancelled"}
        self.progress_card.setVisible(status != "idle")
        self.progress_bar.setVisible(show_meter)
        self.progress_percent_label.setVisible(show_meter)
        self._refresh_progress_percent()

    def _set_progress_detail(self, text: str) -> None:
        self.summary_label.setText(text)
        self.summary_label.setToolTip(text)

    def _set_export_progress_detail(self, *, completed: int | None = None) -> None:
        if self.current_job is None:
            return
        total = len(self.current_job.selected_tracks)
        completed_count = self.progress_bar.value() if completed is None else completed
        stem_word = "stem" if total == 1 else "stems"
        self._set_progress_detail(
            f"{completed_count} of {total} {stem_word} · Saving to {self.current_job.stems_dir}"
        )

    def _refresh_progress_percent(self, *_args) -> None:
        maximum = self.progress_bar.maximum()
        minimum = self.progress_bar.minimum()
        span = maximum - minimum
        if span <= 0:
            percent = 0
        else:
            percent = round(((self.progress_bar.value() - minimum) / span) * 100)
        self.progress_percent_label.setText(f"{max(0, min(percent, 100))}%")

    def _handle_export_finished(self, result: ExportResult) -> None:
        self.current_result = result
        failures = [item.track.name for item in result.items if item.status == "failed"]
        total = len(result.job.selected_tracks)
        summary = f"Exported {result.success_count}/{total} stems to {result.job.stems_dir}."
        if failures:
            summary += f" Failed: {', '.join(failures)}."
        if self.export_cancel_requested:
            self._set_progress_state("cancelled")
            self.progress_label.setText("Export cancelled")
            summary = f"Cancelled after exporting {result.success_count}/{total} stems to {result.job.stems_dir}."
            if failures:
                summary += f" Failed before cancellation: {', '.join(failures)}."
        else:
            self.progress_bar.setValue(self.progress_bar.maximum())
            self._set_progress_state("export-complete")
            self.progress_label.setText("Export complete")
        self._set_progress_detail(summary)
        self._set_open_available(True)
        full_summary = build_export_summary(result)
        self.preferences = append_recent_export(
            self.preferences,
            RecentExport(
                song_name=result.job.song_name,
                stems_dir=str(result.job.stems_dir),
                exported_count=result.success_count,
                failed_count=result.failure_count,
                summary=full_summary,
            ),
        )
        self.preferences_store.save(self.preferences)
        if self.preferences.copy_summary_to_clipboard:
            self.copy_summary(notify=False)
        if self.preferences.auto_open_folder:
            self.open_export_folder()

    def _handle_export_failed(self, message: str) -> None:
        self._set_progress_state("export-failed")
        self.progress_label.setText("Export failed")
        self._set_progress_detail(message)
        QMessageBox.warning(self, "Export failed", message)

    def _cleanup_export_thread(self, *_args) -> None:
        if self.export_thread is not None:
            self.export_thread.quit()
            self.export_thread.wait()
        self.export_thread = None
        self.export_worker = None
        self.scan_button.setEnabled(True)
        self._set_cancel_available(False)
        self.update_destination_preview()

    def copy_summary(self, *, notify: bool = True) -> None:
        if self.current_result is None:
            return
        summary = build_export_summary(self.current_result)
        clipboard = self.window().windowHandle().screen().context().clipboard() if False else None
        del clipboard
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(summary)
        if notify:
            self.summary_label.setText("Export summary copied to clipboard.")

    def cancel_export(self) -> None:
        if self.export_worker is None:
            return
        self.export_cancel_requested = True
        self.export_worker.cancel()
        self._set_progress_state("cancelling")
        self.progress_label.setText("Cancelling after current stem")
        self._set_export_progress_detail()

    def open_export_folder(self) -> None:
        if self.current_job is not None:
            path = self.current_job.stems_dir
        elif self.preferences.recent_exports:
            path = Path(self.preferences.recent_exports[0].stems_dir)
        elif (self.preferences.export_destination_root or "").strip():
            path = Path(self.preferences.export_destination_root)
        elif self.project is not None:
            path = self.project.project_folder
        else:
            return
        subprocess.run(["open", str(path)], check=False)

    def closeEvent(self, event) -> None:
        if self.preferences.sticky_panel_position:
            self.preferences.panel_x = self.x()
            self.preferences.panel_y = self.y()
        self.preferences.panel_width = self.width()
        self.preferences.panel_height = self.height()
        self.preferences.launch_at_login = is_launch_agent_installed()
        self.preferences_store.save(self.preferences)
        if self.preferences.menubar_mode and self.tray_icon is not None and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            return
        self.gateway.stop_listener()
        super().closeEvent(event)
