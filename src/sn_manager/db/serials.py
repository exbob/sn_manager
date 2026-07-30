"""序列号分配、查询与状态更新。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from sn_manager.core.errors import SequenceExhaustedError
from sn_manager.core.status import Status
from sn_manager.core.version_a import SnFields, encode_version_a, validate_generation_input

SEQ_MAX = 4095

_FILTER_COLUMNS = frozenset(
    {
        "sn",
        "product_model",
        "hw_batch",
        "factory",
        "market",
        "prod_year",
        "prod_month",
        "prod_day",
        "status",
    }
)

_UPPERCASE_FILTERS = frozenset({"product_model", "hw_batch", "factory", "market", "sn"})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_to_ordinal(d: date) -> int:
    return d.year * 10_000 + d.month * 100 + d.day


def allocate_and_insert(
    conn: sqlite3.Connection,
    *,
    product_model: str,
    hw_batch: str,
    factory: str,
    market: str,
    prod_date: date,
    count: int,
) -> list[str]:
    """在同一写事务中分配序号并插入 serial_numbers 行。"""
    if count < 1:
        raise ValueError("count must be >= 1")

    normalized = validate_generation_input(
        product_model=product_model,
        hw_batch=hw_batch,
        factory=factory,
        market=market,
        prod_date=prod_date,
    )

    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            """
            SELECT MAX(seq) AS max_seq
            FROM serial_numbers
            WHERE product_model = ?
              AND hw_batch = ?
              AND prod_year = ?
              AND prod_month = ?
              AND prod_day = ?
            """,
            (
                normalized.product_model,
                normalized.hw_batch,
                prod_date.year,
                prod_date.month,
                prod_date.day,
            ),
        ).fetchone()
        max_seq = row["max_seq"]
        start = (max_seq if max_seq is not None else -1) + 1
        end = start + count - 1
        if end > SEQ_MAX:
            raise SequenceExhaustedError()

        now = _utc_now_iso()
        sns: list[str] = []
        for seq in range(start, start + count):
            fields = SnFields(
                version=normalized.version,
                product_model=normalized.product_model,
                hw_batch=normalized.hw_batch,
                factory=normalized.factory,
                market=normalized.market,
                prod_year=prod_date.year,
                prod_month=prod_date.month,
                prod_day=prod_date.day,
                seq=seq,
            )
            sn = encode_version_a(fields)
            conn.execute(
                """
                INSERT INTO serial_numbers (
                    sn, version, product_model, hw_batch, factory, market,
                    prod_year, prod_month, prod_day, seq, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sn,
                    fields.version,
                    fields.product_model,
                    fields.hw_batch,
                    fields.factory,
                    fields.market,
                    fields.prod_year,
                    fields.prod_month,
                    fields.prod_day,
                    fields.seq,
                    Status.UNUSED,
                    now,
                    now,
                ),
            )
            sns.append(sn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return sns


def filter_serials(conn: sqlite3.Connection, **filters: Any) -> list[dict[str, Any]]:
    """按可选条件筛选 serial_numbers，返回字典列表。"""
    conditions: list[str] = []
    params: list[Any] = []

    for key, value in filters.items():
        if value is None:
            continue
        if key in _FILTER_COLUMNS:
            if key in _UPPERCASE_FILTERS and isinstance(value, str):
                value = value.upper()
            conditions.append(f"{key} = ?")
            params.append(value)
        elif key == "prod_date_from":
            conditions.append(
                "(prod_year * 10000 + prod_month * 100 + prod_day) >= ?"
            )
            params.append(_date_to_ordinal(value))
        elif key == "prod_date_to":
            conditions.append(
                "(prod_year * 10000 + prod_month * 100 + prod_day) <= ?"
            )
            params.append(_date_to_ordinal(value))
        else:
            raise ValueError(f"unknown filter: {key}")

    sql = "SELECT * FROM serial_numbers"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC, sn"

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def update_statuses(
    conn: sqlite3.Connection,
    sns: list[str],
    status: Status,
) -> int:
    """批量更新 SN 状态，返回受影响行数。"""
    if not sns:
        return 0

    now = _utc_now_iso()
    placeholders = ", ".join("?" for _ in sns)
    cursor = conn.execute(
        f"""
        UPDATE serial_numbers
        SET status = ?, updated_at = ?
        WHERE sn IN ({placeholders})
        """,
        [status.value, now, *sns],
    )
    conn.commit()
    return cursor.rowcount
