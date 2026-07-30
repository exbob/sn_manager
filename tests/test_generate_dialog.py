from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QDialog, QMessageBox

from sn_manager.app.services import SnService
from sn_manager.core.version_a import SnFields, encode_version_a
from sn_manager.db.connection import connect
from sn_manager.gui.generate_dialog import GenerateDialog, GenerateParams
from sn_manager.gui.main_window import MainWindow


def test_generate_dialog_loads_seed_master_data(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    dlg = GenerateDialog(svc)
    assert dlg._factory_combo.count() == 2
    assert dlg._market_combo.count() == 4


def test_generate_dialog_returns_params_on_accept(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    dlg = GenerateDialog(svc)
    dlg._model_combo.setCurrentText("svg14")
    dlg._batch_combo.setCurrentText("05")
    dlg._factory_combo.setCurrentIndex(0)
    dlg._market_combo.setCurrentIndex(0)
    dlg._date_edit.setDate(dlg._date_edit.date())
    dlg._count_spin.setValue(3)
    dlg._on_accept()
    params = dlg.params()
    assert params == GenerateParams(
        product_model="svg14",
        hw_batch="05",
        factory=dlg._factory_combo.currentData(),
        market=dlg._market_combo.currentData(),
        prod_date=date(
            dlg._date_edit.date().year(),
            dlg._date_edit.date().month(),
            dlg._date_edit.date().day(),
        ),
        count=3,
    )


class _AcceptedGenerateDialog:
    def __init__(self, service: SnService, parent=None) -> None:
        self._params = GenerateParams(
            product_model="SVG14",
            hw_batch="05",
            factory="2",
            market="1",
            prod_date=date(2026, 1, 12),
            count=1,
        )

    def exec(self) -> QDialog.DialogCode:
        return QDialog.DialogCode.Accepted

    def params(self) -> GenerateParams:
        return self._params


def test_main_window_generate_replaces_table_and_selects(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    win = MainWindow(svc)
    monkeypatch.setattr(
        "sn_manager.gui.main_window.GenerateDialog",
        _AcceptedGenerateDialog,
    )
    win._on_generate()
    assert win._table.rowCount() == 1
    assert len(win._selected_sns()) == 1
    assert win._selected_sns()[0] == "ASVG140521261C000"


def test_main_window_generate_sequence_exhausted_warning(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    fields = SnFields(
        version="A",
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_year=2026,
        prod_month=1,
        prod_day=2,
        seq=4095,
    )
    sn = encode_version_a(fields)
    conn.execute(
        "INSERT INTO serial_numbers(sn, version, product_model, hw_batch, factory, market, "
        "prod_year, prod_month, prod_day, seq, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sn, "A", "ABC12", "01", "1", "0", 2026, 1, 2, 4095, "unused", "t", "t"),
    )
    conn.commit()

    class _ExhaustDialog:
        def __init__(self, service: SnService, parent=None) -> None:
            self._params = GenerateParams(
                product_model="ABC12",
                hw_batch="01",
                factory="1",
                market="0",
                prod_date=date(2026, 1, 2),
                count=1,
            )

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def params(self) -> GenerateParams:
            return self._params

    warnings: list[tuple] = []

    def _capture_warning(*args):
        warnings.append(args)

    monkeypatch.setattr(
        "sn_manager.gui.main_window.GenerateDialog",
        _ExhaustDialog,
    )
    monkeypatch.setattr(QMessageBox, "warning", _capture_warning)

    win = MainWindow(SnService(conn))
    win._on_generate()
    assert win._table.rowCount() == 0
    assert warnings
    assert warnings[0][2] == "序号已用尽，请更换生产日期或硬件批次"
