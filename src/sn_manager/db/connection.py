"""SQLite 连接与初始化。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sn_manager.db.schema import DDL, SEED


def connect(db_path: Path) -> sqlite3.Connection:
    """打开数据库，执行 schema 与种子数据初始化。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    conn.executescript(SEED)
    return conn
