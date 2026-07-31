"""应用版本解析（界面展示用，与 scripts/git-version.sh 同格式）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_APP_VERSION_NAME = "app_version.txt"
_MAX_WALK_UP = 8


def _read_version_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def _walk_app_version_files() -> list[Path]:
    """开发态候选路径：cwd，再从本模块向上最多 _MAX_WALK_UP 层。"""
    candidates: list[Path] = []
    cwd_file = Path.cwd() / _APP_VERSION_NAME
    candidates.append(cwd_file)
    here = Path(__file__).resolve().parent
    for i, parent in enumerate([here, *here.parents]):
        if i > _MAX_WALK_UP:
            break
        path = parent / _APP_VERSION_NAME
        if path not in candidates:
            candidates.append(path)
    return candidates


def _git_describe(cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "describe", "--tags", "--always", "--long"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    text = (completed.stdout or "").strip()
    return text or None


def resolve_app_version() -> str:
    """返回界面用版本字符串；永不抛给调用方。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            found = _read_version_file(Path(meipass) / _APP_VERSION_NAME)
            if found is not None:
                return found
    else:
        for path in _walk_app_version_files():
            found = _read_version_file(path)
            if found is not None:
                return found

    described = _git_describe(Path.cwd())
    if described is not None:
        return described
    return "unknown"
