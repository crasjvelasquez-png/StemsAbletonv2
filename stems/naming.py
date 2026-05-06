from __future__ import annotations

import re
from datetime import date

from .preferences import DEFAULT_FOLDER_NAME_FORMAT, DEFAULT_STEM_NAME_FORMAT


NEW_STEMS_PATTERN = re.compile(r".+ - [A-Za-z]+ \d{1,2} \d{4} - Stems - .+", re.IGNORECASE)


def render_name(format_string: str, **tokens: object) -> str:
    mapping: dict[str, str] = {}
    for key, value in tokens.items():
        if value is None or value == "":
            mapping[key] = ""
        elif key == "index":
            try:
                mapping[key] = f"{int(value):02d}"
            except (ValueError, TypeError):
                mapping[key] = str(value)
        else:
            mapping[key] = str(value)
    result = format_string
    for token, text in mapping.items():
        result = result.replace("{" + token + "}", text)
    return result.strip()


def stems_folder_name(
    song_name: str,
    key: str | None,
    bpm: int | float | None,
    format_string: str | None = None,
) -> str:
    fmt = format_string or DEFAULT_FOLDER_NAME_FORMAT
    today = date.today().strftime("%B %d %Y")
    return render_name(
        fmt,
        song=song_name,
        key=key or "",
        bpm=str(bpm) if bpm is not None else "Unknown BPM",
        date=today,
    )


def stem_file_name(
    song_name: str,
    track_name: str,
    key: str | None = None,
    bpm: int | float | None = None,
    index: int | None = None,
    format_string: str | None = None,
) -> str:
    fmt = format_string or DEFAULT_STEM_NAME_FORMAT
    return render_name(
        fmt,
        song=song_name,
        track=track_name,
        key=key or "",
        bpm=str(bpm) if bpm is not None else "",
        index=index or "",
    )


def escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
