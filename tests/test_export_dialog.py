from datetime import date
from pathlib import Path
import re

from openpyxl import load_workbook
from PySide6.QtWidgets import QDialog, QMessageBox

from sn_manager.app.paths import app_dir
from sn_manager.app.services import SnService
from sn_manager.core.status import Status
from sn_manager.db.connection import connect
from sn_manager.gui.export_dialog import ExportDialog, ExportParams
from sn_manager.gui.main_window import ChangeStatusDialog, MainWindow


def test_export_dialog_defaults(qapp):
    dlg = ExportDialog()
    assert dlg._burn_check.isChecked()
    assert not dlg._excel_check.isChecked()
    assert dlg._mark_used_check.isChecked()
    assert dlg._path_edit.text() == str(app_dir())


def test_export_dialog_returns_params_on_accept(qapp):
    dlg = ExportDialog()
    dlg._burn_check.setChecked(True)
    dlg._excel_check.setChecked(True)
    dlg._path_edit.setText("/tmp/out")
    dlg._mark_used_check.setChecked(False)
    dlg._on_accept()
    assert dlg.params() == ExportParams(
        burn=True,
        excel=True,
        export_directory=Path("/tmp/out"),
        mark_used=False,
    )


def test_export_dialog_rejects_no_type(qapp, monkeypatch):
    dlg = ExportDialog()
    warnings: list[tuple] = []

    def _capture_warning(*args):
        warnings.append(args)

    monkeypatch.setattr(QMessageBox, "warning", _capture_warning)
    dlg._burn_check.setChecked(False)
    dlg._excel_check.setChecked(False)
    dlg._on_accept()
    assert dlg.params() is None
    assert warnings


def test_export_dialog_rejects_empty_path(qapp, monkeypatch):
    dlg = ExportDialog()
    warnings: list[tuple] = []

    def _capture_warning(*args):
        warnings.append(args)

    monkeypatch.setattr(QMessageBox, "warning", _capture_warning)
    dlg._path_edit.setText("   ")
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
    win = MainWindow(svc)
    win._rows = rows
    win._populate_table(rows)
    win._table.selectRow(0)

    class _AcceptedExportDialog:
        def __init__(self, parent=None) -> None:
            self._params = ExportParams(
                burn=False,
                excel=True,
                export_directory=tmp_path,
                mark_used=False,
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

    xlsx_files = list(tmp_path.glob("*.xlsx"))
    assert len(xlsx_files) == 1
    assert re.fullmatch(r"\d{14}\.xlsx", xlsx_files[0].name)
    wb = load_workbook(xlsx_files[0])
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
                burn=True,
                excel=False,
                export_directory=burn_dir,
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
                burn=True,
                excel=False,
                export_directory=tmp_path / "burn",
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
        "sn_manager.gui.main_window.export_selected_and_mark_used",
        boom,
    )
    monkeypatch.setattr(QMessageBox, "warning", _capture_warning)

    win._on_export()

    assert warnings
    assert svc.filter(sn=sn)[0]["status"] == Status.UNUSED.value
