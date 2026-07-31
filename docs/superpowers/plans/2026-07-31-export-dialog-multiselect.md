# 导出对话框多选与共用路径 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 导出对话框支持烧写/Excel 多选、共用导出目录（默认应用目录）、默认「导出后标为已使用」，且勾选类型全部写成功后才标 `used`。

**Architecture:** `paths.app_dir()` 统一应用目录；`ExportParams` 改为 `burn`/`excel`/`export_directory`/`mark_used`；`export_selected_and_mark_used` 编排写出顺序与 mark used；对话框用双复选框 + 单路径；主窗口只调编排函数。

**Tech Stack:** Python ≥3.12、PySide6、openpyxl、pytest。

## Global Constraints

- 导出路径始终为**目录**；Excel 文件名确认时本地时间 `YYYYMMDDHHmmss.xlsx`
- 烧写在上、Excel 在下；默认仅烧写；至少选一种
- mark used 默认勾选；全部勾选类型写成功后才 `set_status(..., USED)`
- 写出顺序：先烧写、后 Excel；失败保留已写文件、不改状态
- 规格：`docs/superpowers/specs/2026-07-31-export-dialog-multiselect-design.md`；PRD：`docs/PRD.md` §4/§5
- 中文 GUI 文案；不改 Excel 列与 `sn_<SN>.txt` 命名

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/app/paths.py` | 新增 `app_dir()`；`default_db_path` 复用 |
| `tests/test_paths.py` | `app_dir` / `default_db_path` 行为 |
| `src/sn_manager/app/export.py` | 新增 `export_selected_and_mark_used`；可保留或薄封装旧 `export_burn_and_mark_used` |
| `tests/test_export.py` | 编排：双选成功 mark used；第二步失败不 mark |
| `src/sn_manager/gui/export_dialog.py` | 双复选框 + 共用路径 + 新 `ExportParams` |
| `tests/test_export_dialog.py` | 对话框默认值、校验、params；主窗口导出用例适配 |
| `src/sn_manager/gui/main_window.py` | `_on_export` 改用新 params / 编排函数 |

---

### Task 1: `app_dir()` + 复用 `default_db_path`

**Files:**
- Modify: `src/sn_manager/app/paths.py`
- Create: `tests/test_paths.py`

**Interfaces:**
- Consumes: `sys`、`pathlib.Path`
- Produces: `app_dir() -> Path`；`default_db_path() -> Path`（= `app_dir() / "sn_manager.db"`）

- [ ] **Step 1: 写失败单测**

Create `tests/test_paths.py`：

```python
from pathlib import Path

import sn_manager.app.paths as paths_mod
from sn_manager.app.paths import app_dir, default_db_path


def test_app_dir_cwd_when_not_frozen(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths_mod.sys, "frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)
    assert app_dir() == tmp_path.resolve()
    assert default_db_path() == tmp_path.resolve() / "sn_manager.db"


def test_app_dir_executable_parent_when_frozen(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "dist" / "sn_manager"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_mod.sys, "executable", str(exe))
    assert app_dir() == exe.resolve().parent
    assert default_db_path() == exe.resolve().parent / "sn_manager.db"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_paths.py -v`  
Expected: FAIL（`app_dir` 未定义）

- [ ] **Step 3: 实现 `app_dir` 并改写 `default_db_path`**

`src/sn_manager/app/paths.py`：

```python
"""应用层路径约定。"""

from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    """可执行文件所在目录；开发未打包时为当前工作目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def default_db_path() -> Path:
    """返回默认 SQLite 数据库路径。"""
    return app_dir() / "sn_manager.db"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_paths.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/app/paths.py tests/test_paths.py
git commit -m "$(cat <<'EOF'
feat: extract app_dir for default export and db paths

EOF
)"
```

---

### Task 2: `export_selected_and_mark_used` 编排

**Files:**
- Modify: `src/sn_manager/app/export.py`
- Modify: `tests/test_export.py`

**Interfaces:**
- Consumes: `export_burn_txt`、`export_excel`、`SnService.set_status`、`Status.USED`
- Produces:

```python
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
```

说明：时间戳文件名在 GUI 确认时生成并传入 `excel_path`，避免编排层依赖「当前时间」难测；当 `excel=True` 且 `excel_path is None` 时用 `export_directory / datetime.now().strftime("%Y%m%d%H%M%S.xlsx")` 作为回退。

保留 `export_burn_and_mark_used` 为对编排的薄封装（或改为调用新函数），避免无谓破坏既有单测；优先让新测试覆盖双选路径。

- [ ] **Step 1: 写失败单测**

在 `tests/test_export.py` 追加：

```python
from datetime import datetime
from sn_manager.app.export import export_selected_and_mark_used


def test_export_selected_both_mark_used(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    sn = rows[0]["sn"]
    xlsx = tmp_path / "20260731152950.xlsx"

    export_selected_and_mark_used(
        svc,
        rows,
        burn=True,
        excel=True,
        export_directory=tmp_path,
        mark_used=True,
        excel_path=xlsx,
    )

    assert (tmp_path / f"sn_{sn}.txt").read_text(encoding="utf-8") == sn
    assert load_workbook(xlsx).active["A2"].value == sn
    assert svc.filter(sn=sn)[0]["status"] == Status.USED.value


def test_export_selected_excel_failure_does_not_mark_used(tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    sn = rows[0]["sn"]

    def boom(*_a, **_k):
        raise OSError("excel failed")

    monkeypatch.setattr("sn_manager.app.export.export_excel", boom)

    with pytest.raises(OSError):
        export_selected_and_mark_used(
            svc,
            rows,
            burn=True,
            excel=True,
            export_directory=tmp_path,
            mark_used=True,
            excel_path=tmp_path / "out.xlsx",
        )

    assert (tmp_path / f"sn_{sn}.txt").exists()
    assert svc.filter(sn=sn)[0]["status"] == Status.UNUSED.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_export.py::test_export_selected_both_mark_used tests/test_export.py::test_export_selected_excel_failure_does_not_mark_used -v`  
Expected: FAIL（函数未定义）

- [ ] **Step 3: 实现编排函数**

在 `export.py` 增加（示意）：

```python
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
    from datetime import datetime

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
```

将 `export_burn_and_mark_used` 改为调用本函数（`burn=True, excel=False`），保持旧测试通过。

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_export.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/app/export.py tests/test_export.py
git commit -m "$(cat <<'EOF'
feat: orchestrate multi-type export before mark used

EOF
)"
```

---

### Task 3: 重写 `ExportDialog` + 单测

**Files:**
- Modify: `src/sn_manager/gui/export_dialog.py`
- Modify: `tests/test_export_dialog.py`（对话框相关用例；主窗口用例可同文件稍后 Task 4 改）

**Interfaces:**
- Consumes: `app_dir()`、`QCheckBox`、`QFileDialog.getExistingDirectory`
- Produces:

```python
@dataclass(frozen=True)
class ExportParams:
    burn: bool
    excel: bool
    export_directory: Path
    mark_used: bool
```

删除 `ExportMode`。

- [ ] **Step 1: 写/改失败单测（对话框部分）**

替换 `tests/test_export_dialog.py` 中依赖旧 `ExportMode`/`excel_path`/`burn_directory` 的对话框测试为：

```python
from sn_manager.app.paths import app_dir
from sn_manager.gui.export_dialog import ExportDialog, ExportParams


def test_export_dialog_defaults(qapp):
    dlg = ExportDialog()
    assert dlg._burn_check.isChecked()
    assert not dlg._excel_check.isChecked()
    assert dlg._mark_used_check.isChecked()
    assert dlg._path_edit.text() == str(app_dir())


def test_export_dialog_returns_params_on_accept(qapp):
    dlg = ExportDialog()
    dlg._burn_check.setChecked(True)
    dlg._excel_check.setChecked(True)
    dlg._path_edit.setText("/tmp/out")
    dlg._mark_used_check.setChecked(False)
    dlg._on_accept()
    assert dlg.params() == ExportParams(
        burn=True,
        excel=True,
        export_directory=Path("/tmp/out"),
        mark_used=False,
    )


def test_export_dialog_rejects_no_type(qapp, monkeypatch):
    dlg = ExportDialog()
    warnings: list[tuple] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
    dlg._burn_check.setChecked(False)
    dlg._excel_check.setChecked(False)
    dlg._on_accept()
    assert dlg.params() is None
    assert warnings


def test_export_dialog_rejects_empty_path(qapp, monkeypatch):
    dlg = ExportDialog()
    warnings: list[tuple] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
    dlg._path_edit.setText("   ")
    dlg._on_accept()
    assert dlg.params() is None
    assert warnings
```

（暂时保留主窗口旧用例会失败，Task 4 一并改；本 Task 可先只跑上述四个，或本 Task 末尾连同 Task 4 一起绿。）

- [ ] **Step 2: Run dialog tests expecting fail**

Run: `uv run pytest tests/test_export_dialog.py::test_export_dialog_defaults tests/test_export_dialog.py::test_export_dialog_returns_params_on_accept -v`  
Expected: FAIL（旧 API / 缺控件）

- [ ] **Step 3: 实现对话框**

要点：

- `_burn_check` 文案「烧写文本 (sn_<SN>.txt)」；`_excel_check`「导出 Excel (.xlsx)」
- 表单一行「导出路径」：`_path_edit` + 浏览 → `getExistingDirectory`
- `_path_edit` 初始 `str(app_dir())`
- `_mark_used_check` 默认勾选
- `_on_accept`：校验类型与路径后写 `ExportParams`

- [ ] **Step 4: Run dialog unit tests**

Run: `uv run pytest tests/test_export_dialog.py::test_export_dialog_defaults tests/test_export_dialog.py::test_export_dialog_returns_params_on_accept tests/test_export_dialog.py::test_export_dialog_rejects_no_type tests/test_export_dialog.py::test_export_dialog_rejects_empty_path -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/export_dialog.py tests/test_export_dialog.py
git commit -m "$(cat <<'EOF'
feat: multiselect export dialog with shared directory path

EOF
)"
```

---

### Task 4: 主窗口接线 + 集成测试

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`（`_on_export` 与 import）
- Modify: `tests/test_export_dialog.py`（主窗口导出相关 mock/断言）

**Interfaces:**
- Consumes: `ExportDialog`、`ExportParams`、`export_selected_and_mark_used`、`datetime`
- Produces: `_on_export` 行为符合 spec

- [ ] **Step 1: 改写主窗口导出测试**

将 `test_main_window_export_excel_selected_rows`、`test_main_window_export_burn_mark_used`、`test_main_window_export_burn_failure_shows_warning` 改为使用新 `ExportParams`，并 mock `export_selected_and_mark_used` 或真实写出：

```python
class _AcceptedExportDialog:
    def __init__(self, parent=None) -> None:
        self._params = ExportParams(
            burn=False,
            excel=True,
            export_directory=tmp_path,
            mark_used=False,
        )
    # exec / params 同前
```

Excel 用例需 monkeypatch 时间或直接断言目录下存在匹配 `^\d{14}\.xlsx$` 的文件（若 `_on_export` 用 `datetime.now()` 生成路径再交给编排）。  
Burn+mark_used 用例：`burn=True, excel=False, mark_used=True`。  
失败用例：monkeypatch `export_selected_and_mark_used` 抛 `OSError`，断言 warning 且状态 unused。

- [ ] **Step 2: 实现 `_on_export`**

```python
from datetime import datetime
from sn_manager.app.export import export_selected_and_mark_used
from sn_manager.gui.export_dialog import ExportDialog

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
    except OSError as exc:
        QMessageBox.warning(self, "导出失败", str(exc))
```

去掉对 `ExportMode` / `export_excel` / `export_burn_and_mark_used` 的直接依赖（若别处不用）。

- [ ] **Step 3: 跑相关测试**

Run: `uv run pytest tests/test_export.py tests/test_export_dialog.py tests/test_paths.py -v`  
Expected: PASS

- [ ] **Step 4: 全量回归（可选但推荐）**

Run: `uv run pytest -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_export_dialog.py
git commit -m "$(cat <<'EOF'
feat: wire main window to multiselect export flow

EOF
)"
```

---

### Task 5: 文档状态收尾

**Files:**
- Modify: `docs/superpowers/specs/2026-07-31-export-dialog-multiselect-design.md`（状态 → 已确认；实现完成后可再标「已实现」若团队有此惯例）
- 确认：`docs/PRD.md` 已与行为一致（本会话已改，实现后对照一遍）

- [ ] **Step 1: 实现全部通过后，将 spec 状态改为「已确认」或「已实现」**
- [ ] **Step 2: Commit docs if needed**

```bash
git add docs/PRD.md docs/superpowers/specs/2026-07-31-export-dialog-multiselect-design.md docs/superpowers/plans/2026-07-31-export-dialog-multiselect.md
git commit -m "$(cat <<'EOF'
docs: export multiselect PRD, spec, and plan

EOF
)"
```

（若文档已在实现前单独提交，本 Task 仅更新状态字段。）

---

## Spec coverage（自审）

| Spec 要求 | Task |
| ---- | ---- |
| 双复选框、烧写默认、顺序 | Task 3 |
| 共用目录路径 + `app_dir` 默认 | Task 1 + 3 |
| mark used 默认勾选 | Task 3 |
| Excel `YYYYMMDDHHmmss.xlsx` | Task 4（生成）+ Task 2（写出） |
| 先 burn 后 excel；失败不 mark | Task 2 |
| 主窗口接线 / 刷新 | Task 4 |
| PRD 已修订 | 实现前已完成；Task 5 复核 |

## Placeholder scan

无 TBD/TODO；类型名在 Task 间一致：`ExportParams`、`export_selected_and_mark_used`、`app_dir`。
