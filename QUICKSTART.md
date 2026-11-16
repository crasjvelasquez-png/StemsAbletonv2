# Stems App Quick Start

## Open the built app

If the app bundle already exists:

```bash
open dist/Stems.app
```

## Build the app first

If `dist/Stems.app` does not exist yet:

```bash
./build_app.sh
open dist/Stems.app
```

## Run without building

If you want to launch it directly from Python instead of the app bundle:

```bash
python3 run_ui.py
```

## First-run checklist

1. Open Ableton Live.
2. Load or save your project.
3. Make sure AbletonOSC is enabled in Ableton Preferences.
4. If macOS asks for permissions, allow Accessibility / Automation access.
5. Launch the app.

## If it does not open

Try these in order:

```bash
python3 -m pytest
python3 run_ui.py
```

If the built app fails but the Python version works, rebuild it:

```bash
./build_app.sh
```

## Export stems

1. Name the tracks or groups you want exported in ALL CAPS. PRINT, MIXBUS, REF, and MASTER are excluded.
2. Open Stems. It checks the current set automatically; any setup problem appears with a fix and a **Try Again** button.
3. Leave all stems checked, or uncheck the ones you do not need. Enter a key or song-name override if needed.
4. Click **Export Stems** once. Stems refreshes the set before exporting. If the set or track list changed, review the refreshed list and click Export again.
5. Leave the keyboard and mouse free while Ableton exports. Cancel stops after the current stem; moving the pointer to a screen corner stops the next keyboard/mouse automation action.

Exports stay inside the detected Ableton project folder and replace files with the same names. Click **Saves to** or **Open Folder** to reveal the destination (or the existing parent folder before the first export).

Preferences contain three file-name styles, three folder-name styles, and an option to open the folder after export. Window size and position are always remembered. The app no longer copies results to your clipboard, runs in the menu bar, or launches at login. Existing login registration is removed on the next launch. Retired preferences and export history are discarded on save; custom naming formats fall back to Studio Detail.

## Repeatable UI verification

```bash
python3 scripts/verify_simplified_ui.py
```

This exercises the Qt application with fake Ableton and export integrations. Screenshots and a JSON result are written to `/tmp/stems-ui-verification`. It does not verify live Ableton dialogs, permissions, audio, or the physical corner stop.
