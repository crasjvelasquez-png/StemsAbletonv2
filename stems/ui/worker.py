from __future__ import annotations

from ..automation import find_ableton_app_path
from ..preflight import check_ableton_running, check_osc_reachable, check_project_saved
from ..errors import AbletonConnectionError, ProjectDetectionError
from ..export import ExportAutomation, execute_export_job
from ..models import ExportJob
from ..state import AppState

try:
    from PySide6.QtCore import QObject, Signal
except ImportError as exc:
    raise SystemExit("PySide6 is not installed. Run: pip install PySide6") from exc


class _KnownTrackCount:
    """Answers check_osc_reachable from the scan's own result, no extra Ableton round trip."""

    def __init__(self, count: int) -> None:
        self._count = count

    def get_track_count(self) -> int:
        return self._count


class ScanWorker(QObject):
    tracks_ready = Signal(object)
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state

    def run(self) -> None:
        try:
            check_ableton_running(find_ableton_app_path)
            try:
                project, _tracks = self.state.scan_current_set(on_tracks=self.tracks_ready.emit)
            except AbletonConnectionError as exc:
                raise AbletonConnectionError(
                    "Ableton isn't connected. In Live > Settings > Link, Tempo & MIDI, "
                    "select AbletonOSC as a Control Surface, then click Try Again."
                ) from exc
            except ProjectDetectionError as exc:
                raise ProjectDetectionError(
                    f"Save your Ableton set, bring its window to the front, then click Try Again. {exc}"
                ) from exc
            # Cheap checks only; the full preflight (incl. Accessibility) runs at export.
            check_osc_reachable(_KnownTrackCount(len(self.state.all_tracks)))
            check_project_saved(project.project_folder, project.song_name)
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
