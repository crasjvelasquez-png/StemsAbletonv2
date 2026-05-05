from __future__ import annotations

import re

from .models import StemTrack


BUS_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9 _&/]+$")
DEFAULT_EXCLUDED_NAMES = {"PRINT", "MIXBUS", "REF", "MASTER"}


def is_stem_candidate(name: str, exclusions: set[str] | None = None) -> bool:
    cleaned = name.strip()
    excluded = exclusions or DEFAULT_EXCLUDED_NAMES
    return bool(cleaned) and BUS_NAME_PATTERN.match(cleaned) is not None and cleaned not in excluded


def find_bus_tracks(all_tracks: list[dict[str, object]], exclusions: set[str] | None = None) -> list[StemTrack]:
    tracks: list[StemTrack] = []
    for track in all_tracks:
        name = str(track["name"]).strip()
        if is_stem_candidate(name, exclusions=exclusions):
            tracks.append(StemTrack(index=int(track["index"]), name=name))
    return tracks
