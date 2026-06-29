from __future__ import annotations

import logging
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import ProjectDetectionError
from .naming import NEW_STEMS_PATTERN, stems_folder_name
from .preferences import PreferencesStore


logger = logging.getLogger("stems")


@dataclass(frozen=True)
class DiskSearchResult:
    candidates: list[Path]
    timed_out: bool = False


def _bad_path(path: str | Path) -> bool:
    value = str(path)
    return (
        "Backup" in value
        or ".backup" in value
        or "MobileBackups" in value
        or "/Library/Preferences/Ableton/" in value
    )


def _find_als_on_disk(name: str, runner=subprocess.run, home: Path | None = None) -> DiskSearchResult:
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
    candidates: list[Path] = []
    timed_out = False
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
        except subprocess.TimeoutExpired:
            timed_out = True
            continue
        except Exception:
            continue
        candidates.extend(
            Path(path)
            for path in result.stdout.strip().splitlines()
            if path and not _bad_path(path)
        )
    return DiskSearchResult(candidates=candidates, timed_out=timed_out)


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


def _is_accessibility_error(errors: list[str]) -> bool:
    for err in errors:
        if "assistive access" in err.lower():
            return True
    return False


def _is_ableton_not_open_error(errors: list[str]) -> bool:
    for err in errors:
        normalized = err.lower().replace("can’t", "can't")
        if "can't get process" in normalized and ('name = "live"' in normalized or "name starts with" in normalized):
            return True
    return False


def _valid_candidate(path: Path, name: str) -> bool:
    return path.name == f"{name}.als" and path.is_file() and not _bad_path(path)


def _cached_candidate(name: str, preferences_store: PreferencesStore) -> tuple[Path | None, str | None]:
    preferences = preferences_store.load()
    cached_folder = preferences.project_locations.get(name)
    if not cached_folder:
        return None, None

    candidate = Path(cached_folder) / f"{name}.als"
    if _valid_candidate(candidate, name):
        return candidate, None

    missing_volume = None
    parts = Path(cached_folder).parts
    if len(parts) >= 3 and parts[1] == "Volumes" and not Path(*parts[:3]).exists():
        missing_volume = parts[2]

    preferences_store.set_project_location(name, None)
    return None, missing_volume


def _cache_candidate(name: str, path: Path, preferences_store: PreferencesStore) -> None:
    if preferences_store.load().project_locations.get(name) == str(path.parent):
        return
    preferences_store.set_project_location(name, str(path.parent))


def _spotlight_candidates(name: str, runner=subprocess.run) -> list[Path]:
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    result = runner(
        ["mdfind", f'kMDItemFSName == "{escaped}.als"'],
        capture_output=True,
        text=True,
        timeout=5,
    )
    paths = [Path(path) for path in result.stdout.strip().splitlines() if path]
    candidates = [path for path in paths if _valid_candidate(path, name)]
    candidates.extend(
        candidate
        for path in paths
        if (candidate := _project_from_backup_candidate(path, name)) is not None
    )
    return candidates


def get_project_info(
    runner=subprocess.run,
    finder=_find_als_on_disk,
    preferences_store: PreferencesStore | None = None,
    sleeper=time.sleep,
    spotlight_attempts: int = 3,
    spotlight_delay: float = 0.4,
) -> tuple[Path, str]:
    song_name, title_errors = _read_live_window_title_with_errors(runner)

    if not song_name:
        if _is_accessibility_error(title_errors):
            raise ProjectDetectionError(
                "Stems needs Accessibility permission to read Ableton's project name.\n\n"
                "Go to System Settings → Privacy & Security → Accessibility,\n"
                "then enable Stems and relaunch the app."
            )
        if _is_ableton_not_open_error(title_errors):
            raise ProjectDetectionError("Ableton is not open")
        detail = ""
        if title_errors:
            detail = f" Last AppleScript error: {title_errors[-1]}"
        raise ProjectDetectionError(f"Could not read project name from Ableton's window title.{detail}")

    store = preferences_store or PreferencesStore()
    cached, missing_volume = _cached_candidate(song_name, store)
    if cached is not None:
        return cached.parent, cached.stem

    candidates: list[Path] = []
    for attempt in range(max(1, spotlight_attempts)):
        try:
            candidates = _spotlight_candidates(song_name, runner)
        except Exception:
            candidates = []
        if candidates:
            break
        if attempt + 1 < spotlight_attempts:
            sleeper(spotlight_delay)

    search_timed_out = False
    if not candidates:
        logger.info("  (Spotlight didn't find '%s.als', searching disk...)", song_name)
        search_result = finder(song_name)
        if isinstance(search_result, DiskSearchResult):
            candidates = search_result.candidates
            search_timed_out = search_result.timed_out
        else:
            candidates = search_result

    if not candidates:
        if missing_volume:
            raise ProjectDetectionError(
                f"The drive '{missing_volume}' containing '{song_name}.als' is not mounted. Connect it and scan again."
            )
        if search_timed_out:
            raise ProjectDetectionError(
                f"Searching for '{song_name}.als' timed out. The drive may be slow or unavailable; reconnect it and scan again."
            )
        raise ProjectDetectionError(f"Could not find '{song_name}.als' on disk. Save the project first.")

    candidates = [path for path in candidates if _valid_candidate(path, song_name)]
    if not candidates:
        raise ProjectDetectionError(f"Could not find '{song_name}.als' on disk. Save the project first.")
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    als_path = candidates[0]
    _cache_candidate(song_name, als_path, store)
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
    return project_folder / folder_name
