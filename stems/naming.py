from __future__ import annotations

import re
from datetime import date
from typing import Literal

from .preferences import DEFAULT_FOLDER_NAME_FORMAT, DEFAULT_STEM_NAME_FORMAT


NEW_STEMS_PATTERN = re.compile(r".+ - [A-Za-z]+ \d{1,2} \d{4} - Stems - .+", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")
STEM_NAME_TOKENS = ("song", "track", "bpm", "key", "date", "index")
FOLDER_NAME_TOKENS = ("song", "bpm", "key", "date")


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


def validate_name_format(format_string: str, kind: Literal["stem", "folder"]) -> str | None:
    value = format_string.strip()
    if not value:
        return "Enter a naming format."
    if "/" in value or "\\" in value:
        return "Remove path separators; formats can only name one file or folder."

    allowed = set(STEM_NAME_TOKENS if kind == "stem" else FOLDER_NAME_TOKENS)
    found = TOKEN_PATTERN.findall(value)
    unknown = sorted({token for token in found if token not in allowed})
    if unknown:
        return f"Unsupported token: {{{unknown[0]}}}."
    stripped = TOKEN_PATTERN.sub("", value)
    if "{" in stripped or "}" in stripped:
        return "Fix the unmatched token brace."
    if kind == "stem":
        if not value.lower().endswith(".wav"):
            return "Stem file formats must end in .wav."
        if "{track}" not in value and "{index}" not in value:
            return "Add {track} or {index} so each stem gets a unique name."
    return None


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
        date=date.today().strftime("%B %d %Y"),
        index=index or "",
    )


def escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
