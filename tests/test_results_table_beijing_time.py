from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow, _TABLE_COLUMNS, format_display_timestamp


def test_format_display_timestamp_passthrough_when_utc() -> None:
    raw = "2026-07-31T01:02:03Z"
    assert format_display_timestamp(raw, use_beijing=False) == raw


def test_format_display_timestamp_beijing_from_z() -> None:
    # UTC 01:02:03 → 北京 09:02:03
    assert (
        format_display_timestamp("2026-07-31T01:02:03Z", use_beijing=True)
        == "2026-07-31 09:02:03"
    )


def test_format_display_timestamp_beijing_from_offset() -> None:
    assert (
        format_display_timestamp("2026-07-31T01:02:03+00:00", use_beijing=True)
        == "2026-07-31 09:02:03"
    )


def test_format_display_timestamp_invalid_passthrough() -> None:
    raw = "not-a-timestamp"
    assert format_display_timestamp(raw, use_beijing=True) == raw


def test_table_columns_order() -> None:
    keys = [k for k, _ in _TABLE_COLUMNS]
    assert keys[-4:] == ["seq", "created_at", "status", "updated_at"]
    labels = [lab for _, lab in _TABLE_COLUMNS]
    assert labels[-4:] == ["序号", "创建时间", "状态", "更新时间"]


def test_results_header_label_and_beijing_checkbox_default(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    labels = [
        w.text()
        for w in win.findChildren(QLabel)
        if w.text().startswith("结果表")
    ]
    assert "结果表" in labels
    assert "结果表（可多选）" not in labels
    assert win._beijing_time_cb.isChecked() is True
    assert win._beijing_time_cb.text() == "北京时间"


def test_populate_table_formats_times_when_beijing_checked(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    row = {
        "sn": "A" * 17,
        "product_model": "SVG14",
        "hw_batch": "05",
        "factory": "1",
        "market": "0",
        "prod_year": 2026,
        "prod_month": 7,
        "prod_day": 31,
        "seq": 1,
        "status": "unused",
        "created_at": "2026-07-31T01:02:03Z",
        "updated_at": "2026-07-31T02:03:04Z",
    }
    win._populate_table([row])
    col = {k: i for i, (k, _) in enumerate(_TABLE_COLUMNS)}
    assert win._table.item(0, col["created_at"]).text() == "2026-07-31 09:02:03"
    assert win._table.item(0, col["updated_at"]).text() == "2026-07-31 10:03:04"
    assert win._table.item(0, col["status"]).text() == "未使用"


def test_toggle_beijing_shows_utc_and_restores_selection(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    rows = [
        {
            "sn": f"SN{i:015d}",
            "product_model": "SVG14",
            "hw_batch": "05",
            "factory": "1",
            "market": "0",
            "prod_year": 2026,
            "prod_month": 7,
            "prod_day": 31,
            "seq": i,
            "status": "unused",
            "created_at": "2026-07-31T01:02:03Z",
            "updated_at": "2026-07-31T01:02:03Z",
        }
        for i in (1, 2)
    ]
    win._rows = rows
    win._populate_table(rows)
    win._table.selectRow(1)
    assert win._selected_sns() == ["SN000000000000002"]

    win._beijing_time_cb.setChecked(False)
    col = {k: i for i, (k, _) in enumerate(_TABLE_COLUMNS)}
    assert win._table.item(0, col["created_at"]).text() == "2026-07-31T01:02:03Z"
    assert win._selected_sns() == ["SN000000000000002"]
