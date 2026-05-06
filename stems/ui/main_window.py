from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from ..ableton import AbletonClient
from ..models import ExportJob, ExportResult, StemTrack
from ..osc import OSCGateway
from ..preferences import PreferencesStore, RecentExport, append_recent_export
from ..reporting import build_export_summary
from ..state import AppState

try:
    from PySide6.QtCore import QSize, QThread, QTimer, Qt
    from PySide6.QtGui import QColor, QIcon
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGraphicsDropShadowEffect,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QFrame,
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
from .theme import DARK_STYLESHEET
from .worker import ExportWorker, ScanWorker


def _resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*parts)


def _app_icon() -> QIcon:
    return QIcon(str(_resource_path("assets", "logo", "stems-tower.png")))


class StemTrackRow(QWidget):
    ROW_HEIGHT = 64

    def __init__(self, track: StemTrack, display_index: int, *, show_separator: bool = True) -> None:
        super().__init__()
        self.setObjectName("stemTrackRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(self.ROW_HEIGHT)
        self.setMaximumHeight(self.ROW_HEIGHT)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("stemTrackRowContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        content.setMinimumHeight(self.ROW_HEIGHT - 1)
        content.setMaximumHeight(self.ROW_HEIGHT - 1)

        row_layout = QHBoxLayout(content)
        row_layout.setContentsMargins(24, 0, 24, 0)
        row_layout.setSpacing(18)

        self.index_label = QLabel(str(display_index))
        self.index_label.setObjectName("stemRowIndex")
        self.index_label.setFixedWidth(40)
        self.index_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.name_label = QLabel(track.name)
        self.name_label.setObjectName("stemRowName")
        self.name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.checkbox = QCheckBox()
        self.checkbox.setObjectName("stemRowCheckbox")
        self.checkbox.setChecked(track.selected)
        self.checkbox.setToolTip(f"Export {track.name}")
        self.checkbox.setFixedSize(22, 22)
        self.checkbox.toggled.connect(self._sync_check_icon)
        self._sync_check_icon(track.selected)

        self.status_label = QLabel("Detected")
        self.status_label.setObjectName("stemRowStatus")
        self.status_label.setProperty("statusState", "detected")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.setMinimumWidth(88)

        row_layout.addWidget(self.index_label)
        row_layout.addWidget(self.name_label, 1)
        row_layout.addWidget(self.status_label)
        row_layout.addWidget(self.checkbox)

        separator = QFrame()
        separator.setObjectName("stemTrackRowSeparator")
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setVisible(show_separator)

        outer_layout.addWidget(content)
        outer_layout.addWidget(separator)

    def _sync_check_icon(self, checked: bool) -> None:
        self.checkbox.setText("✓" if checked else "")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Stems")
        self.setWindowIcon(_app_icon())
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(640, 820)
        self.resize(700, 860)

        self.preferences_store = PreferencesStore()
        self.preferences = self.preferences_store.load()
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

        self._build_ui()
        self._apply_preferences_to_ui()
        self._build_tray()
        QTimer.singleShot(0, self.scan_current_set)

    def _build_ui(self) -> None:
        self.setStyleSheet(DARK_STYLESHEET)
        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 10, 24, 24)
        layout.setSpacing(16)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("mainScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setObjectName("mainScrollContent")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        content_layout.addWidget(self._build_header_section())
        content_layout.addWidget(self._build_current_set_section())
        content_layout.addWidget(self._build_detected_stems_section(), 1)
        content_layout.addWidget(self._build_export_section())
        content_layout.addWidget(self._build_progress_section())

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)
        layout.addLayout(self._build_action_row())

    def _build_header_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("appHeader")
        layout = QHBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.preferences_button = QPushButton("⚙")
        self.preferences_button.setObjectName("headerAction")
        self.preferences_button.setToolTip("Preferences")
        self.preferences_button.setFixedSize(QSize(28, 28))
        self.preferences_button.clicked.connect(self.show_preferences)

        layout.addStretch(1)
        layout.addWidget(self.preferences_button)
        return section

    def _build_current_set_section(self) -> QWidget:
        section, body = self._build_card("Current Set")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        self.song_value = QLabel("Not scanned")
        self.song_value.setObjectName("currentSetValue")
        self.song_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.song_value.setWordWrap(True)
        self.song_value.setMinimumHeight(22)
        self.song_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.bpm_value = QLabel("-")
        self.bpm_value.setObjectName("currentSetValue")
        self.bpm_value.setMinimumHeight(22)
        self.bpm_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.path_value = QLabel("-")
        self.path_value.setObjectName("currentSetPathValue")
        self.path_value.setWordWrap(True)
        self.path_value.setMinimumHeight(22)
        self.path_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.path_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        song_label = QLabel("Song")
        song_label.setObjectName("currentSetLabel")
        bpm_label = QLabel("BPM")
        bpm_label.setObjectName("currentSetLabel")
        proj_label = QLabel("Project")
        proj_label.setObjectName("currentSetLabel")

        label_width = 80
        for label in (song_label, bpm_label, proj_label):
            label.setFixedWidth(label_width)
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        for label, value in (
            (song_label, self.song_value),
            (bpm_label, self.bpm_value),
            (proj_label, self.path_value),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(28)
            row.addWidget(label)
            row.addWidget(value, 1)
            body_layout.addLayout(row)

        return section

    def _build_detected_stems_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("detectedStemsSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title_label = QLabel("Detected Stems (List View)")
        title_label.setObjectName("cardTitle")

        list_panel = QWidget()
        list_panel.setObjectName("stemListPanel")
        list_panel.setAttribute(Qt.WA_StyledBackground, True)
        panel_layout = QVBoxLayout(list_panel)
        panel_layout.setContentsMargins(22, 16, 22, 16)
        panel_layout.setSpacing(0)

        self.track_list = QListWidget()
        self.track_list.setObjectName("stemTrackList")
        self.track_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.track_list.setMinimumHeight(198)
        panel_layout.addWidget(self.track_list)

        layout.addWidget(title_label)
        layout.addWidget(list_panel, 1)
        return section

    def _build_export_section(self) -> QWidget:
        section, body = self._build_card("Export")
        section.setMinimumHeight(230)
        options_layout = QVBoxLayout(body)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(14)

        self.key_input = QLineEdit()
        self.key_input.setObjectName("exportInput")
        self.key_input.setPlaceholderText("Optional key, e.g. F# Minor")
        self.key_input.setMinimumHeight(36)
        self.key_input.textChanged.connect(self.update_destination_preview)
        self.replace_mode = QComboBox()
        self.replace_mode.setObjectName("exportInput")
        self.replace_mode.addItem("Replace existing files", "replace")
        self.replace_mode.addItem("Skip existing files", "keep")
        self.replace_mode.setMinimumHeight(36)
        self.replace_mode.currentIndexChanged.connect(self.update_destination_preview)

        self.destination_value = QLabel("-")
        self.destination_value.setObjectName("destinationPath")
        self.destination_value.setMinimumHeight(36)
        self.destination_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.destination_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.choose_destination_button = QPushButton("Choose...")
        self.choose_destination_button.setObjectName("secondary")
        self.choose_destination_button.setMinimumHeight(36)
        self.choose_destination_button.clicked.connect(self.choose_destination_folder)

        key_label = self._build_field_label("Key")
        key_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        mode_label = self._build_field_label("Mode")
        mode_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        dest_label = self._build_field_label("Destination")
        dest_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        label_width = 98
        for label in (key_label, mode_label, dest_label):
            label.setFixedWidth(label_width)

        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.setSpacing(18)
        key_row.addWidget(key_label)
        key_row.addWidget(self.key_input, 1)

        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(18)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.replace_mode, 1)

        destination_row = QHBoxLayout()
        destination_row.setContentsMargins(0, 0, 0, 0)
        destination_row.setSpacing(18)
        destination_row.addWidget(dest_label)
        destination_row.addWidget(self.destination_value, 1)
        destination_row.addWidget(self.choose_destination_button)

        options_layout.addLayout(key_row)
        options_layout.addLayout(mode_row)
        options_layout.addLayout(destination_row)
        return section

    def _build_progress_section(self) -> QWidget:
        section = QWidget()
        section.setObjectName("progressCard")
        section.setAttribute(Qt.WA_StyledBackground, True)
        self._apply_panel_shadow(section)
        self.progress_card = section

        progress_layout = QVBoxLayout(section)
        progress_layout.setContentsMargins(20, 16, 20, 16)
        progress_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        title_label = QLabel("Progress")
        title_label.setObjectName("progressTitle")
        self.progress_label = QLabel("Idle")
        self.progress_label.setObjectName("progressStatePill")
        self.progress_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.progress_label.setMinimumWidth(96)

        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        self.progress_status_module = QWidget()
        self.progress_status_module.setObjectName("progressStatusModule")
        self.progress_status_module.setAttribute(Qt.WA_StyledBackground, True)

        module_layout = QVBoxLayout(self.progress_status_module)
        module_layout.setContentsMargins(22, 18, 22, 18)
        module_layout.setSpacing(12)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(10)

        self.progress_icon_label = QLabel("i")
        self.progress_icon_label.setObjectName("progressStatusIcon")
        self.progress_icon_label.setAlignment(Qt.AlignCenter)
        self.progress_icon_label.setFixedSize(QSize(26, 26))

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setObjectName("progressPercent")
        self.progress_percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.progress_percent_label.setMinimumWidth(44)

        status_row.addWidget(self.progress_icon_label)
        status_row.addWidget(self.progress_label)
        status_row.addStretch(1)
        status_row.addWidget(self.progress_percent_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.valueChanged.connect(self._refresh_progress_percent)

        self.progress_summary_area = QScrollArea()
        self.progress_summary_area.setObjectName("progressSummaryArea")
        self.progress_summary_area.setWidgetResizable(True)
        self.progress_summary_area.setFrameShape(QFrame.NoFrame)
        self.progress_summary_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.progress_summary_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.progress_summary_area.setMinimumHeight(44)
        self.progress_summary_area.setMaximumHeight(82)

        summary_body = QWidget()
        summary_body.setObjectName("progressSummaryBody")
        summary_layout = QVBoxLayout(summary_body)
        summary_layout.setContentsMargins(0, 2, 0, 0)
        summary_layout.setSpacing(0)

        self.summary_label = QLabel("Scan the current set to begin.")
        self.summary_label.setObjectName("progressSummary")
        self.summary_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        summary_layout.addWidget(self.summary_label)
        self.progress_summary_area.setWidget(summary_body)

        module_layout.addLayout(status_row)
        module_layout.addWidget(self.progress_bar)
        module_layout.addWidget(self.progress_summary_area)

        progress_layout.addLayout(header_layout)
        progress_layout.addWidget(self.progress_status_module)
        self._set_progress_state("idle")
        return section

    def _build_action_row(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 10, 0, 0)
        actions.setSpacing(22)
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
        self.open_button = QPushButton("Open Folder")
        self.open_button.setObjectName("secondary")
        self.open_button.clicked.connect(self.open_export_folder)
        self.open_button.setEnabled(False)
        for button in (self.scan_button, self.open_button, self.cancel_button, self.export_button):
            button.setProperty("actionBarButton", True)
            button.setMinimumHeight(38)
            button.setMaximumHeight(38)
        actions.addWidget(self.scan_button, 1)
        actions.addWidget(self.open_button, 1)
        actions.addWidget(self.cancel_button, 1)
        actions.addWidget(self.export_button, 1)
        return actions

    def _build_card(self, title: str) -> tuple[QWidget, QWidget]:
        section = QWidget()
        section.setObjectName("card")
        section.setAttribute(Qt.WA_StyledBackground, True)
        self._apply_panel_shadow(section)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(14)

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

    def _apply_panel_shadow(self, widget: QWidget) -> None:
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 58))
        widget.setGraphicsEffect(shadow)

    def _apply_preferences_to_ui(self) -> None:
        self.key_input.setText(self.preferences.default_key)
        index = 0 if self.preferences.replace_mode == "replace" else 1
        self.replace_mode.setCurrentIndex(index)
        if self.preferences.sticky_panel_position and self.preferences.panel_x is not None and self.preferences.panel_y is not None:
            self.move(self.preferences.panel_x, self.preferences.panel_y)

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
        self.export_button.setEnabled(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("scanning")
        self.progress_label.setText("Scanning Ableton set...")
        self.summary_label.setText("Looking up current song, BPM, project path, and stem tracks.")

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
        self.bpm_value.setText(str(project.bpm) if project.bpm is not None else "Unknown")
        self.path_value.setText(str(project.project_folder))
        self._populate_tracks(state.detected_tracks)
        self.update_destination_preview()
        count = len(state.detected_tracks)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self._set_progress_state("idle")
        self.progress_label.setText("Scan complete")
        self.summary_label.setText(f"Detected {count} stem{'s' if count != 1 else ''}.")
        self.export_button.setEnabled(count > 0)
        self.open_button.setEnabled(self.current_job is not None or self.project is not None)

    def _handle_scan_failure(self, message: str) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("scan-failed")
        self.progress_label.setText("Scan failed")
        self.summary_label.setText(message)
        QMessageBox.warning(self, "Scan failed", message)

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
            item.setSizeHint(QSize(0, StemTrackRow.ROW_HEIGHT))
            row = StemTrackRow(track, display_index, show_separator=display_index < len(tracks))
            row.checkbox.toggled.connect(self.update_destination_preview)
            self.track_list.setItemWidget(item, row)
            self.item_by_track_name[track.name] = item
            self.status_by_track_name[track.name] = row.status_label

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
            return
        tracks = self._selected_tracks()
        key = self.key_input.text().strip() or None
        replace_mode = self.replace_mode.currentData()
        destination_root = (self.preferences.export_destination_root or "").strip() or None
        job = self.state.build_export_job(
            key=key,
            replace_mode=replace_mode,
            destination_root=destination_root,
        )
        self.current_job = replace(job, tracks=tracks)
        self.destination_value.setText(self.current_job.stems_dir.name or "-")
        self.export_button.setEnabled(bool(self.current_job.selected_tracks))
        self.open_button.setEnabled(True)

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
        if dialog.exec() == dialog.Accepted:
            self.preferences = dialog.to_preferences()
            self.preferences.launch_at_login = dialog.launch_at_login.isChecked()
            if self.preferences.launch_at_login:
                install_launch_agent(Path(__file__).resolve().parents[2] / "run_ui.py")
            else:
                remove_launch_agent()
            self.preferences_store.save(self.preferences)
            self._apply_preferences_to_ui()
            if self.preferences.menubar_mode:
                self.hide()
            else:
                self.showNormal()

    def confirm_export(self) -> None:
        self.update_destination_preview()
        if self.current_job is None or not self.current_job.selected_tracks:
            QMessageBox.information(self, "No stems selected", "Select at least one stem to export.")
            return

        preview_names = ", ".join(track.name for track in self.current_job.selected_tracks)
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirm Export")
        confirm.setText("These are the stems to export")
        confirm.setInformativeText(
            f"Count: {len(self.current_job.selected_tracks)}\n"
            f"Destination: {self.current_job.stems_dir}\n"
            f"Mode: {self.current_job.replace_mode}\n"
            f"Tracks: {preview_names}"
        )
        cancel_button = confirm.addButton("Cancel", QMessageBox.RejectRole)
        boom_button = confirm.addButton("Boom", QMessageBox.AcceptRole)
        confirm.setDefaultButton(boom_button)
        confirm.exec()
        if confirm.clickedButton() is cancel_button:
            return
        self.start_export()

    def start_export(self) -> None:
        if self.current_job is None or self.export_thread is not None:
            return

        self.export_cancel_requested = False
        self.progress_bar.setRange(0, len(self.current_job.selected_tracks) or 1)
        self.progress_bar.setValue(0)
        self._set_progress_state("export-starting")
        self.progress_label.setText("Starting export...")
        self.summary_label.setText("Preparing per-stem export.")
        self.scan_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

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
        elif event == "cancelled":
            self._set_progress_state("cancelled")
        else:
            self._set_progress_state("export-in-progress")
        self.progress_label.setText(message)
        if event == "stem":
            parts = message.split(" ", 1)[0]
            current_index = int(parts.split("/")[0])
            self.progress_bar.setValue(current_index - 1)
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
        elif event == "cancelled":
            self.summary_label.setText("Export cancelled before the next stem.")

    def _set_track_status(self, label: QLabel, status: str) -> None:
        label.setText(status.title())
        label.setProperty("statusState", status)
        label.style().unpolish(label)
        label.style().polish(label)

    def _set_progress_state(self, status: str) -> None:
        for widget in (
            self.progress_card,
            self.progress_status_module,
            self.progress_icon_label,
            self.progress_label,
            self.progress_percent_label,
            self.progress_bar,
            self.progress_summary_area,
            self.summary_label,
        ):
            widget.setProperty("progressState", status)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        self.progress_icon_label.setText(self._progress_icon_for_state(status))
        self._refresh_progress_percent()

    def _progress_icon_for_state(self, status: str) -> str:
        if status in {"scan-failed", "export-failed"}:
            return "!"
        if status in {"export-complete"}:
            return "OK"
        if status in {"scanning", "export-starting", "export-in-progress"}:
            return ">"
        if status in {"cancelling", "cancelled"}:
            return "-"
        return "i"

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
        self.summary_label.setText(summary)
        self.open_button.setEnabled(True)
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
        self.summary_label.setText(message)
        QMessageBox.warning(self, "Export failed", message)

    def _cleanup_export_thread(self, *_args) -> None:
        if self.export_thread is not None:
            self.export_thread.quit()
            self.export_thread.wait()
        self.export_thread = None
        self.export_worker = None
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
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
        self.progress_label.setText("Cancelling after current stem...")
        self.summary_label.setText("Safe cancel requested.")

    def open_export_folder(self) -> None:
        if self.current_job is not None:
            path = self.current_job.stems_dir
        elif self.project is not None:
            path = self.project.project_folder
        else:
            return
        subprocess.run(["open", str(path)], check=False)

    def closeEvent(self, event) -> None:
        if self.preferences.sticky_panel_position:
            self.preferences.panel_x = self.x()
            self.preferences.panel_y = self.y()
        self.preferences.launch_at_login = is_launch_agent_installed()
        self.preferences_store.save(self.preferences)
        if self.preferences.menubar_mode and self.tray_icon is not None and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            return
        self.gateway.stop_listener()
        super().closeEvent(event)
