import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from sn_manager.app.paths import default_db_path
from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    db_path = default_db_path()
    try:
        conn = connect(db_path)
    except OSError as e:
        QMessageBox.critical(None, "错误", f"无法打开数据库：{db_path}\n{e}")
        raise SystemExit(1) from e
    service = SnService(conn)
    win = MainWindow(service)
    win.setWindowTitle("设备序列号管理")
    win.resize(1100, 700)
    win.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
