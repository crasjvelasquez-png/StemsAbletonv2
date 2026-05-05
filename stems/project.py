from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from .errors import ProjectDetectionError
from .naming import NEW_STEMS_PATTERN, stems_folder_name


logger = logging.getLogger("stems")


def _bad_path(path: str | Path) -> bool:
    value = str(path)
    return "Backup" in value or ".backup" in value or "MobileBackups" in value


def _find_als_on_disk(name: str, runner=subprocess.run, home: Path | None = None) -> list[Path]:
    search_home = home or Path.home()
    search_roots = [
        search_home / "Music" / "Ableton",
        search_home / "Music",
        search_home / "Documents",
        search_home / "Desktop",
        search_home,
    ]
    seen: set[Path] = set()
    for root in search_roots:
        if not root.exists() or root in seen:
            continue
        seen.add(root)
        try:
            result = runner(
                ["find", str(root), "-maxdepth", "6", "-name", f"{name}.als"],
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
    process_queries = [
        'first process whose name starts with "Ableton Live"',
        'first process whose name is "Live"',
    ]
    for process_query in process_queries:
        try:
            result = runner(
                [
                    "osascript",
                    "-e",
                    (
                        'tell application "System Events" to get name of window 1 '
                        f'of ({process_query})'
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            continue
        title = result.stdout.strip().rstrip("*").strip().removesuffix(".als")
        if title:
            return title
    return None


def get_project_info(runner=subprocess.run, finder=_find_als_on_disk) -> tuple[Path, str]:
    song_name = _read_live_window_title(runner)

    if not song_name:
        raise ProjectDetectionError("Could not read project name from Ableton's window title.")

    candidates: list[Path] = []
    try:
        escaped = song_name.replace('"', '\\"')
        result = runner(
            ["mdfind", f'kMDItemFSName == "{escaped}.als"'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        candidates = [Path(path) for path in result.stdout.strip().splitlines() if path and not _bad_path(path)]
    except Exception:
        candidates = []

    if not candidates:
        logger.info("  (Spotlight didn't find '%s.als', searching disk...)", song_name)
        candidates = finder(song_name)

    if not candidates:
        raise ProjectDetectionError(f"Could not find '{song_name}.als' on disk. Save the project first.")

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    als_path = candidates[0]
    return als_path.parent, als_path.stem


def rename_old_stems_folders(project_folder: Path, new_name: str) -> None:
    target = project_folder / new_name
    for item in sorted(project_folder.iterdir(), key=lambda path: path.stat().st_mtime):
        if not item.is_dir() or item == target:
            continue
        if NEW_STEMS_PATTERN.match(item.name):
            continue
        if re.search(r"\bstem", item.name, re.IGNORECASE):
            destination = target
            suffix = 1
            while destination.exists():
                destination = project_folder / f"{new_name} ({suffix})"
                suffix += 1
            logger.info("  Renaming: '%s' -> '%s'", item.name, destination.name)
            item.rename(destination)


def get_stems_folder(project_folder: Path, song_name: str, key: str | None, bpm: int | float | None) -> Path:
    folder_name = stems_folder_name(song_name, key, bpm)
    stems_dir = project_folder / folder_name
    stems_dir.mkdir(parents=True, exist_ok=True)
    return stems_dir
