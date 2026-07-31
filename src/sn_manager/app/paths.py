"""应用层路径约定。"""

from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    """可执行文件所在目录；开发未打包时为当前工作目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def default_db_path() -> Path:
    """返回默认 SQLite 数据库路径。"""
    return app_dir() / "sn_manager.db"
