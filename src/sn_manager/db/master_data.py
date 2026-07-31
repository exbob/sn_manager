"""主数据 CRUD。"""

from __future__ import annotations

import sqlite3
from typing import Any

from sn_manager.core.errors import ValidationError
from sn_manager.core.version_a import normalize_alnum

_MASTER_TABLES = frozenset({"product_models", "hardware_batches", "factories", "markets"})

_REF_COLUMN: dict[str, str] = {
    "product_models": "product_model",
    "hardware_batches": "hw_batch",
    "factories": "factory",
    "markets": "market",
}


def validate_product_code(code: str) -> str:
    """校验产品型号编码（5 位字母数字）。"""
    return normalize_alnum(code, "产品型号", 5)


def validate_hardware_batch_code(code: str) -> str:
    """校验硬件批次编码（2 位字母数字）。"""
    return normalize_alnum(code, "硬件批次", 2)


def validate_factory_code(code: str) -> str:
    """校验生产单位编码（1 位字母数字）。"""
    return normalize_alnum(code, "生产单位", 1)


def validate_market_code(code: str) -> str:
    """校验投放市场编码（1 位字母数字）。"""
    return normalize_alnum(code, "投放市场", 1)


NAME_MAX_LENGTH = 64


def validate_name(name: str, field_label: str = "名称") -> str:
    """校验主数据名称：去首尾空白后非空，且长度不超过 NAME_MAX_LENGTH。"""
    normalized = name.strip()
    if not normalized:
        raise ValidationError(f"{field_label}不能为空")
    if len(normalized) > NAME_MAX_LENGTH:
        raise ValidationError(f"{field_label}长度不能超过{NAME_MAX_LENGTH}")
    return normalized


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


def _maybe_commit(conn: sqlite3.Connection, *, commit: bool) -> None:
    if commit:
        conn.commit()


def upsert_product(
    conn: sqlite3.Connection, code: str, name: str, *, commit: bool = True
) -> None:
    """插入或更新产品型号（编码转大写并校验；名称必填）。"""
    normalized = validate_product_code(code)
    conn.execute(
        "INSERT OR REPLACE INTO product_models (code, name) VALUES (?, ?)",
        (normalized, validate_name(name)),
    )
    _maybe_commit(conn, commit=commit)


def add_product_model(conn: sqlite3.Connection, code: str, name: str) -> None:
    upsert_product(conn, code, name)


def upsert_hardware_batch(
    conn: sqlite3.Connection, code: str, name: str, *, commit: bool = True
) -> None:
    normalized = validate_hardware_batch_code(code)
    conn.execute(
        "INSERT OR REPLACE INTO hardware_batches (code, name) VALUES (?, ?)",
        (normalized, validate_name(name)),
    )
    _maybe_commit(conn, commit=commit)


def add_hardware_batch(conn: sqlite3.Connection, code: str, name: str) -> None:
    upsert_hardware_batch(conn, code, name)


def upsert_factory(
    conn: sqlite3.Connection, code: str, name: str, *, commit: bool = True
) -> None:
    normalized = validate_factory_code(code)
    conn.execute(
        "INSERT OR REPLACE INTO factories (code, name) VALUES (?, ?)",
        (normalized, validate_name(name)),
    )
    _maybe_commit(conn, commit=commit)


def upsert_market(
    conn: sqlite3.Connection, code: str, name: str, *, commit: bool = True
) -> None:
    normalized = validate_market_code(code)
    conn.execute(
        "INSERT OR REPLACE INTO markets (code, name) VALUES (?, ?)",
        (normalized, validate_name(name)),
    )
    _maybe_commit(conn, commit=commit)


def _assert_not_referenced(conn: sqlite3.Connection, table: str, code: str) -> None:
    column = _REF_COLUMN[table]
    row = conn.execute(
        f"SELECT 1 FROM serial_numbers WHERE {column} = ? LIMIT 1",
        (code,),
    ).fetchone()
    if row is not None:
        raise ValidationError(f"编码 {code} 已被序列号引用，无法删除")


def delete_product_model(
    conn: sqlite3.Connection, code: str, *, commit: bool = True
) -> None:
    normalized = code.upper()
    _assert_not_referenced(conn, "product_models", normalized)
    conn.execute("DELETE FROM product_models WHERE code = ?", (normalized,))
    _maybe_commit(conn, commit=commit)


def delete_hardware_batch(
    conn: sqlite3.Connection, code: str, *, commit: bool = True
) -> None:
    normalized = code.upper()
    _assert_not_referenced(conn, "hardware_batches", normalized)
    conn.execute("DELETE FROM hardware_batches WHERE code = ?", (normalized,))
    _maybe_commit(conn, commit=commit)


def delete_factory(conn: sqlite3.Connection, code: str, *, commit: bool = True) -> None:
    normalized = code.upper()
    _assert_not_referenced(conn, "factories", normalized)
    conn.execute("DELETE FROM factories WHERE code = ?", (normalized,))
    _maybe_commit(conn, commit=commit)


def delete_market(conn: sqlite3.Connection, code: str, *, commit: bool = True) -> None:
    normalized = code.upper()
    _assert_not_referenced(conn, "markets", normalized)
    conn.execute("DELETE FROM markets WHERE code = ?", (normalized,))
    _maybe_commit(conn, commit=commit)
