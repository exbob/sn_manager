from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from sn_manager.app.services import SnService
from sn_manager.core.status import Status
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow, _TABLE_COLUMNS


def _status_col() -> int:
    return next(i for i, (key, _) in enumerate(_TABLE_COLUMNS) if key == "status")


def _row(sn: str, status: str) -> dict:
    data = {key: "" for key, _ in _TABLE_COLUMNS}
    data["sn"] = sn
    data["status"] = status
    return data


def test_status_column_colors(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win._populate_table(
        [
            _row("A1", Status.UNUSED.value),
            _row("A2", Status.USED.value),
            _row("A3", Status.VOID.value),
        ]
    )
    col = _status_col()
    unused = win._table.item(0, col)
    used = win._table.item(1, col)
    void = win._table.item(2, col)
    assert unused is not None and used is not None and void is not None
    assert unused.data(Qt.ItemDataRole.ForegroundRole) is None
    assert used.foreground().color() == QColor("#2E7D32")
    assert void.foreground().color() == QColor("#C62828")
