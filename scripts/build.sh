#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

./scripts/git-version.sh > app_version.txt

uv run pyinstaller \
  --noconfirm \
  --windowed \
  --name sn-manager \
  --paths src \
  --collect-submodules PySide6 \
  --add-data "app_version.txt:." \
  src/sn_manager/__main__.py

cp -f docs/user-manual.md dist/sn-manager/user-manual.md

echo "Built: dist/sn-manager/sn-manager"
