#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

uv run pyinstaller \
  --noconfirm \
  --windowed \
  --name sn-manager \
  --paths src \
  --collect-submodules PySide6 \
  src/sn_manager/__main__.py

echo "Built: dist/sn-manager/sn-manager"
