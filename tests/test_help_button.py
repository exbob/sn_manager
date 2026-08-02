from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtWidgets import QMessageBox

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_help_button_exists(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    assert win._help_btn.text() == "帮助"


def test_help_opens_manual(qapp, tmp_path: Path, monkeypatch) -> None:
    manual = tmp_path / "user-manual.md"
    manual.write_text("# x\n", encoding="utf-8")
    monkeypatch.setattr(
        "sn_manager.gui.main_window.resolve_user_manual_path",
        lambda: manual,
    )
    opened: list = []
    monkeypatch.setattr(
        "sn_manager.gui.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win._help_btn.click()
    assert len(opened) == 1
    assert Path(opened[0].toLocalFile()) == manual


def test_help_missing_shows_warning(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sn_manager.gui.main_window.resolve_user_manual_path",
        lambda: None,
    )
    warned = MagicMock()
    monkeypatch.setattr(QMessageBox, "warning", warned)
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win._help_btn.click()
    warned.assert_called_once()
