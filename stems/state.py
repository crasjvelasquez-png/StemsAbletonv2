from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from .detection import find_bus_tracks
from .models import ExportJob, ExportRange, ProjectContext, StemTrack
from .project import get_project_info, stems_folder_path


class AppState:
    def __init__(self, ableton_client, project_info_getter=get_project_info, stems_folder_getter=stems_folder_path):
        self.ableton_client = ableton_client
        self.project_info_getter = project_info_getter
        self.stems_folder_getter = stems_folder_getter
        self.project: ProjectContext | None = None
        self.all_tracks: list[dict[str, object]] = []
        self.detected_tracks: list[StemTrack] = []
        self.export_range: ExportRange | None = None

    def scan_current_set(
        self,
        on_tracks: Callable[[list[StemTrack]], object] | None = None,
    ) -> tuple[ProjectContext, list[StemTrack]]:
        self.export_range = None
        project_result: list[tuple[Path, str]] = []
        project_error: list[BaseException] = []

        def _fetch_project() -> None:
            try:
                project_result.append(self.project_info_getter())
            except BaseException as exc:
                project_error.append(exc)

        project_thread = threading.Thread(target=_fetch_project, daemon=True)
        project_thread.start()

        count = self.ableton_client.get_track_count()
        bpm = self.ableton_client.get_bpm()
        self.all_tracks = self.ableton_client.get_all_tracks(count)
        self.detected_tracks = find_bus_tracks(self.all_tracks)
        if on_tracks is not None:
            on_tracks(self.detected_tracks)
        try:
            self.export_range = self.ableton_client.get_export_range()
        except Exception:
            self.export_range = None

        project_thread.join()
        if project_error:
            raise project_error[0]
        project_folder, song_name = project_result[0]
        self.project = ProjectContext(song_name=song_name, project_folder=project_folder, bpm=bpm)
        return self.project, self.detected_tracks

    def build_export_job(
        self,
        key: str | None = None,
        replace_mode: str = "replace",
        destination_root: str | Path | None = None,
        custom_song_name: str | None = None,
        stem_name_format: str | None = None,
        folder_name_format: str | None = None,
        artist: str | None = None,
    ) -> ExportJob:
        if self.project is None:
            raise RuntimeError("scan_current_set() must run before build_export_job().")
        song = custom_song_name or self.project.song_name
        # Stem exports live with the detected .als project. Keep the legacy
        # argument for API compatibility, but do not let a saved preference
        # redirect an export away from its project.
        del destination_root
        stems_root = self.project.project_folder
        stems_dir = self.stems_folder_getter(
            stems_root, song, key, self.project.bpm, format_string=folder_name_format,
            artist=artist,
        )
        return ExportJob(
            song_name=self.project.song_name,
            project_folder=self.project.project_folder,
            stems_dir=stems_dir,
            tracks=self.detected_tracks,
            bpm=self.project.bpm,
            key=key,
            artist=artist,
            replace_mode=replace_mode,
            custom_song_name=custom_song_name,
            stem_name_format=stem_name_format,
            folder_name_format=folder_name_format,
        )
