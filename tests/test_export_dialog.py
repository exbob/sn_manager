from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from PySide6.QtWidgets import QDialog, QMessageBox

from sn_manager.app.services import SnService
from sn_manager.core.status import Status
from sn_manager.db.connection import connect
from sn_manager.gui.export_dialog import ExportDialog, ExportMode, ExportParams
from sn_manager.gui.main_window import ChangeStatusDialog, MainWindow


def test_export_dialog_returns_excel_params_on_accept(qapp):
    dlg = ExportDialog()
    dlg._excel_radio.setChecked(True)
    dlg._excel_path_edit.setText("/tmp/out.xlsx")
    dlg._on_accept()
    params = dlg.params()
    assert params == ExportParams(
        mode=ExportMode.EXCEL,
        excel_path=Path("/tmp/out.xlsx"),
    )


def test_export_dialog_returns_burn_params_on_accept(qapp):
    dlg = ExportDialog()
    dlg._burn_radio.setChecked(True)
    dlg._burn_dir_edit.setText("/tmp/burn")
    dlg._mark_used_check.setChecked(True)
    dlg._on_accept()
    params = dlg.params()
    assert params == ExportParams(
        mode=ExportMode.BURN,
        burn_directory=Path("/tmp/burn"),
        mark_used=True,
    )


def test_export_dialog_rejects_empty_excel_path(qapp, monkeypatch):
    dlg = ExportDialog()
    warnings: list[tuple] = []

    def _capture_warning(*args):
        warnings.append(args)

    monkeypatch.setattr(QMessageBox, "warning", _capture_warning)
    dlg._on_accept()
    assert dlg.params() is None
    assert warnings


def test_change_status_dialog_returns_status(qapp):
    dlg = ChangeStatusDialog()
    dlg._status_combo.setCurrentIndex(1)
    dlg._on_accept()
    assert dlg.status() is Status.USED


def test_main_window_action_buttons_disabled_without_selection(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    assert not win._change_status_btn.isEnabled()
    assert not win._export_btn.isEnabled()


def test_main_window_change_status_updates_table(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    win = MainWindow(svc)
    win._rows = rows
    win._populate_table(rows)
    win._table.selectRow(0)

    class _AcceptedStatusDialog:
        def __init__(self, parent=None) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def status(self) -> Status:
            return Status.USED

    monkeypatch.setattr(
        "sn_manager.gui.main_window.ChangeStatusDialog",
        _AcceptedStatusDialog,
    )
    win._on_change_status()

    status_item = win._table.item(0, 9)
    assert status_item is not None
    assert status_item.text() == "已使用"
    assert svc.filter(sn=rows[0]["sn"])[0]["status"] == Status.USED.value


def test_main_window_export_excel_selected_rows(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    xlsx = tmp_path / "out.xlsx"
    win = MainWindow(svc)
    win._rows = rows
    win._populate_table(rows)
    win._table.selectRow(0)

    class _AcceptedExportDialog:
        def __init__(self, parent=None) -> None:
            self._params = ExportParams(
                mode=ExportMode.EXCEL,
                excel_path=xlsx,
            )

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def params(self) -> ExportParams:
            return self._params

    monkeypatch.setattr(
        "sn_manager.gui.main_window.ExportDialog",
        _AcceptedExportDialog,
    )
    win._on_export()

    wb = load_workbook(xlsx)
    assert wb.active["A2"].value == rows[0]["sn"]


def test_main_window_export_burn_mark_used(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    sn = rows[0]["sn"]
    burn_dir = tmp_path / "burn"
    win = MainWindow(svc)
    win._rows = rows
    win._populate_table(rows)
    win._table.selectRow(0)

    class _AcceptedBurnDialog:
        def __init__(self, parent=None) -> None:
            self._params = ExportParams(
                mode=ExportMode.BURN,
                burn_directory=burn_dir,
                mark_used=True,
            )

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def params(self) -> ExportParams:
            return self._params

    monkeypatch.setattr(
        "sn_manager.gui.main_window.ExportDialog",
        _AcceptedBurnDialog,
    )
    win._on_export()

    assert (burn_dir / f"sn_{sn}.txt").read_text(encoding="utf-8") == sn
    assert svc.filter(sn=sn)[0]["status"] == Status.USED.value
    status_item = win._table.item(0, 9)
    assert status_item is not None
    assert status_item.text() == "已使用"


def test_main_window_export_burn_failure_shows_warning(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    sn = rows[0]["sn"]
    win = MainWindow(svc)
    win._rows = rows
    win._populate_table(rows)
    win._table.selectRow(0)

    class _AcceptedBurnDialog:
        def __init__(self, parent=None) -> None:
            self._params = ExportParams(
                mode=ExportMode.BURN,
                burn_directory=tmp_path / "burn",
                mark_used=True,
            )

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def params(self) -> ExportParams:
            return self._params

    warnings: list[tuple] = []

    def _capture_warning(*args):
        warnings.append(args)

    def boom(*_args, **_kwargs):
        raise OSError("write failed")

    monkeypatch.setattr(
        "sn_manager.gui.main_window.ExportDialog",
        _AcceptedBurnDialog,
    )
    monkeypatch.setattr(
        "sn_manager.gui.main_window.export_burn_and_mark_used",
        boom,
    )
    monkeypatch.setattr(QMessageBox, "warning", _capture_warning)

    win._on_export()

    assert warnings
    assert svc.filter(sn=sn)[0]["status"] == Status.UNUSED.value
