# AGENTS.md

## Commands
- Install runtime deps with `python3 -m pip install -r requirements.txt`.
- Install editable dev deps with `python3 -m pip install -e ".[dev]"`.
- Run the UI directly with `python3 run_ui.py`.
- Run all tests with `python3 -m pytest`.
- Run a focused test file with `python3 -m pytest tests/test_export.py`.
- Run a single test with `python3 -m pytest tests/test_export.py -k retries`.
- Build the macOS app bundle with `./build_app.sh`; this runs `PyInstaller` against `Stems.spec` and produces `dist/Stems.app`.

## Architecture
- This is a single Python package repo, not a monorepo. Core code lives under `stems/`; tests live under `tests/`.
- GUI entrypoint is `run_ui.py`, which calls `stems.ui.app:main`; packaged app builds from that same file via `Stems.spec`.
- CLI entrypoint is `stems.cli:main` (`c4milo-stems` in `pyproject.toml`).
- The main UI is `stems/ui/main_window.py`; scanning and export run in `QThread` workers from `stems/ui/worker.py`.
- Scan flow is `AppState.scan_current_set()` -> Ableton OSC track query -> bus detection -> project lookup.
- Export flow is `execute_export_job()` in `stems/export.py`; it runs preflight checks, solos tracks one at a time, then automates Ableton's export/save dialogs.

## Repo-Specific Behavior
- Stem detection is intentionally name-based: `stems/detection.py` only treats ALL-CAPS bus names as stems and excludes `PRINT`, `MIXBUS`, `REF`, and `MASTER`.
- Project detection is macOS-specific: `stems/project.py` reads Ableton's front window title via `osascript`, tries `mdfind` for `<song>.als`, then falls back to `find` under common user folders.
- Export automation is also macOS-specific: `stems/export.py` and `stems/automation.py` depend on `osascript`, `open`, and `pyautogui` controlling Ableton's UI.
- Preflight requires all of the following to work: Ableton Live running, AbletonOSC reachable, the project saved on disk, and macOS Accessibility permission for UI scripting.
- User preferences are persisted at `~/.stems_ableton/preferences.json`.
- "Launch at login" writes `~/Library/LaunchAgents/com.c4milo.stems.plist`.

## Verification Notes
- There is no repo-configured lint, formatter, or typecheck command. The only verified automated check in repo config is `pytest`.
- Tests are unit-style and heavily fake Ableton/GUI integrations; they verify packaging, naming, detection, state, and export logic without requiring Ableton Live.
- `build/` and `dist/` are generated PyInstaller outputs. Do not hand-edit them; change sources or `Stems.spec` and rebuild instead.
