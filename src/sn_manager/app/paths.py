"""应用层路径约定。"""

from __future__ import annotations

import sys
from pathlib import Path


def default_db_path() -> Path:
    """返回默认 SQLite 数据库路径。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "sn_manager.db"
    return Path.cwd() / "sn_manager.db"
