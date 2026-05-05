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
