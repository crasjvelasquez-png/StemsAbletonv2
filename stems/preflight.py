from __future__ import annotations

from pathlib import Path
from typing import Callable

from .errors import PreflightCheckError


def check_ableton_running(app_path_finder: Callable[[], str | None]) -> None:
    if app_path_finder() is None:
        raise PreflightCheckError("Open Ableton Live and a saved set, then click Try Again.")


def check_osc_reachable(ableton_client) -> None:
    if ableton_client.get_track_count() <= 0:
        raise PreflightCheckError("Ableton isn't connected. Select AbletonOSC as a Control Surface in Live > Settings > Link, Tempo & MIDI, then click Try Again.")


def check_project_saved(project_folder: Path, song_name: str) -> None:
    if not song_name.strip():
        raise PreflightCheckError("Save the Ableton set with a name, then click Try Again.")
    if not project_folder.exists() or not project_folder.is_dir():
        raise PreflightCheckError("Project folder does not exist. Save the Ableton project first.")


def check_accessibility_access(script_runner: Callable[[str, int], str]) -> None:
    result = script_runner(
        '''
tell application "System Events"
    if not (exists process "Live") then
        return "missing"
    end if
    tell process "Live"
        return (count of windows) as string
    end tell
end tell''',
        timeout=5,
    )
    if not result.isdigit() or int(result) < 1:
        raise PreflightCheckError(
            "Allow Stems in System Settings > Privacy & Security > Accessibility, then click Try Again. If running from source, allow your Python app or terminal instead."
        )


def run_export_preflight(
    *,
    ableton_client,
    project_folder: Path,
    song_name: str,
    app_path_finder: Callable[[], str | None],
    script_runner: Callable[[str, int], str],
) -> None:
    check_ableton_running(app_path_finder)
    check_osc_reachable(ableton_client)
    check_project_saved(project_folder, song_name)
    check_accessibility_access(script_runner)
