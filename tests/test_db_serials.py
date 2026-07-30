from datetime import date
from pathlib import Path

import pytest

from sn_manager.core.errors import SequenceExhaustedError
from sn_manager.core.status import Status
from sn_manager.db.connection import connect
from sn_manager.db import serials as ser


def test_allocate_sequential(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    sns = ser.allocate_and_insert(
        conn,
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 12, 1),
        count=2,
    )
    assert len(sns) == 2
    assert sns[0].endswith("000")
    assert sns[1].endswith("001")


def test_void_does_not_recycle(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    d = date(2026, 1, 1)
    kwargs = dict(
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_date=d,
    )
    s1 = ser.allocate_and_insert(conn, count=1, **kwargs)[0]
    ser.update_statuses(conn, [s1], Status.VOID)
    s2 = ser.allocate_and_insert(conn, count=1, **kwargs)[0]
    assert s2.endswith("001")


def test_exhaust_raises(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    d = date(2026, 1, 2)
    kwargs = dict(
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_date=d,
    )
    # 直接插入 seq=4095 的边界：先插入 4095 个太慢；改为手工插入 max 行后请求 1
    from sn_manager.core.version_a import SnFields, encode_version_a

    fields = SnFields(
        version="A",
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_year=2026,
        prod_month=1,
        prod_day=2,
        seq=4095,
    )
    sn = encode_version_a(fields)
    conn.execute(
        "INSERT INTO serial_numbers(sn, version, product_model, hw_batch, factory, market, "
        "prod_year, prod_month, prod_day, seq, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sn, "A", "ABC12", "01", "1", "0", 2026, 1, 2, 4095, "unused", "t", "t"),
    )
    conn.commit()
    with pytest.raises(SequenceExhaustedError):
        ser.allocate_and_insert(conn, count=1, **kwargs)
