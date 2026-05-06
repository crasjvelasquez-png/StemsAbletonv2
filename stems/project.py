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


def get_project_info(runner=subprocess.run, finder=_find_als_on_disk) -> tuple[Path, str]:
    song_name, title_errors = _read_live_window_title_with_errors(runner)

    if not song_name:
        detail = ""
        if title_errors:
            detail = f" Last AppleScript error: {title_errors[-1]}"
        raise ProjectDetectionError(f"Could not read project name from Ableton's window title.{detail}")

    candidates: list[Path] = []
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


def get_stems_folder(
    project_folder: Path,
    song_name: str,
    key: str | None,
    bpm: int | float | None,
    format_string: str | None = None,
) -> Path:
    folder_name = stems_folder_name(song_name, key, bpm, format_string=format_string)
    stems_dir = project_folder / folder_name
    stems_dir.mkdir(parents=True, exist_ok=True)
    return stems_dir
