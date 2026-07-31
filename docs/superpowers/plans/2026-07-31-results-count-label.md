# 结果表底部数量统计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在结果表下方左侧、与「导出」同一行，显示 `共 N 条，已选 M 条`，并随查询/生成/选中变化即时更新。

**Architecture:** 在现有 `bottom_row` 的 stretch 之前插入单个 `QLabel`（`_count_label`）；新增 `_update_count_label`，由 `_update_action_buttons` 调用（已接 `itemSelectionChanged`）。`_populate_table` 末尾已调 `_update_action_buttons`，无需另挂信号。

**Tech Stack:** PySide6；pytest + 既有 `qapp` fixture。

## Global Constraints

- 文案格式：`共 N 条，已选 M 条`（始终显示，含 `共 0 条，已选 0 条`）
- N = `self._table.rowCount()`；M = `len(self._selected_sns())`
- 布局：`[_count_label] …stretch… [改状态] [导出]`
- 不改导出/改状态启用条件、筛选、列定义
- 规格来源：`docs/superpowers/specs/2026-07-31-results-count-label-design.md`

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/gui/main_window.py` | `_count_label` 布局；`_update_count_label`；接入 `_update_action_buttons` |
| `tests/test_results_count_label.py` | 启动文案、填充与选中后文案 |

---

### Task 1: 数量标签与刷新

**Files:**
- Create: `tests/test_results_count_label.py`
- Modify: `src/sn_manager/gui/main_window.py`（`_build_results_panel` 的 `bottom_row`；`_update_action_buttons`）

**Interfaces:**
- Consumes: `MainWindow._selected_sns() -> list[str]`；`MainWindow._populate_table`；`MainWindow._table`
- Produces: `MainWindow._count_label: QLabel`；`MainWindow._update_count_label() -> None`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_results_count_label.py`：

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def _sample_rows(sns: list[str]) -> list[dict]:
    return [
        {
            "sn": sn,
            "product_model": "SVG14",
            "hw_batch": "05",
            "factory": "1",
            "market": "0",
            "prod_year": 2026,
            "prod_month": 7,
            "prod_day": 31,
            "seq": i,
            "status": "unused",
            "created_at": "2026-07-31T01:02:03Z",
            "updated_at": "2026-07-31T01:02:03Z",
        }
        for i, sn in enumerate(sns, start=1)
    ]


def test_count_label_zero_on_startup(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    assert win._count_label.text() == "共 0 条，已选 0 条"


def test_count_label_after_populate_and_select(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    rows = _sample_rows(
        ["SN000000000000001", "SN000000000000002", "SN000000000000003"]
    )
    win._rows = rows
    win._populate_table(rows)
    assert win._count_label.text() == "共 3 条，已选 0 条"

    model = win._table.selectionModel()
    table_model = win._table.model()
    assert model is not None and table_model is not None
    model.clearSelection()
    for row_idx in (0, 2):
        model.select(
            table_model.index(row_idx, 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
    assert win._count_label.text() == "共 3 条，已选 2 条"

    win._on_select_all()
    assert win._count_label.text() == "共 3 条，已选 3 条"

    model.clearSelection()
    assert win._count_label.text() == "共 3 条，已选 0 条"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_results_count_label.py -v`

Expected: FAIL（`AttributeError: '_count_label'` 或类似）

- [ ] **Step 3: 最小实现**

在 `_build_results_panel` 中，将：

```python
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self._change_status_btn = QPushButton("改状态")
        self._export_btn = QPushButton("导出")
```

改为：

```python
        bottom_row = QHBoxLayout()
        self._count_label = QLabel("共 0 条，已选 0 条")
        bottom_row.addWidget(self._count_label)
        bottom_row.addStretch()
        self._change_status_btn = QPushButton("改状态")
        self._export_btn = QPushButton("导出")
```

在 `_update_action_buttons` 旁新增并接入：

```python
    def _update_count_label(self) -> None:
        n = self._table.rowCount()
        m = len(self._selected_sns())
        self._count_label.setText(f"共 {n} 条，已选 {m} 条")

    def _update_action_buttons(self) -> None:
        has_selection = bool(self._selected_sns())
        self._change_status_btn.setEnabled(has_selection)
        self._export_btn.setEnabled(has_selection)
        self._update_count_label()
```

（`_populate_table` 末尾已调用 `_update_action_buttons()`，无需再改。）

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_results_count_label.py -v`

Expected: PASS（2 passed）

再跑相关回归：

Run: `uv run pytest tests/test_export_dialog.py::test_main_window_action_buttons_disabled_without_selection tests/test_results_table_beijing_time.py tests/test_table_selection_ux.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_results_count_label.py docs/superpowers/plans/2026-07-31-results-count-label.md
git commit -m "$(cat <<'EOF'
feat(gui): show result and selection counts under results table

EOF
)"
```

（若本 plan 文件尚未入库，与实现一并加入；若已单独提交 plan，则 commit 仅含实现与测试。）

---

## Spec coverage (self-review)

| Spec 要求 | Task |
| --------- | ---- |
| 左侧 `共 N 条，已选 M 条` 与导出同行 | Task 1 Step 3 |
| 启动 `共 0 条，已选 0 条` | Task 1 测试 + 初始文案 |
| 查询/填充后 N；选中/全选后 M | Task 1 测试 |
| 经 `_update_action_buttons` / `_populate_table` 刷新 | Task 1 Step 3 |
| 非目标：不改导出启用等 | 未改启用逻辑，仅追加 label 刷新 |

无 TBD/TODO；接口名 `_count_label` / `_update_count_label` 前后一致。
