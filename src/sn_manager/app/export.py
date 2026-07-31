"""Excel 与烧写文本导出。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openpyxl import Workbook

from sn_manager.core.status import Status

if TYPE_CHECKING:
    from sn_manager.app.services import SnService

_EXCEL_COLUMNS = (
    "sn",
    "product_model",
    "hw_batch",
    "factory",
    "market",
    "prod_year",
    "prod_month",
    "prod_day",
    "seq",
    "status",
    "created_at",
    "updated_at",
)


def export_excel(rows: list[dict[str, Any]], path: Path) -> None:
    """将选中行导出为单文件 Excel。"""
    wb = Workbook()
    ws = wb.active
    ws.append(list(_EXCEL_COLUMNS))
    for row in rows:
        ws.append([row.get(col) for col in _EXCEL_COLUMNS])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def export_burn_txt(sns: list[str], directory: Path) -> list[Path]:
    """为每个 SN 写入 sn_<SN>.txt，内容一行 SN；已存在则覆盖。"""
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for sn in sns:
        path = directory / f"sn_{sn}.txt"
        path.write_text(sn, encoding="utf-8")
        paths.append(path)
    return paths


def export_selected_and_mark_used(
    svc: SnService,
    rows: list[dict[str, Any]],
    *,
    burn: bool,
    excel: bool,
    export_directory: Path,
    mark_used: bool,
    excel_path: Path | None = None,
) -> None:
    """按勾选写出；全部成功后可选标 used。excel_path 由调用方传入（含时间戳文件名）。"""
    if not burn and not excel:
        raise ValueError("at least one export type required")
    sns = [str(row["sn"]) for row in rows]
    if burn:
        export_burn_txt(sns, export_directory)
    if excel:
        path = excel_path or (
            export_directory / datetime.now().strftime("%Y%m%d%H%M%S.xlsx")
        )
        export_excel(rows, path)
    if mark_used:
        svc.set_status(sns, Status.USED)


def export_burn_and_mark_used(
    svc: SnService,
    sns: list[str],
    directory: Path,
    *,
    mark_used: bool,
) -> None:
    """先写完全部烧写文件，成功后再可选批量标为已使用。"""
    rows = [{"sn": sn} for sn in sns]
    export_selected_and_mark_used(
        svc,
        rows,
        burn=True,
        excel=False,
        export_directory=directory,
        mark_used=mark_used,
    )
