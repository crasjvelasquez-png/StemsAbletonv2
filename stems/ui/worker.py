from __future__ import annotations

from ..automation import find_ableton_app_path, osascript
from ..preflight import check_ableton_running, run_export_preflight
from ..errors import AbletonConnectionError, ProjectDetectionError
from ..export import ExportAutomation, execute_export_job
from ..models import ExportJob
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
            check_ableton_running(find_ableton_app_path)
            try:
                project, tracks = self.state.scan_current_set()
            except AbletonConnectionError as exc:
                raise AbletonConnectionError(
                    "Ableton isn't connected. In Live > Settings > Link, Tempo & MIDI, "
                    "select AbletonOSC as a Control Surface, then click Try Again."
                ) from exc
            except ProjectDetectionError as exc:
                raise ProjectDetectionError(
                    f"Save your Ableton set, bring its window to the front, then click Try Again. {exc}"
                ) from exc
            run_export_preflight(
                ableton_client=self.state.ableton_client,
                project_folder=project.project_folder,
                song_name=project.song_name,
                app_path_finder=find_ableton_app_path,
                script_runner=osascript,
            )
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
