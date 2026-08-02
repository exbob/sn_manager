import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from sn_manager.app.paths import default_db_path, resolve_app_icon_path
from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.fonts import apply_ui_font
from sn_manager.gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    # 固定浅色，避免跟随 Windows 系统深色模式
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    icon_path = resolve_app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))
    chosen = apply_ui_font(app)
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
    if chosen is None:
        QMessageBox.warning(
            win,
            "字体提示",
            "未检测到中文字体，界面中文可能显示为乱码或方框。\n"
            "Linux/WSL 可安装：sudo apt install fonts-noto-cjk\n"
            "或将 NotoSansCJK-Regular.ttc 放到 ~/.local/share/fonts/ 后执行 fc-cache -f",
        )
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
