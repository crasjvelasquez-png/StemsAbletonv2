from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


ReplaceMode = Literal["replace", "keep", "keep_both"]
ExportStatus = Literal["pending", "skipped", "success", "failed"]
DEFAULT_RANGE_BARS = (1, 200)


def normalize_track_color(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if 0 <= value <= 0xFFFFFF:
        return int(value)
    return None


@dataclass(frozen=True)
class StemTrack:
    index: int
    name: str
    selected: bool = True
    detected: bool = True
    excluded_reason: str | None = None
    color: int | None = None


@dataclass(frozen=True)
class ExportRange:
    start_beats: float
    length_beats: float
    numerator: int
    denominator: int
    bpm: float | None

    @property
    def beats_per_bar(self) -> float:
        return self.numerator * 4.0 / self.denominator

    @property
    def start_bar(self) -> int:
        return math.floor(self.start_beats / self.beats_per_bar) + 1

    @property
    def end_bar(self) -> int:
        return math.ceil((self.start_beats + self.length_beats) / self.beats_per_bar)

    @property
    def bar_count(self) -> int:
        return self.end_bar - self.start_bar + 1

    @property
    def duration_seconds(self) -> float | None:
        if self.bpm is None or self.bpm <= 0:
            return None
        return self.length_beats * 60.0 / self.bpm

    def describe(self) -> tuple[str, str]:
        if self.length_beats <= 0:
            default_start, default_end = DEFAULT_RANGE_BARS
            default_bars = default_end - default_start + 1
            return f"Bars {default_start} to {default_end}", f"{default_bars} bars"
        bars = self.bar_count
        bar_word = "bar" if bars == 1 else "bars"
        headline = f"Bars {self.start_bar} to {self.end_bar}"
        duration = self.duration_seconds
        if duration is not None:
            total_seconds = max(0, round(duration))
            minutes, seconds = divmod(total_seconds, 60)
            detail = f"{bars} {bar_word} · {minutes}:{seconds:02d}"
        else:
            detail = f"{bars} {bar_word}"
        return headline, detail


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
    artist: str | None = None
    replace_mode: ReplaceMode = "replace"
    custom_song_name: str | None = None
    stem_name_format: str | None = None
    folder_name_format: str | None = None

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
