"""主窗口：筛选、查询结果表与操作按钮骨架。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from PySide6.QtCore import QDate, QItemSelectionModel, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
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

from sn_manager.app.export import export_selected_and_mark_used
from sn_manager.app.paths import resolve_user_manual_path
from sn_manager.app.services import SnService
from sn_manager.app.version import resolve_app_version
from sn_manager.core.errors import SnError
from sn_manager.core.status import Status
from sn_manager.db import master_data as md
from sn_manager.gui.export_dialog import ExportDialog
from sn_manager.gui.generate_dialog import GenerateDialog
from sn_manager.gui.master_data_dialog import MasterDataDialog
from sn_manager.gui.no_focus_delegate import (
    SKY_BLUE_SELECTION_STYLESHEET,
    install_no_focus_delegate,
)

# 北京时间固定 UTC+8（无夏令时）；避免 Windows/PyInstaller 依赖 tzdata。
_BEIJING = timezone(timedelta(hours=8))


def format_display_timestamp(raw: str, *, use_beijing: bool) -> str:
    """库内 UTC ISO 文本 → 展示字符串；解析失败则原样返回。"""
    if not use_beijing:
        return raw
    text = raw.strip()
    if not text:
        return raw
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw


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
    ("created_at", "创建时间"),
    ("status", "状态"),
    ("updated_at", "更新时间"),
]

_STATUS_LABELS: dict[str, str] = {
    Status.UNUSED.value: "未使用",
    Status.USED.value: "已使用",
    Status.VOID.value: "作废",
}

_STATUS_FOREGROUND: dict[str, QColor] = {
    Status.USED.value: QColor("#2E7D32"),
    Status.VOID.value: QColor("#C62828"),
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

PAGE_SIZE = 200


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
        self._total_count = 0
        self._page = 1
        self._query_criteria: dict[str, Any] = {}
        self._memory_rows: list[dict[str, Any]] | None = None
        self._build_ui()
        self._wire_signals()
        self._update_action_buttons()
        self._update_page_controls()

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

        self._model_combo = QComboBox()
        self._model_combo.setEditable(False)
        form.addRow("型号", self._model_combo)

        self._batch_combo = QComboBox()
        self._batch_combo.setEditable(False)
        form.addRow("批次", self._batch_combo)

        self._factory_combo = QComboBox()
        self._factory_combo.setEditable(False)
        form.addRow("单位", self._factory_combo)

        self._market_combo = QComboBox()
        self._market_combo.setEditable(False)
        form.addRow("市场", self._market_combo)

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

        self._help_btn = QPushButton("帮助")
        layout.addWidget(self._help_btn)

        self._version_label = QLabel(resolve_app_version())
        self._version_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        font = self._version_label.font()
        font.setPointSize(max(8, font.pointSize() - 2))
        self._version_label.setFont(font)
        self._version_label.setStyleSheet("color: #666666;")
        layout.addWidget(self._version_label)
        self._reload_filter_master_combos()
        return panel

    def _reload_filter_master_combos(self) -> None:
        def fill(combo: QComboBox, rows: list[dict[str, Any]]) -> None:
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("", None)
            for row in rows:
                combo.addItem(f"{row['code']} {row['name']}", row["code"])
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        conn = self._service.conn
        fill(self._model_combo, md.list_product_models(conn))
        fill(self._factory_combo, md.list_factories(conn))
        fill(self._market_combo, md.list_markets(conn))
        self._reload_filter_batch_combo()

    def _reload_filter_batch_combo(self) -> None:
        current = self._batch_combo.currentData()
        self._batch_combo.blockSignals(True)
        self._batch_combo.clear()
        self._batch_combo.addItem("", None)
        model = self._model_combo.currentData()
        if model:
            for row in md.list_hardware_batches(self._service.conn, str(model)):
                self._batch_combo.addItem(f"{row['code']} {row['name']}", row["code"])
            idx = self._batch_combo.findData(current)
            self._batch_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self._batch_combo.setCurrentIndex(0)
        self._batch_combo.blockSignals(False)

    def _build_results_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("结果表"))
        self._beijing_time_cb = QCheckBox("北京时间")
        self._beijing_time_cb.setChecked(True)
        top_row.addWidget(self._beijing_time_cb)
        top_row.addStretch()
        self._select_all_btn = QPushButton("全选")
        top_row.addWidget(self._select_all_btn)
        layout.addLayout(top_row)

        self._table = QTableWidget(0, len(_TABLE_COLUMNS))
        self._table.setHorizontalHeaderLabels([label for _, label in _TABLE_COLUMNS])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(SKY_BLUE_SELECTION_STYLESHEET)
        # QSS alone cannot suppress the Windows focus frame that covers cell text.
        install_no_focus_delegate(self._table)
        header = self._table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)
        layout.addWidget(self._table)

        bottom_row = QHBoxLayout()
        self._count_label = QLabel("共 0 条，已选 0 条")
        bottom_row.addWidget(self._count_label)
        self._prev_page_btn = QPushButton("上一页")
        self._prev_page_btn.setEnabled(False)
        bottom_row.addWidget(self._prev_page_btn)
        self._page_label = QLabel("第 1 / 1 页")
        bottom_row.addWidget(self._page_label)
        self._next_page_btn = QPushButton("下一页")
        self._next_page_btn.setEnabled(False)
        bottom_row.addWidget(self._next_page_btn)
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
        self._model_combo.currentIndexChanged.connect(self._reload_filter_batch_combo)
        self._query_btn.clicked.connect(self._on_query)
        self._generate_btn.clicked.connect(self._on_generate)
        self._master_btn.clicked.connect(self._on_master_data)
        self._help_btn.clicked.connect(self._on_help)
        self._select_all_btn.clicked.connect(self._on_select_all)
        self._beijing_time_cb.toggled.connect(self._on_beijing_time_toggled)
        self._change_status_btn.clicked.connect(self._on_change_status)
        self._export_btn.clicked.connect(self._on_export)
        self._prev_page_btn.clicked.connect(self._on_prev_page)
        self._next_page_btn.clicked.connect(self._on_next_page)
        self._table.itemSelectionChanged.connect(self._update_action_buttons)

    def _build_criteria(self) -> dict[str, Any]:
        criteria: dict[str, Any] = {}

        if text := self._sn_edit.text().strip():
            criteria["sn"] = text
        if code := self._model_combo.currentData():
            criteria["product_model"] = code
        if code := self._batch_combo.currentData():
            criteria["hw_batch"] = code
        if code := self._factory_combo.currentData():
            criteria["factory"] = code
        if code := self._market_combo.currentData():
            criteria["market"] = code

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

    def _page_count(self) -> int:
        if self._total_count <= 0:
            return 1
        return max(1, (self._total_count + PAGE_SIZE - 1) // PAGE_SIZE)

    def _update_page_controls(self) -> None:
        p = self._page_count()
        self._page_label.setText(f"第 {self._page} / {p} 页")
        self._prev_page_btn.setEnabled(self._page > 1)
        self._next_page_btn.setEnabled(self._page < p)

    def _set_query_busy(self, busy: bool) -> None:
        self._query_btn.setText("查询中…" if busy else "查询")
        self._query_btn.setEnabled(not busy)
        self._generate_btn.setEnabled(not busy)
        self._master_btn.setEnabled(not busy)
        self._select_all_btn.setEnabled(not busy)
        if busy:
            self._change_status_btn.setEnabled(False)
            self._export_btn.setEnabled(False)
            self._prev_page_btn.setEnabled(False)
            self._next_page_btn.setEnabled(False)
        else:
            self._update_action_buttons()
            self._update_page_controls()

    def _show_memory_page(self) -> None:
        assert self._memory_rows is not None
        start = (self._page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        self._rows = self._memory_rows[start:end]
        self._populate_table(self._rows)
        self._update_page_controls()

    def _load_db_page(self, *, show_busy: bool) -> None:
        if show_busy:
            self._set_query_busy(True)
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
        try:
            offset = (self._page - 1) * PAGE_SIZE
            self._rows = self._service.filter(
                limit=PAGE_SIZE, offset=offset, **self._query_criteria
            )
            self._populate_table(self._rows)
            self._update_page_controls()
        except Exception as exc:
            QMessageBox.warning(self, "查询失败", str(exc))
        finally:
            if show_busy:
                self._set_query_busy(False)

    def _on_query(self) -> None:
        self._memory_rows = None
        self._set_query_busy(True)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        try:
            criteria = self._build_criteria()
            self._total_count = self._service.count(**criteria)
            self._query_criteria = criteria
            self._page = 1
            self._rows = self._service.filter(
                limit=PAGE_SIZE, offset=0, **criteria
            )
            self._populate_table(self._rows)
            self._update_page_controls()
        except Exception as exc:
            QMessageBox.warning(self, "查询失败", str(exc))
        finally:
            self._set_query_busy(False)

    def _on_prev_page(self) -> None:
        if self._page <= 1:
            return
        self._page -= 1
        if self._memory_rows is not None:
            self._show_memory_page()
        else:
            self._load_db_page(show_busy=True)

    def _on_next_page(self) -> None:
        if self._page >= self._page_count():
            return
        self._page += 1
        if self._memory_rows is not None:
            self._show_memory_page()
        else:
            self._load_db_page(show_busy=True)

    def _cell_display(self, key: str, value: object) -> str:
        if key == "status":
            return _STATUS_LABELS.get(str(value), str(value))
        if key in ("created_at", "updated_at"):
            return format_display_timestamp(
                str(value), use_beijing=self._beijing_time_cb.isChecked()
            )
        return str(value)

    def _restore_selection(self, sns: list[str]) -> None:
        if not sns:
            return
        wanted = set(sns)
        self._table.clearSelection()
        model = self._table.selectionModel()
        table_model = self._table.model()
        if model is None or table_model is None:
            return
        for row_idx in range(self._table.rowCount()):
            item = self._table.item(row_idx, 0)
            if item is None:
                continue
            sn = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if sn in wanted:
                model.select(
                    table_model.index(row_idx, 0),
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )

    def _on_beijing_time_toggled(self, _checked: bool) -> None:
        if not self._rows:
            return
        selected = self._selected_sns()
        self._populate_table(self._rows)
        self._restore_selection(selected)

    def _populate_table(self, rows: list[dict[str, Any]]) -> None:
        # Avoid ResizeToContents recalculating on every setItem during re-fill.
        table = self._table
        header = table.horizontalHeader()
        table.setUpdatesEnabled(False)
        try:
            table.clearSelection()
            if header is not None:
                header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            table.setRowCount(0)
            table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                for col_idx, (key, _) in enumerate(_TABLE_COLUMNS):
                    value = row.get(key, "")
                    display = self._cell_display(key, value)
                    item = QTableWidgetItem(display)
                    item.setData(Qt.ItemDataRole.UserRole, row.get("sn"))
                    if key == "status":
                        color = _STATUS_FOREGROUND.get(str(value))
                        if color is not None:
                            item.setForeground(color)
                    table.setItem(row_idx, col_idx, item)
            if header is not None:
                header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
                header.setStretchLastSection(True)
        finally:
            table.setUpdatesEnabled(True)
        self._update_action_buttons()

    def _on_select_all(self) -> None:
        self._table.selectAll()

    def _on_help(self) -> None:
        path = resolve_user_manual_path()
        if path is None:
            QMessageBox.warning(self, "帮助", "未找到使用手册文件（user-manual.md）。")
            return
        ok = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not ok:
            QMessageBox.warning(self, "帮助", f"无法打开使用手册：\n{path}")

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
                display = self._cell_display(key, value)
                cell = self._table.item(row_idx, col_idx)
                if cell is None:
                    cell = QTableWidgetItem(display)
                    if col_idx == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, sn)
                    self._table.setItem(row_idx, col_idx, cell)
                else:
                    cell.setText(display)
                if key == "status":
                    color = _STATUS_FOREGROUND.get(str(value))
                    if color is not None:
                        cell.setForeground(color)
                    else:
                        cell.setData(Qt.ItemDataRole.ForegroundRole, None)

        self._rows = [
            updated[r["sn"]] if r.get("sn") in updated else r for r in self._rows
        ]
        if self._memory_rows is not None:
            self._memory_rows = [
                updated[r["sn"]] if r.get("sn") in updated else r
                for r in self._memory_rows
            ]

    def _update_count_label(self) -> None:
        n = self._total_count
        m = len(self._selected_sns())
        self._count_label.setText(f"共 {n} 条，已选 {m} 条")

    def _update_action_buttons(self) -> None:
        has_selection = bool(self._selected_sns())
        self._change_status_btn.setEnabled(has_selection)
        self._export_btn.setEnabled(has_selection)
        self._update_count_label()

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
        self._apply_generated_rows(rows)

    def _apply_generated_rows(self, rows: list[dict[str, Any]]) -> None:
        self._memory_rows = rows
        self._total_count = len(rows)
        self._page = 1
        self._query_criteria = {}
        self._show_memory_page()
        self._table.selectAll()

    def _on_master_data(self) -> None:
        dlg = MasterDataDialog(self._service, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_filter_master_combos()

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
        excel_path = None
        if params.excel:
            excel_path = params.export_directory / datetime.now().strftime(
                "%Y%m%d%H%M%S.xlsx"
            )
        try:
            export_selected_and_mark_used(
                self._service,
                rows,
                burn=params.burn,
                excel=params.excel,
                export_directory=params.export_directory,
                mark_used=params.mark_used,
                excel_path=excel_path,
            )
            if params.mark_used:
                self._refresh_rows_for_sns([str(r["sn"]) for r in rows])
            export_dir = params.export_directory.resolve()
            ok = QDesktopServices.openUrl(QUrl.fromLocalFile(str(export_dir)))
            if not ok:
                QMessageBox.warning(
                    self,
                    "导出",
                    f"导出已完成，但无法打开导出目录：\n{export_dir}",
                )
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
