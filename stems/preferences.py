from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import get_type_hints
from pathlib import Path


def default_preferences_path() -> Path:
    return Path.home() / ".stems_ableton" / "preferences.json"


@dataclass
class RecentExport:
    song_name: str
    stems_dir: str
    exported_count: int
    failed_count: int
    summary: str


DEFAULT_STEM_NAME_FORMAT = "{song}_{track} - {key} {bpm} BPM.wav"
DEFAULT_FOLDER_NAME_FORMAT = "{song} - {date} - Stems - {key} {bpm} BPM"


@dataclass
class Preferences:
    replace_mode: str = "replace"
    export_destination_root: str = ""
    auto_open_folder: bool = True
    menubar_mode: bool = False
    launch_at_login: bool = False
    copy_summary_to_clipboard: bool = True
    sticky_panel_position: bool = True
    panel_x: int | None = None
    panel_y: int | None = None
    stem_name_format: str = DEFAULT_STEM_NAME_FORMAT
    folder_name_format: str = DEFAULT_FOLDER_NAME_FORMAT
    recent_exports: list[RecentExport] = field(default_factory=list)


class PreferencesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_preferences_path()

    def load(self) -> Preferences:
        if not self.path.exists():
            return Preferences()
        data = json.loads(self.path.read_text())
        recent = [RecentExport(**item) for item in data.get("recent_exports", [])]
        data["recent_exports"] = recent
        data = {key: value for key, value in data.items() if key in get_type_hints(Preferences)}
        return Preferences(**data)

    def save(self, preferences: Preferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(preferences)
        self.path.write_text(json.dumps(payload, indent=2))


def append_recent_export(preferences: Preferences, entry: RecentExport, limit: int = 6) -> Preferences:
    recent = [entry]
    for item in preferences.recent_exports:
        if item.song_name == entry.song_name and item.stems_dir == entry.stems_dir:
            continue
        recent.append(item)
    preferences.recent_exports = recent[:limit]
    return preferences
