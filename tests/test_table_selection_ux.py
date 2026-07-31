from pathlib import Path

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_results_table_selection_stylesheet(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    ss = win._table.styleSheet().replace(" ", "")
    assert "#87CEFA" in ss
    assert "item:focus" in ss
    assert "outline:none" in ss
