#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

VERSION=""
if command -v git >/dev/null 2>&1; then
        VERSION="$(git -C "${ROOT_DIR}" describe --tags --always --long 2>/dev/null || true)"
fi

if [[ -z "${VERSION:-}" ]]; then
        VERSION="unknown"
fi

printf "%s\n" "${VERSION}"
