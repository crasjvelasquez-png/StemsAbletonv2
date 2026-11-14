from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from pathlib import Path

from .errors import ProjectDetectionError
from .naming import render_name, stems_folder_name
from .preferences import DEFAULT_FOLDER_NAME_FORMAT


logger = logging.getLogger("stems")


def _bad_path(path: str | Path) -> bool:
    value = str(path)
    return (
        "Backup" in value
        or ".backup" in value
        or "MobileBackups" in value
        or "/Library/Preferences/Ableton/" in value
    )


def _find_als_on_disk(name: str, runner=subprocess.run, home: Path | None = None) -> list[Path]:
    search_home = home or Path.home()
    search_roots = [
        search_home / "Music" / "Ableton",
        search_home / "Music",
        search_home / "Documents",
        search_home / "Desktop",
        search_home,
    ]
    volumes_root = Path("/Volumes")
    if volumes_root.exists():
        try:
            search_roots.extend(path for path in volumes_root.iterdir() if path.is_dir())
        except OSError:
            pass
    seen: set[Path] = set()
    for root in search_roots:
        if not root.exists() or root in seen:
            continue
        seen.add(root)
        max_depth = "10" if root.parent == volumes_root else "6"
        try:
            result = runner(
                ["find", str(root), "-maxdepth", max_depth, "-name", f"{name}.als"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            continue
        candidates = [Path(path) for path in result.stdout.strip().splitlines() if path and not _bad_path(path)]
        if candidates:
            return candidates
    return []


def _read_live_window_title(runner=subprocess.run) -> str | None:
    title, _errors = _read_live_window_title_with_errors(runner)
    return title


def _clean_live_window_title(title: str) -> str:
    return title.strip().rstrip("*").strip().removesuffix(".als")


def _read_live_window_title_with_errors(runner=subprocess.run) -> tuple[str | None, list[str]]:
    scripts = [
        """
        tell application "System Events"
            set liveProcesses to every process whose name is "Live" or name starts with "Ableton Live"
            repeat with liveProcess in liveProcesses
                if (count of windows of liveProcess) > 0 then
                    return name of window 1 of liveProcess
                end if
            end repeat
        end tell
        """,
    ]
    process_queries = [
        'first process whose name starts with "Ableton Live"',
        'first process whose name is "Live"',
    ]
    for process_query in process_queries:
        scripts.append(
            'tell application "System Events" to get name of window 1 '
            f'of ({process_query})'
        )

    errors: list[str] = []
    for script in scripts:
        try:
            result = runner(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception as exc:
            errors.append(str(exc))
            continue
        if result.stderr.strip():
            errors.append(result.stderr.strip())
        title = _clean_live_window_title(result.stdout)
        if title:
            return title, errors
    return None, errors


def _project_from_backup_candidate(path: Path, name: str) -> Path | None:
    if path.parent.name != "Backup":
        return None
    candidate = path.parent.parent / f"{name}.als"
    if candidate.exists() and not _bad_path(candidate):
        return candidate
    return None


SPOTLIGHT_ATTEMPTS = 3
SPOTLIGHT_RETRY_DELAY = 1.0
_LAST_KNOWN_ALS: dict[str, Path] = {}
_CACHE_LOCK = threading.Lock()


def clear_project_cache() -> None:
    """Clear cached song-to-.als path mappings."""
    with _CACHE_LOCK:
        _LAST_KNOWN_ALS.clear()


def _spotlight_candidates(song_name: str, runner) -> list[Path]:
    try:
        escaped = song_name.replace('"', '\\"')
        result = runner(
            ["mdfind", f'kMDItemFSName == "{escaped}.als"'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        mdfind_paths = [Path(path) for path in result.stdout.strip().splitlines() if path]
        candidates = [path for path in mdfind_paths if not _bad_path(path)]
        if not candidates:
            candidates = [
                candidate
                for path in mdfind_paths
                if (candidate := _project_from_backup_candidate(path, song_name)) is not None
            ]
        return candidates
    except Exception:
        return []


def get_project_info(runner=subprocess.run, finder=_find_als_on_disk, sleep=time.sleep) -> tuple[Path, str]:
    song_name, title_errors = _read_live_window_title_with_errors(runner)

    if not song_name:
        detail = ""
        if title_errors:
            detail = f" Last AppleScript error: {title_errors[-1]}"
        raise ProjectDetectionError(f"Could not read project name from Ableton's window title.{detail}")

    if song_name.lower().startswith("untitled"):
        raise ProjectDetectionError("This Ableton set hasn't been saved yet.")

    # Spotlight can briefly lose a file while Ableton is saving it. Ask a few
    # times before falling back to the slow disk search, which can time out on
    # external drives.
    candidates: list[Path] = []
    for attempt in range(SPOTLIGHT_ATTEMPTS):
        candidates = _spotlight_candidates(song_name, runner)
        if candidates:
            break
        if attempt == 0:
            with _CACHE_LOCK:
                cached = _LAST_KNOWN_ALS.get(song_name)
            if cached is not None:
                if cached.exists() and not _bad_path(cached):
                    with _CACHE_LOCK:
                        _LAST_KNOWN_ALS[song_name] = cached
                    return cached.parent, cached.stem
                with _CACHE_LOCK:
                    if _LAST_KNOWN_ALS.get(song_name) == cached:
                        _LAST_KNOWN_ALS.pop(song_name, None)
        if attempt < SPOTLIGHT_ATTEMPTS - 1:
            sleep(SPOTLIGHT_RETRY_DELAY)

    if not candidates:
        logger.info("  (Spotlight didn't find '%s.als', searching disk...)", song_name)
        candidates = finder(song_name)

    if not candidates:
        raise ProjectDetectionError(f"Could not find '{song_name}.als' on disk. Save the project first.")

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    als_path = candidates[0]
    with _CACHE_LOCK:
        _LAST_KNOWN_ALS[song_name] = als_path
    return als_path.parent, als_path.stem


def get_stems_folder(
    project_folder: Path,
    song_name: str,
    key: str | None,
    bpm: int | float | None,
    format_string: str | None = None,
    artist: str | None = None,
) -> Path:
    stems_dir = stems_folder_path(project_folder, song_name, key, bpm, format_string=format_string, artist=artist)
    stems_dir.mkdir(parents=True, exist_ok=True)
    return stems_dir


def stems_folder_path(
    project_folder: Path,
    song_name: str,
    key: str | None,
    bpm: int | float | None,
    format_string: str | None = None,
    artist: str | None = None,
) -> Path:
    folder_name = stems_folder_name(song_name, key, bpm, format_string=format_string, artist=artist)
    desired = project_folder / folder_name
    if desired.is_dir():
        return desired
    existing = find_existing_stems_folder(project_folder, song_name, key, bpm, format_string, artist)
    return existing or desired


def find_existing_stems_folder(
    project_folder: Path,
    song_name: str,
    key: str | None = None,
    bpm: int | float | None = None,
    format_string: str | None = None,
    artist: str | None = None,
) -> Path | None:
    """Reuse a stems folder already inside the project folder.

    Order: same naming format from another day, then any folder with both the
    song name and "stem" in its name, then a plain "Stems" folder.
    """
    try:
        folders = [
            entry for entry in project_folder.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
            and "stem" in entry.name.casefold()
        ]
    except OSError:
        return None
    if not folders:
        return None

    marker = "\x00DATE\x00"
    template = render_name(
        format_string or DEFAULT_FOLDER_NAME_FORMAT,
        song=song_name,
        artist=artist or "",
        key=key or "",
        bpm=str(bpm) if bpm is not None else "Unknown BPM",
        date=marker,
    )
    pattern = re.compile(
        "^" + re.escape(template).replace(re.escape(marker), ".+") + "$", re.IGNORECASE
    )
    song = song_name.casefold()

    def newest(candidates: list[Path]) -> Path | None:
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    return (
        newest([f for f in folders if pattern.match(f.name)])
        or newest([f for f in folders if song and song in f.name.casefold()])
        or newest([f for f in folders if f.name.casefold() in {"stems", "stem"}])
    )
