from pathlib import Path

from PySide6.QtWidgets import QComboBox, QDialog

from sn_manager.app.services import SnService
from sn_manager.db import master_data as md
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_filter_fields_are_combos_with_blank(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    win = MainWindow(SnService(conn))
    assert isinstance(win._model_combo, QComboBox)
    assert win._model_combo.isEditable() is False
    assert win._model_combo.itemText(0) == ""
    assert win._model_combo.itemData(0) in (None, "")
    assert win._model_combo.findData("SVG14") > 0
    assert "SVG14 示例外壳机" in [
        win._model_combo.itemText(i) for i in range(win._model_combo.count())
    ]


def test_build_criteria_uses_combo_data(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "05", "第五批")
    win = MainWindow(SnService(conn))
    win._model_combo.setCurrentIndex(win._model_combo.findData("SVG14"))
    win._batch_combo.setCurrentIndex(win._batch_combo.findData("05"))
    win._factory_combo.setCurrentIndex(win._factory_combo.findData("1"))
    win._market_combo.setCurrentIndex(win._market_combo.findData("0"))
    criteria = win._build_criteria()
    assert criteria["product_model"] == "SVG14"
    assert criteria["hw_batch"] == "05"
    assert criteria["factory"] == "1"
    assert criteria["market"] == "0"


def test_master_data_accept_reloads_filter_combos(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    win = MainWindow(svc)

    class _AcceptDialog:
        def __init__(self, service, parent=None) -> None:
            md.upsert_product(service.conn, "ZZZ99", "新机")

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("sn_manager.gui.main_window.MasterDataDialog", _AcceptDialog)
    win._on_master_data()
    assert win._model_combo.findData("ZZZ99") > 0
