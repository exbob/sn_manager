"""主窗口：筛选、查询结果表与操作按钮骨架。"""

from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sn_manager.app.services import SnService
from sn_manager.core.errors import SnError
from sn_manager.core.status import Status
from sn_manager.app.export import export_burn_and_mark_used, export_excel
from sn_manager.gui.export_dialog import ExportDialog, ExportMode
from sn_manager.gui.generate_dialog import GenerateDialog
from sn_manager.gui.master_data_dialog import MasterDataDialog

_TABLE_COLUMNS: list[tuple[str, str]] = [
    ("sn", "SN"),
    ("product_model", "型号"),
    ("hw_batch", "批次"),
    ("factory", "单位"),
    ("market", "市场"),
    ("prod_year", "年"),
    ("prod_month", "月"),
    ("prod_day", "日"),
    ("seq", "序号"),
    ("status", "状态"),
    ("created_at", "创建时间"),
]

_STATUS_LABELS: dict[str, str] = {
    Status.UNUSED.value: "未使用",
    Status.USED.value: "已使用",
    Status.VOID.value: "作废",
}

_STATUS_FILTER_OPTIONS: list[tuple[str, str | None]] = [
    ("全部", None),
    ("未使用", Status.UNUSED.value),
    ("已使用", Status.USED.value),
    ("作废", Status.VOID.value),
]

_CHANGE_STATUS_OPTIONS: list[tuple[str, Status]] = [
    ("未使用", Status.UNUSED),
    ("已使用", Status.USED),
    ("作废", Status.VOID),
]


class ChangeStatusDialog(QDialog):
    """选择目标状态；Accepted 后可通过 status() 读取。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status: Status | None = None
        self.setWindowTitle("改状态")
        self._build_ui()

    def status(self) -> Status | None:
        return self._status

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._status_combo = QComboBox()
        for label, _ in _CHANGE_STATUS_OPTIONS:
            self._status_combo.addItem(label)
        form.addRow("目标状态", self._status_combo)
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

    def _on_accept(self) -> None:
        _, status = _CHANGE_STATUS_OPTIONS[self._status_combo.currentIndex()]
        self._status = status
        self.accept()


class MainWindow(QMainWindow):
    """设备序列号管理主界面。"""

    def __init__(self, service: SnService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._rows: list[dict[str, Any]] = []
        self._build_ui()
        self._wire_signals()
        self._update_action_buttons()

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_filter_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 820])
        self.setCentralWidget(splitter)

    def _build_filter_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        group = QGroupBox("筛选条件")
        form = QFormLayout(group)

        self._sn_edit = QLineEdit()
        self._sn_edit.setPlaceholderText("完整 SN")
        form.addRow("完整 SN", self._sn_edit)

        self._model_edit = QLineEdit()
        form.addRow("型号", self._model_edit)

        self._batch_edit = QLineEdit()
        form.addRow("批次", self._batch_edit)

        self._factory_edit = QLineEdit()
        form.addRow("单位", self._factory_edit)

        self._market_edit = QLineEdit()
        form.addRow("市场", self._market_edit)

        self._status_combo = QComboBox()
        for label, _ in _STATUS_FILTER_OPTIONS:
            self._status_combo.addItem(label)
        form.addRow("状态", self._status_combo)

        self._date_from_enabled = QCheckBox("启用")
        self._date_from_edit = QDateEdit(calendarPopup=True)
        self._date_from_edit.setDate(QDate.currentDate())
        self._date_from_edit.setEnabled(False)
        from_row = QWidget()
        from_layout = QHBoxLayout(from_row)
        from_layout.setContentsMargins(0, 0, 0, 0)
        from_layout.addWidget(self._date_from_edit)
        from_layout.addWidget(self._date_from_enabled)
        form.addRow("日期从", from_row)

        self._date_to_enabled = QCheckBox("启用")
        self._date_to_edit = QDateEdit(calendarPopup=True)
        self._date_to_edit.setDate(QDate.currentDate())
        self._date_to_edit.setEnabled(False)
        to_row = QWidget()
        to_layout = QHBoxLayout(to_row)
        to_layout.setContentsMargins(0, 0, 0, 0)
        to_layout.addWidget(self._date_to_edit)
        to_layout.addWidget(self._date_to_enabled)
        form.addRow("日期到", to_row)

        layout.addWidget(group)

        self._query_btn = QPushButton("查询")
        self._generate_btn = QPushButton("生成")
        self._master_btn = QPushButton("主数据")
        layout.addWidget(self._query_btn)
        layout.addWidget(self._generate_btn)
        layout.addWidget(self._master_btn)
        layout.addStretch()
        return panel

    def _build_results_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("结果表（可多选）"))
        top_row.addStretch()
        self._select_all_btn = QPushButton("全选")
        top_row.addWidget(self._select_all_btn)
        layout.addLayout(top_row)

        self._table = QTableWidget(0, len(_TABLE_COLUMNS))
        self._table.setHorizontalHeaderLabels([label for _, label in _TABLE_COLUMNS])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)
        layout.addWidget(self._table)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self._change_status_btn = QPushButton("改状态")
        self._export_btn = QPushButton("导出")
        bottom_row.addWidget(self._change_status_btn)
        bottom_row.addWidget(self._export_btn)
        layout.addLayout(bottom_row)
        return panel

    def _wire_signals(self) -> None:
        self._date_from_enabled.toggled.connect(self._date_from_edit.setEnabled)
        self._date_to_enabled.toggled.connect(self._date_to_edit.setEnabled)
        self._query_btn.clicked.connect(self._on_query)
        self._generate_btn.clicked.connect(self._on_generate)
        self._master_btn.clicked.connect(self._on_master_data)
        self._select_all_btn.clicked.connect(self._on_select_all)
        self._change_status_btn.clicked.connect(self._on_change_status)
        self._export_btn.clicked.connect(self._on_export)
        self._table.itemSelectionChanged.connect(self._update_action_buttons)

    def _build_criteria(self) -> dict[str, Any]:
        criteria: dict[str, Any] = {}

        if text := self._sn_edit.text().strip():
            criteria["sn"] = text
        if text := self._model_edit.text().strip():
            criteria["product_model"] = text
        if text := self._batch_edit.text().strip():
            criteria["hw_batch"] = text
        if text := self._factory_edit.text().strip():
            criteria["factory"] = text
        if text := self._market_edit.text().strip():
            criteria["market"] = text

        status_index = self._status_combo.currentIndex()
        _, status_value = _STATUS_FILTER_OPTIONS[status_index]
        if status_value is not None:
            criteria["status"] = status_value

        if self._date_from_enabled.isChecked():
            qd = self._date_from_edit.date()
            criteria["prod_date_from"] = date(qd.year(), qd.month(), qd.day())
        if self._date_to_enabled.isChecked():
            qd = self._date_to_edit.date()
            criteria["prod_date_to"] = date(qd.year(), qd.month(), qd.day())

        return criteria

    def _on_query(self) -> None:
        self._rows = self._service.filter(**self._build_criteria())
        self._populate_table(self._rows)

    def _populate_table(self, rows: list[dict[str, Any]]) -> None:
        self._table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, (key, _) in enumerate(_TABLE_COLUMNS):
                value = row.get(key, "")
                if key == "status":
                    display = _STATUS_LABELS.get(str(value), str(value))
                else:
                    display = str(value)
                item = QTableWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, row.get("sn"))
                self._table.setItem(row_idx, col_idx, item)
        self._update_action_buttons()

    def _on_select_all(self) -> None:
        self._table.selectAll()

    def _selected_sns(self) -> list[str]:
        sns: list[str] = []
        for index in self._table.selectionModel().selectedRows():
            item = self._table.item(index.row(), 0)
            if item is None:
                continue
            sn = item.data(Qt.ItemDataRole.UserRole)
            if sn:
                sns.append(str(sn))
        return sns

    def _selected_rows(self) -> list[dict[str, Any]]:
        sns = self._selected_sns()
        if not sns:
            return []
        by_sn = {row["sn"]: row for row in self._rows if row.get("sn") in sns}
        return [by_sn[sn] for sn in sns if sn in by_sn]

    def _refresh_rows_for_sns(self, sns: list[str]) -> None:
        if not sns:
            return
        updated: dict[str, dict[str, Any]] = {}
        for sn in sns:
            rows = self._service.filter(sn=sn)
            if rows:
                updated[sn] = rows[0]

        for row_idx in range(self._table.rowCount()):
            item = self._table.item(row_idx, 0)
            if item is None:
                continue
            sn = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if sn not in updated:
                continue
            row = updated[sn]
            for col_idx, (key, _) in enumerate(_TABLE_COLUMNS):
                value = row.get(key, "")
                if key == "status":
                    display = _STATUS_LABELS.get(str(value), str(value))
                else:
                    display = str(value)
                cell = self._table.item(row_idx, col_idx)
                if cell is None:
                    cell = QTableWidgetItem(display)
                    if col_idx == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, sn)
                    self._table.setItem(row_idx, col_idx, cell)
                else:
                    cell.setText(display)

        self._rows = [
            updated[r["sn"]] if r.get("sn") in updated else r for r in self._rows
        ]

    def _update_action_buttons(self) -> None:
        has_selection = bool(self._selected_sns())
        self._change_status_btn.setEnabled(has_selection)
        self._export_btn.setEnabled(has_selection)

    def _on_generate(self) -> None:
        dlg = GenerateDialog(self._service, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        params = dlg.params()
        if params is None:
            return
        try:
            rows = self._service.generate(
                product_model=params.product_model,
                hw_batch=params.hw_batch,
                factory=params.factory,
                market=params.market,
                prod_date=params.prod_date,
                count=params.count,
            )
        except SnError as exc:
            QMessageBox.warning(self, "生成失败", str(exc))
            return
        self._rows = rows
        self._populate_table(rows)
        self._table.selectAll()

    def _on_master_data(self) -> None:
        dlg = MasterDataDialog(self._service, parent=self)
        dlg.exec()

    def _on_change_status(self) -> None:
        sns = self._selected_sns()
        if not sns:
            return
        dlg = ChangeStatusDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        status = dlg.status()
        if status is None:
            return
        self._service.set_status(sns, status)
        self._refresh_rows_for_sns(sns)

    def _on_export(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        dlg = ExportDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        params = dlg.params()
        if params is None:
            return
        try:
            if params.mode is ExportMode.EXCEL:
                if params.excel_path is None:
                    return
                export_excel(rows, params.excel_path)
            else:
                if params.burn_directory is None:
                    return
                sns = [str(row["sn"]) for row in rows]
                export_burn_and_mark_used(
                    self._service,
                    sns,
                    params.burn_directory,
                    mark_used=params.mark_used,
                )
                if params.mark_used:
                    self._refresh_rows_for_sns(sns)
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
