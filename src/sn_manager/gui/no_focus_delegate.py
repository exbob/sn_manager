"""Item delegate that suppresses the current-cell focus rectangle."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)


class NoFocusDelegate(QStyledItemDelegate):
    """Paint items without State_HasFocus so Windows focus borders don't cover text."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, opt, index)


def install_no_focus_delegate(view: QAbstractItemView) -> None:
    view.setItemDelegate(NoFocusDelegate(view))
