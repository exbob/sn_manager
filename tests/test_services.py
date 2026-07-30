from datetime import date
from pathlib import Path

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect


def test_generate_and_filter(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
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
