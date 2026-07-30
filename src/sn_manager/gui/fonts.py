"""为界面选择可用的中文字体，避免 Linux/WSL 缺字时中文显示为方框或乱码。"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# 按优先级尝试；Windows 常见雅黑，Linux 常见 Noto / 文泉驿
_CJK_FAMILY_CANDIDATES: tuple[str, ...] = (
    "Noto Sans CJK SC",
    "Noto Sans CJK",
    "Source Han Sans SC",
    "WenQuanYi Micro Hei",
    "WenQuanYi Zen Hei",
    "Microsoft YaHei",
    "Microsoft YaHei UI",
    "SimHei",
    "PingFang SC",
)


def apply_ui_font(app: QApplication, point_size: int = 10) -> str | None:
    """将应用默认字体设为可用的中文字体。

    Returns:
        实际选用的字族名；若未找到合适中文字体则返回 None（仍保持系统默认）。
    """
    available = set(QFontDatabase.families())
    for family in _CJK_FAMILY_CANDIDATES:
        if family in available:
            font = QFont(family, point_size)
            app.setFont(font)
            return family
    return None
