"""主数据维护对话框：确认才落库。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sn_manager.app.services import MasterSnapshot, SnService
from sn_manager.core.errors import ValidationError
from sn_manager.db import master_data as md


class MasterDataDialog(QDialog):
    """编辑四类主数据；仅 Accepted 时写入数据库。"""

    def __init__(self, service: SnService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.setWindowTitle("主数据")
        self.resize(520, 420)
        self._build_ui()
        self._load_from_db()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        self._model_table = self._make_code_table("型号编码")
        self._batch_table = self._make_code_table("批次编码")
        self._factory_table = self._make_named_table("单位编码", "名称")
        self._market_table = self._make_named_table("市场编码", "名称")

        tabs.addTab(self._wrap_table(self._model_table), "型号")
        tabs.addTab(self._wrap_table(self._batch_table), "批次")
        tabs.addTab(self._wrap_table(self._factory_table), "单位")
        tabs.addTab(self._wrap_table(self._market_table), "市场")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn is not None:
            ok_btn.setText("确认")
        if cancel_btn is not None:
            cancel_btn.setText("取消")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_code_table(self, header: str) -> QTableWidget:
        table = QTableWidget(0, 1)
        table.setHorizontalHeaderLabels([header])
        self._configure_table(table)
        return table

    def _make_named_table(self, code_header: str, name_header: str) -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels([code_header, name_header])
        self._configure_table(table)
        return table

    def _configure_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _wrap_table(self, table: QTableWidget) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(table)

        row = QHBoxLayout()
        add_btn = QPushButton("添加")
        remove_btn = QPushButton("删除")
        add_btn.clicked.connect(lambda: self._add_row(table))
        remove_btn.clicked.connect(lambda: self._remove_row(table))
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addStretch()
        layout.addLayout(row)
        return panel

    def _add_row(self, table: QTableWidget) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for col in range(table.columnCount()):
            table.setItem(row, col, QTableWidgetItem(""))

    def _remove_row(self, table: QTableWidget) -> None:
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    def _load_from_db(self) -> None:
        conn = self._service.conn
        self._fill_code_table(self._model_table, md.list_product_models(conn))
        self._fill_code_table(self._batch_table, md.list_hardware_batches(conn))
        self._fill_named_table(self._factory_table, md.list_factories(conn))
        self._fill_named_table(self._market_table, md.list_markets(conn))

    def _fill_code_table(self, table: QTableWidget, rows: list[dict]) -> None:
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            item = QTableWidgetItem(str(row["code"]))
            table.setItem(row_idx, 0, item)

    def _fill_named_table(self, table: QTableWidget, rows: list[dict]) -> None:
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            table.setItem(row_idx, 0, QTableWidgetItem(str(row["code"])))
            table.setItem(row_idx, 1, QTableWidgetItem(str(row["name"])))

    def _cell_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        if item is None:
            return ""
        return item.text().strip()

    def _collect_codes(self, table: QTableWidget, label: str) -> list[str] | None:
        codes: list[str] = []
        seen: set[str] = set()
        for row in range(table.rowCount()):
            code = self._cell_text(table, row, 0).upper()
            if not code:
                continue
            if code in seen:
                QMessageBox.warning(self, "主数据", f"{label}编码重复：{code}")
                return None
            seen.add(code)
            codes.append(code)
        return codes

    def _collect_named(
        self,
        table: QTableWidget,
        label: str,
    ) -> list[tuple[str, str]] | None:
        entries: list[tuple[str, str]] = []
        seen: set[str] = set()
        for row in range(table.rowCount()):
            code = self._cell_text(table, row, 0).upper()
            name = self._cell_text(table, row, 1)
            if not code and not name:
                continue
            if not code:
                QMessageBox.warning(self, "主数据", f"请填写{label}编码。")
                return None
            if not name:
                QMessageBox.warning(self, "主数据", f"请填写{label}名称。")
                return None
            if code in seen:
                QMessageBox.warning(self, "主数据", f"{label}编码重复：{code}")
                return None
            seen.add(code)
            entries.append((code, name))
        return entries

    def _collect_snapshot(self) -> MasterSnapshot | None:
        product_models = self._collect_codes(self._model_table, "型号")
        if product_models is None:
            return None
        hardware_batches = self._collect_codes(self._batch_table, "批次")
        if hardware_batches is None:
            return None
        factories = self._collect_named(self._factory_table, "单位")
        if factories is None:
            return None
        markets = self._collect_named(self._market_table, "市场")
        if markets is None:
            return None
        return MasterSnapshot(
            product_models=product_models,
            hardware_batches=hardware_batches,
            factories=factories,
            markets=markets,
        )

    def _on_accept(self) -> None:
        snapshot = self._collect_snapshot()
        if snapshot is None:
            return
        try:
            self._service.apply_master_data(snapshot)
        except ValidationError as exc:
            QMessageBox.warning(self, "主数据", str(exc))
            self._load_from_db()
            return
        self.accept()
