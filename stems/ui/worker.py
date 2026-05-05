from __future__ import annotations

from ..export import ExportAutomation, execute_export_job
from ..models import ExportJob
from ..project import rename_old_stems_folders
from ..state import AppState

try:
    from PySide6.QtCore import QObject, Signal
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc


class ScanWorker(QObject):
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state

    def run(self) -> None:
        try:
            project, tracks = self.state.scan_current_set()
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(self.state, project)


class ExportWorker(QObject):
    progress = Signal(str, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, state: AppState, job: ExportJob) -> None:
        super().__init__()
        self.state = state
        self.job = job
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        try:
            rename_old_stems_folders(self.job.project_folder, self.job.stems_dir.name)
            result = execute_export_job(
                self.job,
                self.state.ableton_client,
                ExportAutomation(),
                progress=lambda event, message: self.progress.emit(event, message),
                cancel_check=lambda: self.cancel_requested,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)
