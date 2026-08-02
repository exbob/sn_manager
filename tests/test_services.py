from datetime import date
from pathlib import Path

import pytest

from sn_manager.app.services import MasterSnapshot, SnService
from sn_manager.core.errors import ValidationError
from sn_manager.db import master_data as md
from sn_manager.db.connection import connect


def test_generate_and_filter(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "SVG14", "05", "第五批")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="svg14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    assert len(rows) == 1
    assert rows[0]["sn"] == "ASVG140521261C000"
    found = svc.filter(product_model="SVG14")
    assert len(found) == 1


def test_generate_rejects_batch_not_under_model(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_product(conn, "SCP4A", "采集器")
    md.upsert_hardware_batch(conn, "SCP4A", "05", "别的批次")
    svc = SnService(conn)
    with pytest.raises(ValidationError, match="不属于该产品型号"):
        svc.generate(
            product_model="SVG14",
            hw_batch="05",
            factory="2",
            market="1",
            prod_date=date(2026, 1, 12),
            count=1,
        )


def test_generate_rejects_missing_master_pair(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    with pytest.raises(ValidationError, match="不属于该产品型号"):
        svc.generate(
            product_model="SVG14",
            hw_batch="05",
            factory="2",
            market="1",
            prod_date=date(2026, 1, 12),
            count=1,
        )
    assert md.list_product_models(conn) == []
    assert md.list_hardware_batches(conn) == []


def _insert_serial_referencing_svg14(conn) -> None:
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


def test_replace_master_data_rolls_back_on_referenced_delete(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_product(conn, "OTHER", "其它")
    _insert_serial_referencing_svg14(conn)

    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=[("OTHER", "其它")],
        hardware_batches=[],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    with pytest.raises(ValidationError, match="已被序列号引用"):
        svc.replace_master_data(snapshot)

    codes = {r["code"] for r in md.list_product_models(conn)}
    assert codes == {"SVG14", "OTHER"}


def test_replace_master_data_rejects_invalid_product_code(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    before = md.list_product_models(conn)
    snapshot = MasterSnapshot(
        product_models=[("ABC", "短")],
        hardware_batches=[],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    with pytest.raises(ValidationError, match="产品型号长度必须为5"):
        svc.replace_master_data(snapshot)
    assert md.list_product_models(conn) == before


def test_replace_master_data_rejects_long_name(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=[("SVG14", "中" * 65)],
        hardware_batches=[],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    with pytest.raises(ValidationError, match="名称长度不能超过64"):
        svc.replace_master_data(snapshot)


def test_replace_master_data_with_scoped_batches(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=[("SVG14", "示波器"), ("SCP4A", "采集器")],
        hardware_batches=[
            ("SVG14", "01", "国产化FPGA"),
            ("SCP4A", "01", "国产Wi-Fi模块"),
        ],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    svc.replace_master_data(snapshot)
    assert [(r["code"], r["name"]) for r in md.list_hardware_batches(conn, "SVG14")] == [
        ("01", "国产化FPGA")
    ]
    assert [(r["code"], r["name"]) for r in md.list_hardware_batches(conn, "SCP4A")] == [
        ("01", "国产Wi-Fi模块")
    ]


def test_replace_master_data_clears_model_and_batches(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示波器")
    md.upsert_hardware_batch(conn, "SVG14", "01", "一批")
    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=[],
        hardware_batches=[],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    svc.replace_master_data(snapshot)
    assert md.list_product_models(conn) == []
    assert md.list_hardware_batches(conn) == []
