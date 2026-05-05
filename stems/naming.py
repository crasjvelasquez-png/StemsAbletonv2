from __future__ import annotations

import re
from datetime import date


NEW_STEMS_PATTERN = re.compile(r".+ - [A-Za-z]+ \d{1,2} \d{4} - Stems - .+", re.IGNORECASE)


def stems_folder_name(song_name: str, key: str | None, bpm: int | float | None) -> str:
    today = date.today().strftime("%B %d %Y")
    bpm_str = str(bpm) if bpm is not None else "Unknown BPM"
    suffix = f"{key} {bpm_str} BPM" if key else f"{bpm_str} BPM"
    return f"{song_name} - {today} - Stems - {suffix}"


def stem_file_name(song_name: str, track_name: str) -> str:
    return f"{song_name}_{track_name}.wav"


def escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
