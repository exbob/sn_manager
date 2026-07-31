from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def _sample_rows(sns: list[str]) -> list[dict]:
    return [
        {
            "sn": sn,
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
        for i, sn in enumerate(sns, start=1)
    ]


def test_count_label_zero_on_startup(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    assert win._count_label.text() == "共 0 条，已选 0 条"


def test_count_label_after_populate_and_select(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    rows = _sample_rows(
        ["SN000000000000001", "SN000000000000002", "SN000000000000003"]
    )
    win._rows = rows
    win._populate_table(rows)
    assert win._count_label.text() == "共 3 条，已选 0 条"

    model = win._table.selectionModel()
    table_model = win._table.model()
    assert model is not None and table_model is not None
    model.clearSelection()
    for row_idx in (0, 2):
        model.select(
            table_model.index(row_idx, 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
    assert win._count_label.text() == "共 3 条，已选 2 条"

    win._on_select_all()
    assert win._count_label.text() == "共 3 条，已选 3 条"

    model.clearSelection()
    assert win._count_label.text() == "共 3 条，已选 0 条"
