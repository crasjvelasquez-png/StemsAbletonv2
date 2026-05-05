#!/usr/bin/env bash
set -euo pipefail

python3 -m PyInstaller --noconfirm --clean "Stems.spec"

printf '\nBuilt app bundle: %s\n' "$(pwd)/dist/Stems.app"
