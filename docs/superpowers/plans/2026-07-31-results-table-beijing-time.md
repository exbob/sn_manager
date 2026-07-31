# 结果表列顺序与北京时间显示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 结果表列改为「序号 → 创建时间 → 状态 → 更新时间」；标题改为「结果表」；增加默认勾选的「北京时间」开关，勾选时两时间列显示 Asia/Shanghai 墙钟。

**Architecture:** 库与导出仍存/出 UTC。GUI 层增加纯函数 `format_display_timestamp`；`_populate_table` / `_refresh_rows_for_sns` 经共用 `_cell_display` 按勾选状态格式化。勾选切换重绘当前 `_rows` 并恢复选中 SN。

**Tech Stack:** PySide6；`datetime` + `zoneinfo.ZoneInfo("Asia/Shanghai")`；pytest + 既有 `qapp` fixture。

## Global Constraints

- 列顺序（序号之后）：创建时间 → 状态 → 更新时间
- 标题文案：`结果表`（去掉「（可多选）」）
- 「北京时间」复选框默认勾选；不持久化
- 勾选显示：`YYYY-MM-DD HH:MM:SS`（Asia/Shanghai）；未勾选：库内 UTC 原文
- 切换勾选：不重新查库；重绘后恢复选中 SN
- 导出 / 落库仍为 UTC；不改 schema
- 规格来源：`docs/superpowers/specs/2026-07-31-results-table-beijing-time-design.md`

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/gui/main_window.py` | 列定义、标题行勾选、时间格式化与展示 |
| `tests/test_results_table_beijing_time.py` | 格式化函数 + 主窗口列/勾选/显示行为 |

---

### Task 1: `format_display_timestamp` 纯函数

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`（模块级，`_TABLE_COLUMNS` 附近）
- Create: `tests/test_results_table_beijing_time.py`

**Interfaces:**
- Consumes: 无
- Produces: `format_display_timestamp(raw: str, *, use_beijing: bool) -> str`

- [x] **Step 1: 写失败测试**

创建 `tests/test_results_table_beijing_time.py`：

```python
from __future__ import annotations

from sn_manager.gui.main_window import format_display_timestamp


def test_format_display_timestamp_passthrough_when_utc() -> None:
    raw = "2026-07-31T01:02:03Z"
    assert format_display_timestamp(raw, use_beijing=False) == raw


def test_format_display_timestamp_beijing_from_z() -> None:
    # UTC 01:02:03 → 北京 09:02:03
    assert (
        format_display_timestamp("2026-07-31T01:02:03Z", use_beijing=True)
        == "2026-07-31 09:02:03"
    )


def test_format_display_timestamp_beijing_from_offset() -> None:
    assert (
        format_display_timestamp("2026-07-31T01:02:03+00:00", use_beijing=True)
        == "2026-07-31 09:02:03"
    )


def test_format_display_timestamp_invalid_passthrough() -> None:
    raw = "not-a-timestamp"
    assert format_display_timestamp(raw, use_beijing=True) == raw
```

- [x] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_results_table_beijing_time.py -v -k format_display_timestamp`

Expected: FAIL（`format_display_timestamp` 未定义 / ImportError）

- [x] **Step 3: 最小实现**

在 `main_window.py` 顶部增加：

```python
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
```

（若已有 `from datetime import date, datetime`，合并为含 `timezone`。）

在 `_TABLE_COLUMNS` 之前增加：

```python
_BEIJING = ZoneInfo("Asia/Shanghai")


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
```

- [x] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_results_table_beijing_time.py -v -k format_display_timestamp`

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_results_table_beijing_time.py
git commit -m "$(cat <<'EOF'
feat(gui): add Beijing wall-clock timestamp display helper

EOF
)"
```

---

### Task 2: 列顺序、标题、「北京时间」与表格展示

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`（`_TABLE_COLUMNS`、`_build_results_panel`、`_wire_signals`、`_populate_table`、`_refresh_rows_for_sns`）
- Modify: `tests/test_results_table_beijing_time.py`

**Interfaces:**
- Consumes: `format_display_timestamp`（Task 1）
- Produces: `MainWindow._beijing_time_cb: QCheckBox`；`_cell_display(key, value) -> str`；勾选切换重绘并恢复选中

- [x] **Step 1: 写失败测试**

追加到 `tests/test_results_table_beijing_time.py`：

```python
from pathlib import Path

from PySide6.QtWidgets import QLabel

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow, _TABLE_COLUMNS


def test_table_columns_order() -> None:
    keys = [k for k, _ in _TABLE_COLUMNS]
    assert keys[-4:] == ["seq", "created_at", "status", "updated_at"]
    labels = [lab for _, lab in _TABLE_COLUMNS]
    assert labels[-4:] == ["序号", "创建时间", "状态", "更新时间"]


def test_results_header_label_and_beijing_checkbox_default(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    labels = [
        w.text()
        for w in win.findChildren(QLabel)
        if w.text().startswith("结果表")
    ]
    assert "结果表" in labels
    assert "结果表（可多选）" not in labels
    assert win._beijing_time_cb.isChecked() is True
    assert win._beijing_time_cb.text() == "北京时间"


def test_populate_table_formats_times_when_beijing_checked(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    row = {
        "sn": "A" * 17,
        "product_model": "SVG14",
        "hw_batch": "05",
        "factory": "1",
        "market": "0",
        "prod_year": 2026,
        "prod_month": 7,
        "prod_day": 31,
        "seq": 1,
        "status": "unused",
        "created_at": "2026-07-31T01:02:03Z",
        "updated_at": "2026-07-31T02:03:04Z",
    }
    win._populate_table([row])
    col = {k: i for i, (k, _) in enumerate(_TABLE_COLUMNS)}
    assert win._table.item(0, col["created_at"]).text() == "2026-07-31 09:02:03"
    assert win._table.item(0, col["updated_at"]).text() == "2026-07-31 10:03:04"
    assert win._table.item(0, col["status"]).text() == "未使用"


def test_toggle_beijing_shows_utc_and_restores_selection(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    rows = [
        {
            "sn": f"SN{i:015d}",
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
        for i in (1, 2)
    ]
    win._rows = rows
    win._populate_table(rows)
    win._table.selectRow(1)
    assert win._selected_sns() == ["SN000000000000002"]

    win._beijing_time_cb.setChecked(False)
    col = {k: i for i, (k, _) in enumerate(_TABLE_COLUMNS)}
    assert win._table.item(0, col["created_at"]).text() == "2026-07-31T01:02:03Z"
    assert win._selected_sns() == ["SN000000000000002"]
```

- [x] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_results_table_beijing_time.py -v`

Expected: FAIL（列顺序仍为旧顺序 / 无 `_beijing_time_cb` / 时间未转换）

- [x] **Step 3: 最小实现**

1. 改 `_TABLE_COLUMNS`：

```python
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
```

2. `_build_results_panel` 顶部行改为：

```python
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("结果表"))
        self._beijing_time_cb = QCheckBox("北京时间")
        self._beijing_time_cb.setChecked(True)
        top_row.addWidget(self._beijing_time_cb)
        top_row.addStretch()
        self._select_all_btn = QPushButton("全选")
        top_row.addWidget(self._select_all_btn)
```

3. 在 `MainWindow` 内增加共用展示与恢复选中：

```python
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
        for row_idx in range(self._table.rowCount()):
            item = self._table.item(row_idx, 0)
            if item is None:
                continue
            sn = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if sn in wanted:
                self._table.selectRow(row_idx)

    def _on_beijing_time_toggled(self, _checked: bool) -> None:
        if not self._rows:
            return
        selected = self._selected_sns()
        self._populate_table(self._rows)
        self._restore_selection(selected)
```

注意：多次 `selectRow` 在 `ExtendedSelection` 下会累加选中；若只恢复一行足够本测。多行恢复时应用 `QItemSelectionModel.Select | Rows` 累加，例如：

```python
    def _restore_selection(self, sns: list[str]) -> None:
        if not sns:
            return
        from PySide6.QtCore import QItemSelectionModel

        wanted = set(sns)
        self._table.clearSelection()
        model = self._table.selectionModel()
        if model is None:
            return
        for row_idx in range(self._table.rowCount()):
            item = self._table.item(row_idx, 0)
            if item is None:
                continue
            sn = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if sn in wanted:
                model.select(
                    self._table.model().index(row_idx, 0),
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
```

（`QItemSelectionModel` 可改到文件顶部 `from PySide6.QtCore import QDate, QItemSelectionModel, Qt`。）

4. `_wire_signals` 增加：

```python
        self._beijing_time_cb.toggled.connect(self._on_beijing_time_toggled)
```

5. `_populate_table` 中 `display` 改为 `self._cell_display(key, value)`；`_refresh_rows_for_sns` 同样替换原先 status/else 分支。

- [x] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_results_table_beijing_time.py -v`

Expected: PASS

另跑相关回归：

Run: `uv run pytest tests/test_export_dialog.py tests/test_table_selection_ux.py tests/test_main_window_version.py -v`

Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_results_table_beijing_time.py
git commit -m "$(cat <<'EOF'
feat(gui): reorder result columns and add Beijing time toggle

EOF
)"
```

---

## Spec coverage (self-review)

| Spec 要求 | Task |
| --------- | ---- |
| 列顺序 序号→创建时间→状态→更新时间 | Task 2 |
| 标题「结果表」 | Task 2 |
| 「北京时间」默认勾选 | Task 2 |
| 勾选墙钟 / 未勾选 UTC 原文 | Task 1 + 2 |
| 切换不查库、恢复选中 | Task 2 |
| 导出仍 UTC / 不改 schema | 非目标，未改 export/db |
| `_populate` 与 `_refresh` 共用展示逻辑 | Task 2 `_cell_display` |
| 解析失败原样 | Task 1 |

无 TBD/占位；签名与 Task 间一致。
