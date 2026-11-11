from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


def default_preferences_path() -> Path:
    return Path.home() / ".stems_ableton" / "preferences.json"


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
    auto_open_folder: bool = True
    panel_x: int | None = None
    panel_y: int | None = None
    panel_width: int | None = None
    panel_height: int | None = None
    stem_name_format: str = DEFAULT_STEM_NAME_FORMAT
    folder_name_format: str = DEFAULT_FOLDER_NAME_FORMAT


class PreferencesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_preferences_path()

    def load(self) -> Preferences:
        if not self.path.exists():
            return Preferences()
        data = json.loads(self.path.read_text())
        # Ignore retired settings, including clipboard, destination and history.
        data = {key: value for key, value in data.items() if key in Preferences.__dataclass_fields__}
        for key, presets in (("stem_name_format", BUILTIN_STEM_NAMING_PRESETS),
                             ("folder_name_format", BUILTIN_FOLDER_NAMING_PRESETS)):
            if data.get(key) not in {preset.format_string for preset in presets}:
                data[key] = presets[0].format_string
        return Preferences(**data)

    def save(self, preferences: Preferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(preferences), indent=2))
