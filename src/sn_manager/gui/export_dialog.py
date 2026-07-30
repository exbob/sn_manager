"""导出对话框：Excel 或烧写目录。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class ExportMode(Enum):
    """导出方式。"""

    EXCEL = "excel"
    BURN = "burn"


@dataclass(frozen=True)
class ExportParams:
    """用户确认后的导出参数。"""

    mode: ExportMode
    excel_path: Path | None = None
    burn_directory: Path | None = None
    mark_used: bool = False


class ExportDialog(QDialog):
    """选择 Excel 文件或烧写目录；Accepted 后可通过 params() 读取参数。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._params: ExportParams | None = None
        self.setWindowTitle("导出")
        self._build_ui()

    def params(self) -> ExportParams | None:
        return self._params

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._excel_radio = QRadioButton("导出 Excel (.xlsx)")
        self._burn_radio = QRadioButton("导出烧写文本 (sn_<SN>.txt)")
        self._excel_radio.setChecked(True)
        layout.addWidget(self._excel_radio)
        layout.addWidget(self._burn_radio)

        form = QFormLayout()

        excel_row = QWidget()
        excel_layout = QHBoxLayout(excel_row)
        excel_layout.setContentsMargins(0, 0, 0, 0)
        self._excel_path_edit = QLineEdit()
        self._excel_browse_btn = QPushButton("浏览…")
        self._excel_browse_btn.clicked.connect(self._browse_excel)
        excel_layout.addWidget(self._excel_path_edit)
        excel_layout.addWidget(self._excel_browse_btn)
        form.addRow("Excel 文件", excel_row)

        burn_row = QWidget()
        burn_layout = QHBoxLayout(burn_row)
        burn_layout.setContentsMargins(0, 0, 0, 0)
        self._burn_dir_edit = QLineEdit()
        self._burn_browse_btn = QPushButton("浏览…")
        self._burn_browse_btn.clicked.connect(self._browse_burn_dir)
        burn_layout.addWidget(self._burn_dir_edit)
        burn_layout.addWidget(self._burn_browse_btn)
        form.addRow("烧写目录", burn_row)

        layout.addLayout(form)

        self._mark_used_check = QCheckBox("导出后标为已使用")
        layout.addWidget(self._mark_used_check)

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

        self._excel_radio.toggled.connect(self._update_mode_ui)
        self._update_mode_ui()

    def _update_mode_ui(self) -> None:
        excel_mode = self._excel_radio.isChecked()
        self._excel_path_edit.setEnabled(excel_mode)
        self._excel_browse_btn.setEnabled(excel_mode)
        self._burn_dir_edit.setEnabled(not excel_mode)
        self._burn_browse_btn.setEnabled(not excel_mode)
        self._mark_used_check.setEnabled(not excel_mode)

    def _browse_excel(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择 Excel 文件",
            "",
            "Excel 文件 (*.xlsx)",
        )
        if path:
            if not path.lower().endswith(".xlsx"):
                path = f"{path}.xlsx"
            self._excel_path_edit.setText(path)

    def _browse_burn_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择烧写目录")
        if path:
            self._burn_dir_edit.setText(path)

    def _on_accept(self) -> None:
        if self._excel_radio.isChecked():
            text = self._excel_path_edit.text().strip()
            if not text:
                QMessageBox.warning(self, "导出", "请选择 Excel 文件路径。")
                return
            self._params = ExportParams(
                mode=ExportMode.EXCEL,
                excel_path=Path(text),
            )
        else:
            text = self._burn_dir_edit.text().strip()
            if not text:
                QMessageBox.warning(self, "导出", "请选择烧写目录。")
                return
            self._params = ExportParams(
                mode=ExportMode.BURN,
                burn_directory=Path(text),
                mark_used=self._mark_used_check.isChecked(),
            )
        self.accept()
