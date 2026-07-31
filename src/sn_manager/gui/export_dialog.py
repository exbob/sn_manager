"""导出对话框：烧写与/或 Excel，共用导出目录。"""

from __future__ import annotations

from dataclasses import dataclass
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
    QVBoxLayout,
    QWidget,
)

from sn_manager.app.paths import app_dir


@dataclass(frozen=True)
class ExportParams:
    """用户确认后的导出参数。"""

    burn: bool
    excel: bool
    export_directory: Path
    mark_used: bool


class ExportDialog(QDialog):
    """选择烧写与/或 Excel；共用导出目录；Accepted 后可通过 params() 读取参数。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._params: ExportParams | None = None
        self.setWindowTitle("导出")
        self._build_ui()

    def params(self) -> ExportParams | None:
        return self._params

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._burn_check = QCheckBox("烧写文本 (sn_<SN>.txt)")
        self._excel_check = QCheckBox("导出 Excel (.xlsx)")
        self._burn_check.setChecked(True)
        self._excel_check.setChecked(False)
        layout.addWidget(self._burn_check)
        layout.addWidget(self._excel_check)

        form = QFormLayout()
        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        self._path_edit = QLineEdit(str(app_dir()))
        self._browse_btn = QPushButton("浏览…")
        self._browse_btn.clicked.connect(self._browse_directory)
        path_layout.addWidget(self._path_edit)
        path_layout.addWidget(self._browse_btn)
        form.addRow("导出路径", path_row)
        layout.addLayout(form)

        self._mark_used_check = QCheckBox("导出后标为已使用")
        self._mark_used_check.setChecked(True)
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

    def _browse_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择导出路径")
        if path:
            self._path_edit.setText(path)

    def _on_accept(self) -> None:
        burn = self._burn_check.isChecked()
        excel = self._excel_check.isChecked()
        if not burn and not excel:
            QMessageBox.warning(self, "导出", "请至少选择一种导出方式。")
            return
        text = self._path_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "导出", "请选择导出路径。")
            return
        self._params = ExportParams(
            burn=burn,
            excel=excel,
            export_directory=Path(text),
            mark_used=self._mark_used_check.isChecked(),
        )
        self.accept()
