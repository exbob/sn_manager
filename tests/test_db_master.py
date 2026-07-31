from pathlib import Path

import pytest

from sn_manager.core.errors import ValidationError
from sn_manager.db import master_data as md
from sn_manager.db.connection import connect


def test_seed_factories_and_markets(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    factories = md.list_factories(conn)
    assert {f["code"] for f in factories} >= {"1", "2"}
    markets = md.list_markets(conn)
    assert {m["code"] for m in markets} >= {"0", "1", "2", "3"}


def test_add_and_list_product(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "svg14", "示例外壳机")
    row = md.list_product_models(conn)[0]
    assert row["code"] == "SVG14"
    assert row["name"] == "示例外壳机"


def test_upsert_rejects_empty_product_name(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="名称不能为空"):
        md.upsert_product(conn, "SVG14", "  ")


def test_upsert_rejects_long_product_name(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="名称长度不能超过64"):
        md.upsert_product(conn, "SVG14", "中" * 65)


def test_upsert_factory_rejects_long_name(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="名称长度不能超过64"):
        md.upsert_factory(conn, "9", "x" * 65)


def test_delete_product_referenced_by_serial_raises(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "测试型号")
    conn.execute(
        "INSERT INTO serial_numbers("
        "sn, version, product_model, hw_batch, factory, market, "
        "prod_year, prod_month, prod_day, seq, status, created_at, updated_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "ASVG140521261CF000",
            "A",
            "SVG14",
            "05",
            "1",
            "0",
            2026,
            1,
            2,
            0,
            "unused",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
        ),
    )
    conn.commit()
    with pytest.raises(ValidationError, match="已被序列号引用"):
        md.delete_product_model(conn, "SVG14")


def test_delete_unreferenced_product(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "ABC12", "测试型号")
    md.delete_product_model(conn, "ABC12")
    assert md.list_product_models(conn) == []


def test_delete_product_accepts_lowercase_code(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "ABC12", "测试型号")
    md.delete_product_model(conn, "abc12")
    assert md.list_product_models(conn) == []


def test_upsert_rejects_invalid_product_code(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="产品型号长度必须为5"):
        md.upsert_product(conn, "ABC", "短")
    assert md.list_product_models(conn) == []


def test_upsert_rejects_non_alnum_batch(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="硬件批次只能包含字母和数字"):
        md.upsert_hardware_batch(conn, "0!", "坏批次")
    assert md.list_hardware_batches(conn) == []
