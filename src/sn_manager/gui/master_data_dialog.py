"""主数据维护对话框：确认才落库。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
from sn_manager.gui.no_focus_delegate import (
    SKY_BLUE_SELECTION_STYLESHEET,
    install_no_focus_delegate,
)


class MasterDataDialog(QDialog):
    """编辑型号（含下属批次）、单位、市场；仅 Accepted 时写入数据库。"""

    def __init__(self, service: SnService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._batches_by_model: dict[str, list[tuple[str, str]]] = {}
        self._selected_model_code: str | None = None
        self.setWindowTitle("主数据")
        self.resize(560, 520)
        self._build_ui()
        self._load_from_db()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        self._model_table = self._make_named_table("型号编码", "名称")
        self._batch_table = self._make_named_table("批次编码", "名称")
        self._factory_table = self._make_named_table("单位编码", "名称")
        self._market_table = self._make_named_table("市场编码", "名称")

        tabs.addTab(self._build_model_tab(), "型号")
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

        self._model_table.itemSelectionChanged.connect(self._on_model_selection_changed)

    def _build_model_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._model_table)
        layout.addLayout(self._table_buttons(self._model_table))

        layout.addWidget(QLabel("硬件批次（当前型号）"))
        layout.addWidget(self._batch_table)
        batch_btns = QHBoxLayout()
        self._batch_add_btn = QPushButton("添加")
        self._batch_remove_btn = QPushButton("删除")
        self._batch_add_btn.clicked.connect(self._add_batch_row)
        self._batch_remove_btn.clicked.connect(
            lambda: self._remove_row(self._batch_table)
        )
        batch_btns.addWidget(self._batch_add_btn)
        batch_btns.addWidget(self._batch_remove_btn)
        batch_btns.addStretch()
        layout.addLayout(batch_btns)
        self._set_batch_controls_enabled(False)
        return panel

    def _make_named_table(self, code_header: str, name_header: str) -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels([code_header, name_header])
        self._configure_table(table)
        return table

    def _configure_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setStyleSheet(SKY_BLUE_SELECTION_STYLESHEET)
        install_no_focus_delegate(table)
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _table_buttons(self, table: QTableWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        add_btn = QPushButton("添加")
        remove_btn = QPushButton("删除")
        add_btn.clicked.connect(lambda: self._add_row(table))
        remove_btn.clicked.connect(lambda: self._remove_model_row())
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addStretch()
        return row

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

    def _set_batch_controls_enabled(self, enabled: bool) -> None:
        self._batch_table.setEnabled(enabled)
        self._batch_add_btn.setEnabled(enabled)
        self._batch_remove_btn.setEnabled(enabled)

    def _add_row(self, table: QTableWidget) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for col in range(table.columnCount()):
            table.setItem(row, col, QTableWidgetItem(""))
        table.setCurrentCell(row, 0)
        item = table.item(row, 0)
        if item is not None:
            table.editItem(item)

    def _add_batch_row(self) -> None:
        if self._selected_model_code is None:
            return
        self._add_row(self._batch_table)

    def _remove_row(self, table: QTableWidget) -> None:
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    def _remove_model_row(self) -> None:
        row = self._model_table.currentRow()
        if row < 0:
            return
        code = self._cell_text(self._model_table, row, 0).upper()
        self._flush_current_batches()
        if code:
            self._batches_by_model.pop(code, None)
        self._selected_model_code = None
        self._model_table.removeRow(row)
        self._fill_named_table(self._batch_table, [])
        self._set_batch_controls_enabled(False)

    def _load_from_db(self) -> None:
        conn = self._service.conn
        self._batches_by_model = {}
        for row in md.list_hardware_batches(conn):
            model = str(row["product_model"])
            self._batches_by_model.setdefault(model, []).append(
                (str(row["code"]), str(row["name"]))
            )
        self._selected_model_code = None
        self._fill_named_table(self._model_table, md.list_product_models(conn))
        self._fill_named_table(self._batch_table, [])
        self._set_batch_controls_enabled(False)
        self._fill_named_table(self._factory_table, md.list_factories(conn))
        self._fill_named_table(self._market_table, md.list_markets(conn))

    def _fill_named_table(self, table: QTableWidget, rows: list[dict] | list) -> None:
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            if isinstance(row, dict):
                code, name = str(row["code"]), str(row["name"])
            else:
                code, name = row
            table.setItem(row_idx, 0, QTableWidgetItem(code))
            table.setItem(row_idx, 1, QTableWidgetItem(name))

    def _cell_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        if item is None:
            return ""
        return item.text().strip()

    def _read_batch_table(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for row in range(self._batch_table.rowCount()):
            code = self._cell_text(self._batch_table, row, 0).upper()
            name = self._cell_text(self._batch_table, row, 1)
            if not code and not name:
                continue
            entries.append((code, name))
        return entries

    def _flush_current_batches(self) -> None:
        if self._selected_model_code is None:
            return
        self._batches_by_model[self._selected_model_code] = self._read_batch_table()

    def _on_model_selection_changed(self) -> None:
        self._flush_current_batches()
        row = self._model_table.currentRow()
        if row < 0:
            self._selected_model_code = None
            self._fill_named_table(self._batch_table, [])
            self._set_batch_controls_enabled(False)
            return
        code = self._cell_text(self._model_table, row, 0).upper()
        if not code:
            self._selected_model_code = None
            self._fill_named_table(self._batch_table, [])
            self._set_batch_controls_enabled(False)
            return
        self._selected_model_code = code
        batches = self._batches_by_model.get(code, [])
        self._fill_named_table(
            self._batch_table,
            [{"code": c, "name": n} for c, n in batches],
        )
        self._set_batch_controls_enabled(True)

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
        self._flush_current_batches()
        product_models = self._collect_named(self._model_table, "型号")
        if product_models is None:
            return None

        hardware_batches: list[tuple[str, str, str]] = []
        model_codes = {code for code, _ in product_models}
        # Drop batches for models no longer present
        for code in list(self._batches_by_model):
            if code not in model_codes:
                self._batches_by_model.pop(code, None)

        for model_code, _ in product_models:
            seen: set[str] = set()
            for batch_code, batch_name in self._batches_by_model.get(model_code, []):
                if not batch_code and not batch_name:
                    continue
                if not batch_code:
                    QMessageBox.warning(self, "主数据", "请填写批次编码。")
                    return None
                if not batch_name:
                    QMessageBox.warning(self, "主数据", "请填写批次名称。")
                    return None
                if batch_code in seen:
                    QMessageBox.warning(
                        self, "主数据", f"该型号下批次编码重复：{batch_code}"
                    )
                    return None
                seen.add(batch_code)
                hardware_batches.append((model_code, batch_code, batch_name))

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
