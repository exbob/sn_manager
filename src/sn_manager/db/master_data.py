"""主数据 CRUD。"""

from __future__ import annotations

import sqlite3
from typing import Any

from sn_manager.core.errors import ValidationError

_MASTER_TABLES = frozenset({"product_models", "hardware_batches", "factories", "markets"})

_REF_COLUMN: dict[str, str] = {
    "product_models": "product_model",
    "hardware_batches": "hw_batch",
    "factories": "factory",
    "markets": "market",
}


def list_codes(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    """列出指定主数据表的 code 字段（含 name 列时一并返回）。"""
    if table not in _MASTER_TABLES:
        raise ValueError(f"unknown master table: {table}")
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY code").fetchall()
    return [dict(row) for row in rows]


def list_product_models(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_codes(conn, "product_models")


def list_hardware_batches(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_codes(conn, "hardware_batches")


def list_factories(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_codes(conn, "factories")


def list_markets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_codes(conn, "markets")


def upsert_product(conn: sqlite3.Connection, code: str) -> None:
    """插入或更新产品型号（编码转大写）。"""
    normalized = code.upper()
    conn.execute(
        "INSERT OR REPLACE INTO product_models (code) VALUES (?)",
        (normalized,),
    )
    conn.commit()


def add_product_model(conn: sqlite3.Connection, code: str) -> None:
    upsert_product(conn, code)


def upsert_hardware_batch(conn: sqlite3.Connection, code: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO hardware_batches (code) VALUES (?)",
        (code,),
    )
    conn.commit()


def add_hardware_batch(conn: sqlite3.Connection, code: str) -> None:
    upsert_hardware_batch(conn, code)


def upsert_factory(conn: sqlite3.Connection, code: str, name: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO factories (code, name) VALUES (?, ?)",
        (code, name),
    )
    conn.commit()


def upsert_market(conn: sqlite3.Connection, code: str, name: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO markets (code, name) VALUES (?, ?)",
        (code, name),
    )
    conn.commit()


def _assert_not_referenced(conn: sqlite3.Connection, table: str, code: str) -> None:
    column = _REF_COLUMN[table]
    row = conn.execute(
        f"SELECT 1 FROM serial_numbers WHERE {column} = ? LIMIT 1",
        (code,),
    ).fetchone()
    if row is not None:
        raise ValidationError(f"编码 {code} 已被序列号引用，无法删除")


def delete_product_model(conn: sqlite3.Connection, code: str) -> None:
    _assert_not_referenced(conn, "product_models", code)
    conn.execute("DELETE FROM product_models WHERE code = ?", (code,))
    conn.commit()


def delete_hardware_batch(conn: sqlite3.Connection, code: str) -> None:
    _assert_not_referenced(conn, "hardware_batches", code)
    conn.execute("DELETE FROM hardware_batches WHERE code = ?", (code,))
    conn.commit()


def delete_factory(conn: sqlite3.Connection, code: str) -> None:
    _assert_not_referenced(conn, "factories", code)
    conn.execute("DELETE FROM factories WHERE code = ?", (code,))
    conn.commit()


def delete_market(conn: sqlite3.Connection, code: str) -> None:
    _assert_not_referenced(conn, "markets", code)
    conn.execute("DELETE FROM markets WHERE code = ?", (code,))
    conn.commit()
