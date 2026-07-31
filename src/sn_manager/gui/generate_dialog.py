"""生成 SN 对话框。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sn_manager.app.services import SnService
from sn_manager.db import master_data as md


@dataclass(frozen=True)
class GenerateParams:
    """用户确认后的生成参数。"""

    product_model: str
    hw_batch: str
    factory: str
    market: str
    prod_date: date
    count: int


class GenerateDialog(QDialog):
    """填写生成条件；Accepted 后可通过 params() 读取参数。"""

    def __init__(self, service: SnService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._params: GenerateParams | None = None
        self.setWindowTitle("生成序列号")
        self.setMinimumWidth(360)
        self._build_ui()
        self._load_master_data()

    def params(self) -> GenerateParams | None:
        return self._params

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._model_combo = QComboBox()
        form.addRow("型号", self._model_combo)

        self._batch_combo = QComboBox()
        form.addRow("批次", self._batch_combo)

        self._factory_combo = QComboBox()
        form.addRow("单位", self._factory_combo)

        self._market_combo = QComboBox()
        form.addRow("市场", self._market_combo)

        self._date_edit = QDateEdit(calendarPopup=True)
        self._date_edit.setDate(QDate.currentDate())
        form.addRow("生产日期", self._date_edit)

        self._count_spin = QSpinBox()
        self._count_spin.setMinimum(1)
        self._count_spin.setMaximum(9999)
        self._count_spin.setValue(1)
        form.addRow("数量", self._count_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn is not None:
            ok_btn.setText("确定")
        if cancel_btn is not None:
            cancel_btn.setText("取消")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_master_data(self) -> None:
        conn = self._service.conn
        for row in md.list_product_models(conn):
            self._model_combo.addItem(f"{row['code']} {row['name']}", row["code"])
        for row in md.list_hardware_batches(conn):
            self._batch_combo.addItem(f"{row['code']} {row['name']}", row["code"])
        for row in md.list_factories(conn):
            self._factory_combo.addItem(f"{row['code']} {row['name']}", row["code"])
        for row in md.list_markets(conn):
            self._market_combo.addItem(f"{row['code']} {row['name']}", row["code"])

    def _on_accept(self) -> None:
        product_model = self._model_combo.currentData()
        hw_batch = self._batch_combo.currentData()
        factory = self._factory_combo.currentData()
        market = self._market_combo.currentData()
        if not product_model or not hw_batch or not factory or not market:
            QMessageBox.warning(
                self,
                "生成",
                "请先在主数据中维护并选择型号、批次、单位与市场。",
            )
            return

        qd = self._date_edit.date()
        prod_date = date(qd.year(), qd.month(), qd.day())

        self._params = GenerateParams(
            product_model=str(product_model),
            hw_batch=str(hw_batch),
            factory=str(factory),
            market=str(market),
            prod_date=prod_date,
            count=self._count_spin.value(),
        )
        self.accept()
