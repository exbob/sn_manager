"""应用层路径约定。"""

from __future__ import annotations

import sys
from pathlib import Path

_USER_MANUAL_PACKAGED = "user-manual.md"
_USER_MANUAL_DEV = Path("docs") / "user-manual.md"
_APP_ICON_REL = Path("assets") / "icons" / "sn-manager.png"
_MAX_WALK_UP = 8


def app_dir() -> Path:
    """可执行文件所在目录；开发未打包时为当前工作目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def default_db_path() -> Path:
    """返回默认 SQLite 数据库路径。"""
    return app_dir() / "sn_manager.db"


def resolve_user_manual_path() -> Path | None:
    """返回本地使用手册路径；找不到则 None。"""
    if getattr(sys, "frozen", False):
        candidate = app_dir() / _USER_MANUAL_PACKAGED
        return candidate.resolve() if candidate.is_file() else None

    candidates: list[Path] = [Path.cwd() / _USER_MANUAL_DEV]
    here = Path(__file__).resolve().parent
    for i, parent in enumerate([here, *here.parents]):
        if i > _MAX_WALK_UP:
            break
        path = parent / _USER_MANUAL_DEV
        if path not in candidates:
            candidates.append(path)
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def resolve_app_icon_path() -> Path | None:
    """返回应用图标 PNG 路径；找不到则 None。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if not meipass:
            return None
        candidate = Path(meipass) / _APP_ICON_REL
        return candidate.resolve() if candidate.is_file() else None

    candidates: list[Path] = [Path.cwd() / _APP_ICON_REL]
    here = Path(__file__).resolve().parent
    for i, parent in enumerate([here, *here.parents]):
        if i > _MAX_WALK_UP:
            break
        path = parent / _APP_ICON_REL
        if path not in candidates:
            candidates.append(path)
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None
