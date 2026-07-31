# 表格选中样式与主数据添加聚焦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 结果表选中行为浅天蓝且无焦点框；主数据保留默认选中灰、去掉焦点框，并在「添加」后立即进入首单元格编辑。

**Architecture:** 两处 `QTableWidget` 各自设置 QSS（结果表覆盖 selected + focus；主数据仅 focus）。主数据 `_add_row` 在插入空行后 `setCurrentCell` + `editItem`。不抽公共样式模块。

**Tech Stack:** PySide6 `QTableWidget` / `QTableWidgetItem` / `QAbstractItemView`；pytest + 既有 `qapp` fixture。

## Global Constraints

- 结果表选中色：`#87CEFA`（浅天蓝）
- 结果表与主数据：`item:focus` 去掉 outline/border（无蓝色焦点框）
- 主数据：不覆盖 `item:selected`（保持系统默认浅灰）
- 「添加」后立刻进入新行第 0 列编辑态
- 规格来源：`docs/superpowers/specs/2026-07-31-table-selection-ux-design.md`
- 不改落库/筛选/多选语义；不引入全局主题模块

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/gui/main_window.py` | 结果表 QSS：selected `#87CEFA` + 去 focus 框 |
| `src/sn_manager/gui/master_data_dialog.py` | 主数据表 QSS 去 focus 框；`_add_row` 自动编辑 |
| `tests/test_export_dialog.py` 或新建 `tests/test_table_selection_ux.py` | 结果表样式断言（优先新建独立测试文件，避免拖长 export 测试） |
| `tests/test_master_data_dialog.py` | 主数据样式 + 添加后进入编辑态 |

---

### Task 1: 结果表选中样式

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`（`_build_results_panel` 内 `_table` 配置处，约 217–226 行）
- Create: `tests/test_table_selection_ux.py`

**Interfaces:**
- Consumes: `MainWindow._table`（已有）
- Produces: `_table.styleSheet()` 含 `#87CEFA` 与 `item:focus` 规则

- [x] **Step 1: 写失败测试**

创建 `tests/test_table_selection_ux.py`：

```python
from pathlib import Path

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_results_table_selection_stylesheet(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    ss = win._table.styleSheet().replace(" ", "")
    assert "#87CEFA" in ss
    assert "item:focus" in ss
    assert "outline:none" in ss
```

- [x] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_table_selection_ux.py::test_results_table_selection_stylesheet -v`

Expected: FAIL（stylesheet 为空或不含 `#87CEFA`）

- [x] **Step 3: 最小实现**

在 `main_window.py` 的 `_build_results_panel` 中，于 `setEditTriggers(...)` 之后、`header` 配置之前（或之后均可）增加：

```python
        self._table.setStyleSheet(
            """
            QTableWidget::item:selected {
                background-color: #87CEFA;
                color: black;
            }
            QTableWidget::item:focus {
                outline: none;
                border: none;
            }
            """
        )
```

- [x] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_table_selection_ux.py::test_results_table_selection_stylesheet -v`

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_table_selection_ux.py
git commit -m "$(cat <<'EOF'
feat(gui): 结果表选中行使用浅天蓝并去掉焦点框

EOF
)"
```

---

### Task 2: 主数据焦点样式与添加后自动编辑

**Files:**
- Modify: `src/sn_manager/gui/master_data_dialog.py`（`_configure_table`、`_add_row`）
- Modify: `tests/test_master_data_dialog.py`

**Interfaces:**
- Consumes: `_configure_table(table)`、`_add_row(table)`（已有）
- Produces: 各主数据表 stylesheet 含 focus 去边框且**不含** `#87CEFA`；`_add_row` 后 `currentRow`/`currentColumn` 指向新行第 0 列且处于编辑态

- [x] **Step 1: 写失败测试**

在 `tests/test_master_data_dialog.py` 末尾追加：

```python
from PySide6.QtWidgets import QAbstractItemView


def test_master_tables_focus_stylesheet_keeps_default_selection(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    dlg = MasterDataDialog(SnService(conn))
    for table in (
        dlg._model_table,
        dlg._batch_table,
        dlg._factory_table,
        dlg._market_table,
    ):
        ss = table.styleSheet()
        assert "focus" in ss
        assert "outline" in ss
        assert "#87CEFA" not in ss


def test_master_add_row_starts_editing_first_cell(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    dlg = MasterDataDialog(SnService(conn))
    table = dlg._model_table
    before = table.rowCount()
    dlg._add_row(table)
    assert table.rowCount() == before + 1
    assert table.currentRow() == before
    assert table.currentColumn() == 0
    assert table.state() == QAbstractItemView.State.EditingState
```

将 `QAbstractItemView` 的 import 合并到文件顶部既有 `PySide6.QtWidgets` import 中。

- [x] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_master_data_dialog.py::test_master_tables_focus_stylesheet_keeps_default_selection tests/test_master_data_dialog.py::test_master_add_row_starts_editing_first_cell -v`

Expected: FAIL（无 stylesheet / 未进入 EditingState）

- [x] **Step 3: 最小实现**

修改 `_configure_table`：

```python
    def _configure_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setStyleSheet(
            """
            QTableWidget::item:focus {
                outline: none;
                border: none;
            }
            """
        )
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
```

修改 `_add_row`：

```python
    def _add_row(self, table: QTableWidget) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for col in range(table.columnCount()):
            table.setItem(row, col, QTableWidgetItem(""))
        table.setCurrentCell(row, 0)
        item = table.item(row, 0)
        if item is not None:
            table.editItem(item)
```

- [x] **Step 4: 运行相关测试确认通过**

Run: `uv run pytest tests/test_master_data_dialog.py tests/test_table_selection_ux.py -v`

Expected: 全部 PASS（含既有 cancel/accept 用例；`_add_row` 后 `setItem` 仍可用）

- [x] **Step 5: Commit**

```bash
git add src/sn_manager/gui/master_data_dialog.py tests/test_master_data_dialog.py
git commit -m "$(cat <<'EOF'
feat(gui): 主数据去掉焦点框并在添加后立即编辑

EOF
)"
```

---

### Task 3: 手工冒烟（可选但推荐）

**Files:** 无代码改动

- [ ] **Step 1: 启动 GUI**

Run: `uv run python -m sn_manager`

- [ ] **Step 2: 核对三点**

1. 查询出若干行后单击/全选：选中行为 `#87CEFA`，无蓝焦点框  
2. 打开主数据 → 选中行：浅灰底，无蓝焦点框  
3. 点「添加」：可直接键入，无需再点单元格  

- [ ] **Step 3: 若冒烟通过且尚有未提交的规格/计划文档，按需一并提交（仅当用户要求 commit 时）**

可提交：

- `docs/superpowers/specs/2026-07-31-table-selection-ux-design.md`
- `docs/superpowers/plans/2026-07-31-table-selection-ux.md`
