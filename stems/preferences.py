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


@dataclass
class NamingPreset:
    preset_id: str
    name: str
    format_string: str


DEFAULT_STEM_NAME_FORMAT = "{song}_{track} - {key} {bpm} BPM.wav"
DEFAULT_FOLDER_NAME_FORMAT = "{song} - {date} - Stems - {key} {bpm} BPM"

BUILTIN_STEM_NAMING_PRESETS = (
    NamingPreset("builtin-stem-studio-detail", "Studio Detail", DEFAULT_STEM_NAME_FORMAT),
    NamingPreset("builtin-stem-compact", "Compact", "{song}_{track}.wav"),
    NamingPreset("builtin-stem-numbered", "Numbered", "{index}_{track}_{song}.wav"),
)

BUILTIN_FOLDER_NAMING_PRESETS = (
    NamingPreset("builtin-folder-studio-detail", "Studio Detail", DEFAULT_FOLDER_NAME_FORMAT),
    NamingPreset("builtin-folder-compact", "Compact", "{song} - Stems"),
    NamingPreset("builtin-folder-dated", "Dated", "{song} - {date} - Stems"),
)


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
    panel_width: int | None = None
    panel_height: int | None = None
    stem_name_format: str = DEFAULT_STEM_NAME_FORMAT
    folder_name_format: str = DEFAULT_FOLDER_NAME_FORMAT
    stem_name_presets: list[NamingPreset] = field(default_factory=list)
    folder_name_presets: list[NamingPreset] = field(default_factory=list)
    default_stem_name_preset_id: str = BUILTIN_STEM_NAMING_PRESETS[0].preset_id
    default_folder_name_preset_id: str = BUILTIN_FOLDER_NAMING_PRESETS[0].preset_id
    recent_exports: list[RecentExport] = field(default_factory=list)


def all_naming_presets(preferences: Preferences, kind: str) -> list[NamingPreset]:
    if kind == "stem":
        return [*BUILTIN_STEM_NAMING_PRESETS, *preferences.stem_name_presets]
    if kind == "folder":
        return [*BUILTIN_FOLDER_NAMING_PRESETS, *preferences.folder_name_presets]
    raise ValueError(f"Unknown naming preset kind: {kind}")


def _normalize_naming_kind(preferences: Preferences, kind: str) -> None:
    if kind == "stem":
        format_string = preferences.stem_name_format
        default_attr = "default_stem_name_preset_id"
        custom_presets = preferences.stem_name_presets
    else:
        format_string = preferences.folder_name_format
        default_attr = "default_folder_name_preset_id"
        custom_presets = preferences.folder_name_presets

    presets = all_naming_presets(preferences, kind)
    current_default = next(
        (preset for preset in presets if preset.preset_id == getattr(preferences, default_attr)),
        None,
    )
    if current_default is not None and current_default.format_string == format_string:
        return

    matching = next((preset for preset in presets if preset.format_string == format_string), None)
    if matching is not None:
        setattr(preferences, default_attr, matching.preset_id)
        return

    legacy_id = f"custom-{kind}-current"
    legacy = next((preset for preset in custom_presets if preset.preset_id == legacy_id), None)
    if legacy is None:
        legacy = NamingPreset(legacy_id, "Current Format", format_string)
        custom_presets.append(legacy)
    else:
        legacy.format_string = format_string
    setattr(preferences, default_attr, legacy_id)


def normalize_naming_preferences(preferences: Preferences) -> Preferences:
    _normalize_naming_kind(preferences, "stem")
    _normalize_naming_kind(preferences, "folder")
    return preferences


class PreferencesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_preferences_path()

    def load(self) -> Preferences:
        if not self.path.exists():
            return Preferences()
        data = json.loads(self.path.read_text())
        recent = [RecentExport(**item) for item in data.get("recent_exports", [])]
        data["recent_exports"] = recent
        for key in ("stem_name_presets", "folder_name_presets"):
            presets = []
            for item in data.get(key, []):
                try:
                    preset = NamingPreset(**item)
                except (TypeError, ValueError):
                    continue
                if preset.preset_id and preset.name and preset.format_string:
                    presets.append(preset)
            data[key] = presets
        data = {key: value for key, value in data.items() if key in get_type_hints(Preferences)}
        return normalize_naming_preferences(Preferences(**data))

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
