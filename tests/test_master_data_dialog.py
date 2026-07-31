from pathlib import Path

from PySide6.QtWidgets import QAbstractItemView, QDialog, QMessageBox, QTableWidgetItem

from sn_manager.app.services import MasterSnapshot, SnService
from sn_manager.db import master_data as md
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow
from sn_manager.gui.master_data_dialog import MasterDataDialog
from sn_manager.gui.no_focus_delegate import NoFocusDelegate


def test_master_data_dialog_loads_seed_data(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    dlg = MasterDataDialog(svc)
    assert dlg._factory_table.rowCount() == 2
    assert dlg._market_table.rowCount() == 4


def test_master_data_dialog_cancel_does_not_write(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    dlg = MasterDataDialog(svc)
    dlg._add_row(dlg._model_table)
    row = dlg._model_table.rowCount() - 1
    dlg._model_table.setItem(row, 0, QTableWidgetItem("NEW01"))
    dlg.reject()
    assert md.list_product_models(conn) == []


def test_master_data_dialog_accept_writes_new_model(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    dlg = MasterDataDialog(svc)
    dlg._add_row(dlg._model_table)
    row = dlg._model_table.rowCount() - 1
    dlg._model_table.setItem(row, 0, QTableWidgetItem("svg14"))
    dlg._on_accept()
    assert [r["code"] for r in md.list_product_models(conn)] == ["SVG14"]


def test_master_data_dialog_referenced_delete_keeps_open(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14")
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

    svc = SnService(conn)
    dlg = MasterDataDialog(svc)
    dlg._model_table.setRowCount(0)

    warnings: list[tuple] = []

    def _capture_warning(*args):
        warnings.append(args)

    monkeypatch.setattr(QMessageBox, "warning", _capture_warning)
    dlg._on_accept()

    assert dlg.result() != QDialog.DialogCode.Accepted
    assert warnings
    assert "已被序列号引用" in warnings[0][2]
    assert [r["code"] for r in md.list_product_models(conn)] == ["SVG14"]


def test_apply_master_data_alias(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=["ABC12"],
        hardware_batches=["01"],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    svc.apply_master_data(snapshot)
    assert [r["code"] for r in md.list_product_models(conn)] == ["ABC12"]


def test_main_window_master_data_opens_dialog(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    win = MainWindow(svc)
    opened: list[bool] = []

    class _StubDialog:
        def __init__(self, service: SnService, parent=None) -> None:
            opened.append(True)

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("sn_manager.gui.main_window.MasterDataDialog", _StubDialog)
    win._on_master_data()
    assert opened == [True]


def test_master_tables_use_no_focus_delegate(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    dlg = MasterDataDialog(SnService(conn))
    for table in (
        dlg._model_table,
        dlg._batch_table,
        dlg._factory_table,
        dlg._market_table,
    ):
        assert isinstance(table.itemDelegate(), NoFocusDelegate)
        assert "#87CEFA" not in table.styleSheet()


def test_master_add_row_starts_editing_first_cell(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    dlg = MasterDataDialog(SnService(conn))
    table = dlg._model_table
    before = table.rowCount()
    dlg._add_row(table)
    assert table.rowCount() == before + 1
    assert table.currentRow() == before
    assert table.currentColumn() == 0
    assert table.state() == QAbstractItemView.State.EditingState
