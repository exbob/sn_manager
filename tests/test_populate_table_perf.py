"""Regression: re-populating results table must not hang (ResizeToContents)."""

from __future__ import annotations

import time
from pathlib import Path

from sn_manager.app.services import SnService
from sn_manager.core.status import Status
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def _rows(n: int) -> list[dict]:
    return [
        {
            "sn": f"SVG1405120260802{i:04X}",
            "product_model": "SVG14",
            "hw_batch": "05",
            "factory": "1",
            "market": "0",
            "prod_year": 2026,
            "prod_month": 8,
            "prod_day": 2,
            "seq": i,
            "created_at": "2026-08-02T10:00:00+00:00",
            "status": Status.UNUSED.value,
            "updated_at": "2026-08-02T10:00:00+00:00",
        }
        for i in range(n)
    ]


def test_populate_table_second_fill_not_pathologically_slow(
    qapp, tmp_path: Path
) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win.show()
    qapp.processEvents()
    rows = _rows(100)
    win._total_count = 100
    win._rows = rows

    t0 = time.perf_counter()
    win._populate_table(rows)
    qapp.processEvents()
    first = time.perf_counter() - t0

    win._table.selectAll()
    qapp.processEvents()

    t0 = time.perf_counter()
    win._populate_table(rows)
    qapp.processEvents()
    second = time.perf_counter() - t0

    assert win._table.rowCount() == 100
    assert win._table.item(0, 0) is not None
    assert win._table.item(0, 0).text() == rows[0]["sn"]
    # Unfixed ResizeToContents re-fill is ~50–100× slower on offscreen;
    # Windows is worse. Allow headroom for noise but catch the pathology.
    limit = max(first * 15, 0.05)
    assert second < limit, (
        f"second populate too slow: first={first:.3f}s second={second:.3f}s "
        f"limit={limit:.3f}s"
    )
