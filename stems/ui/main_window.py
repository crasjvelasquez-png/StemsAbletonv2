from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

from ..ableton import AbletonClient
from ..models import ExportJob, ExportResult, StemTrack
from ..osc import OSCGateway
from ..preferences import Preferences, PreferencesStore, RecentExport, append_recent_export
from ..reporting import build_export_summary
from ..state import AppState

try:
    from PySide6.QtCore import QThread, QTimer, Qt
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QCheckBox,
        QComboBox,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QSystemTrayIcon,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc

from ..login_item import install_launch_agent, is_launch_agent_installed, remove_launch_agent
from .preferences_dialog import PreferencesDialog
from .worker import ExportWorker, ScanWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Stems")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(460)

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

        self._build_ui()
        self._apply_preferences_to_ui()
        self._build_tray()
        QTimer.singleShot(0, self.scan_current_set)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QGroupBox("Current Set")
        header_layout = QGridLayout(header)
        header_layout.setHorizontalSpacing(10)
        header_layout.setVerticalSpacing(6)
        self.song_value = QLabel("Not scanned")
        self.song_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.bpm_value = QLabel("-")
        self.path_value = QLabel("-")
        self.path_value.setWordWrap(True)
        self.path_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        header_layout.addWidget(QLabel("Song"), 0, 0)
        header_layout.addWidget(self.song_value, 0, 1)
        header_layout.addWidget(QLabel("BPM"), 1, 0)
        header_layout.addWidget(self.bpm_value, 1, 1)
        header_layout.addWidget(QLabel("Project"), 2, 0)
        header_layout.addWidget(self.path_value, 2, 1)
        layout.addWidget(header)

        track_box = QGroupBox("Detected Stems")
        track_layout = QVBoxLayout(track_box)
        track_layout.setSpacing(8)
        self.track_list = QListWidget()
        self.track_list.setSelectionMode(QAbstractItemView.NoSelection)
        track_layout.addWidget(self.track_list)
        layout.addWidget(track_box)

        options_box = QGroupBox("Export")
        options_layout = QGridLayout(options_box)
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Optional key, e.g. F# Minor")
        self.key_input.textChanged.connect(self.update_destination_preview)
        self.replace_mode = QComboBox()
        self.replace_mode.addItem("Replace existing files", "replace")
        self.replace_mode.addItem("Skip existing files", "keep")
        self.replace_mode.currentIndexChanged.connect(self.update_destination_preview)
        self.destination_value = QLabel("-")
        self.destination_value.setWordWrap(True)
        self.destination_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        options_layout.addWidget(QLabel("Key"), 0, 0)
        options_layout.addWidget(self.key_input, 0, 1)
        options_layout.addWidget(QLabel("Mode"), 1, 0)
        options_layout.addWidget(self.replace_mode, 1, 1)
        options_layout.addWidget(QLabel("Destination"), 2, 0)
        options_layout.addWidget(self.destination_value, 2, 1)
        layout.addWidget(options_box)

        recent_box = QGroupBox("Recent Exports")
        recent_layout = QVBoxLayout(recent_box)
        self.recent_exports = QListWidget()
        self.recent_exports.itemDoubleClicked.connect(self._open_recent_export)
        self.copy_summary_button = QPushButton("Copy Summary")
        self.copy_summary_button.clicked.connect(self.copy_summary)
        self.copy_summary_button.setEnabled(False)
        recent_layout.addWidget(self.recent_exports)
        recent_layout.addWidget(self.copy_summary_button)
        layout.addWidget(recent_box)

        progress_box = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_box)
        self.progress_label = QLabel("Idle")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.summary_label = QLabel("Scan the current set to begin.")
        self.summary_label.setWordWrap(True)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.summary_label)
        layout.addWidget(progress_box)

        actions = QHBoxLayout()
        self.scan_button = QPushButton("Scan Current Set")
        self.scan_button.clicked.connect(self.scan_current_set)
        self.export_button = QPushButton("Export Stems")
        self.export_button.clicked.connect(self.confirm_export)
        self.export_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_export)
        self.cancel_button.setEnabled(False)
        self.open_button = QPushButton("Open Folder")
        self.open_button.clicked.connect(self.open_export_folder)
        self.open_button.setEnabled(False)
        self.preferences_button = QPushButton("Preferences")
        self.preferences_button.clicked.connect(self.show_preferences)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.preferences_button)
        actions.addStretch(1)
        actions.addWidget(self.open_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.export_button)
        layout.addLayout(actions)

    def _apply_preferences_to_ui(self) -> None:
        self.key_input.setText(self.preferences.default_key)
        index = 0 if self.preferences.replace_mode == "replace" else 1
        self.replace_mode.setCurrentIndex(index)
        self._refresh_recent_exports()
        if self.preferences.sticky_panel_position and self.preferences.panel_x is not None and self.preferences.panel_y is not None:
            self.move(self.preferences.panel_x, self.preferences.panel_y)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Stems")
        menu = QMenu(self)
        show_action = menu.addAction("Show Panel")
        show_action.triggered.connect(self.showNormal)
        scan_action = menu.addAction("Scan Current Set")
        scan_action.triggered.connect(self.scan_current_set)
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

    def _refresh_recent_exports(self) -> None:
        self.recent_exports.clear()
        for entry in self.preferences.recent_exports:
            item = QListWidgetItem(f"{entry.song_name} -> {entry.stems_dir}")
            item.setData(Qt.UserRole, entry.stems_dir)
            item.setToolTip(entry.summary)
            self.recent_exports.addItem(item)

    def scan_current_set(self) -> None:
        if self.scan_thread is not None:
            return
        self.scan_button.setEnabled(False)
        self.export_button.setEnabled(False)
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
        self.progress_label.setText("Scan complete")
        self.summary_label.setText(f"Detected {count} stem{'s' if count != 1 else ''}.")
        self.export_button.setEnabled(count > 0)
        self.open_button.setEnabled(self.current_job is not None or self.project is not None)

    def _handle_scan_failure(self, message: str) -> None:
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
        for track in tracks:
            item = QListWidgetItem(self.track_list)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            checkbox = QCheckBox(track.name)
            checkbox.setChecked(track.selected)
            checkbox.toggled.connect(self.update_destination_preview)
            status = QLabel("Auto")
            status.setStyleSheet("color: #6b7280;")
            row_layout.addWidget(checkbox)
            row_layout.addStretch(1)
            row_layout.addWidget(status)
            self.track_list.setItemWidget(item, row)
            self.item_by_track_name[track.name] = item
            self.status_by_track_name[track.name] = status

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
        job = self.state.build_export_job(
            key=self.key_input.text().strip() or None,
            replace_mode=self.replace_mode.currentData(),
        )
        self.current_job = replace(job, tracks=tracks)
        self.destination_value.setText(str(self.current_job.stems_dir))
        self.export_button.setEnabled(bool(self.current_job.selected_tracks))
        self.open_button.setEnabled(True)

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

        self.progress_bar.setRange(0, len(self.current_job.selected_tracks) or 1)
        self.progress_bar.setValue(0)
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
                palette = {
                    "success": "#15803d",
                    "skipped": "#92400e",
                    "failed": "#b91c1c",
                }
                label.setText(event.title())
                label.setStyleSheet(f"color: {palette[event]};")
        elif event == "cancelled":
            self.summary_label.setText("Cancel requested. Current stem will finish safely.")

    def _handle_export_finished(self, result: ExportResult) -> None:
        self.current_result = result
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.progress_label.setText("Export complete")
        failures = [item.track.name for item in result.items if item.status == "failed"]
        summary = f"Exported {result.success_count}/{len(result.job.selected_tracks)} stems to {result.job.stems_dir}."
        if failures:
            summary += f" Failed: {', '.join(failures)}."
        self.summary_label.setText(summary)
        self.open_button.setEnabled(True)
        self.copy_summary_button.setEnabled(True)
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
        self._refresh_recent_exports()
        if self.preferences.copy_summary_to_clipboard:
            self.copy_summary()
        if self.preferences.auto_open_folder:
            self.open_export_folder()

    def _handle_export_failed(self, message: str) -> None:
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

    def copy_summary(self) -> None:
        if self.current_result is None:
            return
        summary = build_export_summary(self.current_result)
        clipboard = self.window().windowHandle().screen().context().clipboard() if False else None
        del clipboard
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(summary)
        self.summary_label.setText("Export summary copied to clipboard.")

    def cancel_export(self) -> None:
        if self.export_worker is None:
            return
        self.export_worker.cancel()
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

    def _open_recent_export(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
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
