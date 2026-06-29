#!/usr/bin/env bash
set -euo pipefail

python3 "assets/logo/generate_macos_icon.py"
python3 -m PyInstaller --noconfirm --clean "Stems.spec"
codesign --force --deep --sign - "dist/Stems.app"

icon_file="$(plutil -extract CFBundleIconFile raw "dist/Stems.app/Contents/Info.plist")"
if [[ "$icon_file" != "stems-tower.icns" ]]; then
    printf 'Unexpected CFBundleIconFile: %s\n' "$icon_file" >&2
    exit 1
fi
codesign --verify --deep --strict --verbose=2 "dist/Stems.app"

printf '\nBuilt app bundle: %s\n' "$(pwd)/dist/Stems.app"
