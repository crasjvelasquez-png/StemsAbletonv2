from __future__ import annotations

from pathlib import Path

from .detection import find_bus_tracks
from .models import ExportJob, ProjectContext, StemTrack
from .naming import stems_folder_name
from .project import get_project_info, get_stems_folder


class AppState:
    def __init__(self, ableton_client, project_info_getter=get_project_info, stems_folder_getter=get_stems_folder):
        self.ableton_client = ableton_client
        self.project_info_getter = project_info_getter
        self.stems_folder_getter = stems_folder_getter
        self.project: ProjectContext | None = None
        self.all_tracks: list[dict[str, object]] = []
        self.detected_tracks: list[StemTrack] = []

    def scan_current_set(self) -> tuple[ProjectContext, list[StemTrack]]:
        count = self.ableton_client.get_track_count()
        bpm = self.ableton_client.get_bpm()
        self.all_tracks = self.ableton_client.get_all_tracks(count)
        self.detected_tracks = find_bus_tracks(self.all_tracks)
        project_folder, song_name = self.project_info_getter()
        self.project = ProjectContext(song_name=song_name, project_folder=project_folder, bpm=bpm)
        return self.project, self.detected_tracks

    def build_export_job(
        self,
        key: str | None = None,
        replace_mode: str = "replace",
        destination_root: str | Path | None = None,
    ) -> ExportJob:
        if self.project is None:
            raise RuntimeError("scan_current_set() must run before build_export_job().")
        if destination_root is None:
            stems_dir = self.stems_folder_getter(self.project.project_folder, self.project.song_name, key, self.project.bpm)
        else:
            stems_dir = Path(destination_root) / stems_folder_name(self.project.song_name, key, self.project.bpm)
            stems_dir.mkdir(parents=True, exist_ok=True)
        return ExportJob(
            song_name=self.project.song_name,
            project_folder=self.project.project_folder,
            stems_dir=stems_dir,
            tracks=self.detected_tracks,
            bpm=self.project.bpm,
            key=key,
            replace_mode=replace_mode,
        )
