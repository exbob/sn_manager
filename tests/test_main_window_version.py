from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_main_window_shows_resolved_version(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sn_manager.gui.main_window.resolve_app_version",
        lambda: "v9.9.9-1-gtest000",
    )
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    assert win._version_label.text() == "v9.9.9-1-gtest000"
    assert win._version_label.alignment() & Qt.AlignmentFlag.AlignHCenter
