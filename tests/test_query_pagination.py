from __future__ import annotations

from datetime import date
from pathlib import Path

import sn_manager.gui.main_window as mw
from sn_manager.app.services import SnService
from sn_manager.db import master_data as md
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_query_paginates_and_count_is_total(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mw, "PAGE_SIZE", 2)
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "SVG14", "05", "第五批")
    svc = SnService(conn)
    svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="1",
        market="0",
        prod_date=date(2026, 8, 2),
        count=5,
    )
    win = MainWindow(svc)
    win._on_query()
    assert win._total_count == 5
    assert win._table.rowCount() == 2
    assert win._count_label.text() == "共 5 条，已选 0 条"
    assert win._page_label.text() == "第 1 / 3 页"
    assert not win._prev_page_btn.isEnabled()
    assert win._next_page_btn.isEnabled()

    win._on_next_page()
    assert win._page == 2
    assert win._table.rowCount() == 2
    assert win._page_label.text() == "第 2 / 3 页"
    assert win._prev_page_btn.isEnabled()

    win._on_next_page()
    assert win._page == 3
    assert win._table.rowCount() == 1
    assert not win._next_page_btn.isEnabled()

    win._on_select_all()
    assert win._count_label.text() == "共 5 条，已选 1 条"


def test_set_query_busy_updates_chrome(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win._set_query_busy(True)
    assert win._query_btn.text() == "查询中…"
    assert not win._query_btn.isEnabled()
    assert not win._generate_btn.isEnabled()
    assert not win._master_btn.isEnabled()
    assert not win._select_all_btn.isEnabled()
    assert not win._prev_page_btn.isEnabled()
    assert not win._next_page_btn.isEnabled()
    win._set_query_busy(False)
    assert win._query_btn.text() == "查询"
    assert win._query_btn.isEnabled()


def test_generate_uses_memory_pagination(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mw, "PAGE_SIZE", 2)
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "SVG14", "05", "第五批")
    svc = SnService(conn)
    win = MainWindow(svc)
    rows = svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="1",
        market="0",
        prod_date=date(2026, 8, 2),
        count=5,
    )
    win._apply_generated_rows(rows)
    assert win._memory_rows is not None
    assert win._total_count == 5
    assert win._table.rowCount() == 2
    assert len(win._selected_sns()) == 2
    win._on_next_page()
    assert win._page == 2
    assert win._query_btn.text() == "查询"
