from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


ReplaceMode = Literal["replace", "keep"]
ExportStatus = Literal["pending", "skipped", "success", "failed"]


@dataclass(frozen=True)
class StemTrack:
    index: int
    name: str
    selected: bool = True
    detected: bool = True
    excluded_reason: str | None = None


@dataclass(frozen=True)
class ProjectContext:
    song_name: str
    project_folder: Path
    bpm: int | float | None = None


@dataclass(frozen=True)
class ExportJob:
    song_name: str
    project_folder: Path
    stems_dir: Path
    tracks: list[StemTrack]
    bpm: int | float | None = None
    key: str | None = None
    replace_mode: ReplaceMode = "replace"

    @property
    def selected_tracks(self) -> list[StemTrack]:
        return [track for track in self.tracks if track.selected]


@dataclass(frozen=True)
class ExportItemResult:
    track: StemTrack
    output_path: Path
    status: ExportStatus
    error: str | None = None


@dataclass(frozen=True)
class ExportResult:
    job: ExportJob
    items: list[ExportItemResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.items if item.status in {"success", "skipped"})

    @property
    def failure_count(self) -> int:
        return sum(1 for item in self.items if item.status == "failed")
