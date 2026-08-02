# 查询结果分页与查询中态 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 查询/翻页每次最多向结果表填充 200 行，并在加载中显示「查询中…」、禁用易误点按钮，避免大数据量下 UI 卡死与误操作。

**Architecture:** 在 `filter_serials` 增加 `LIMIT`/`OFFSET`，新增同条件 `count_serials`；主窗口用 DB 分页浏览查询结果，生成结果用内存切片分页；加载中走 `_set_query_busy` + `processEvents`，不做后台线程。

**Tech Stack:** Python 3 + PySide6 + SQLite；pytest + 既有 `qapp` / `tmp_path` fixture。

## Global Constraints

- 页大小固定：`PAGE_SIZE = 200`（模块常量，不可调）
- 页码从 **1** 起；`P = max(1, ceil(N / 200))`；`N = 0` 时 `P = 1`
- 全选 / 改状态 / 导出仅当前页
- 文案：`共 N 条，已选 M 条`（N=总匹配数，M=当前页选中数）；页码为 `第 p / P 页`
- 查询中按钮文案：`查询中…`（中文省略号）
- 无 schema 变更；旧 `sn_manager.db` 兼容
- 规格来源：`docs/superpowers/specs/2026-08-02-query-pagination-design.md`

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/db/serials.py` | 抽取 WHERE 构建；`count_serials`；`filter_serials` 的 limit/offset |
| `src/sn_manager/app/services.py` | `filter(limit=, offset=)` 透传；`count(**criteria)` |
| `src/sn_manager/gui/main_window.py` | 分页状态、翻页控件、busy 态、查询/生成填表 |
| `tests/test_db_serials.py` | count / limit / offset / 负值 |
| `tests/test_services.py` | service.count / filter 分页透传（若已有文件则追加） |
| `tests/test_query_pagination.py` | GUI 分页、busy、数量标签 N、生成内存分页 |
| `tests/test_results_count_label.py` | 适配 N=`_total_count` |
| `docs/user-manual.md` | §6 补充分页与查询中说明 |

---

### Task 1: 数据库层 count + LIMIT/OFFSET

**Files:**
- Modify: `src/sn_manager/db/serials.py`
- Modify: `tests/test_db_serials.py`

**Interfaces:**
- Produces:
  - `count_serials(conn: sqlite3.Connection, **filters: Any) -> int`
  - `filter_serials(conn, *, limit: int | None = None, offset: int | None = None, **filters: Any) -> list[dict[str, Any]]`
  - 内部 `_build_filter_clause(filters: dict[str, Any]) -> tuple[list[str], list[Any]]` 返回 conditions 列表与 params

- [ ] **Step 1: 写失败测试**

在 `tests/test_db_serials.py` 追加：

```python
def test_filter_limit_offset_and_count(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    ser.allocate_and_insert(
        conn,
        product_model="SVG14",
        hw_batch="05",
        factory="1",
        market="0",
        prod_date=date(2026, 8, 2),
        count=5,
    )
    assert ser.count_serials(conn) == 5
    assert ser.count_serials(conn, product_model="SVG14") == 5
    assert ser.count_serials(conn, product_model="ZZZZZ") == 0

    page1 = ser.filter_serials(conn, limit=2, offset=0)
    page2 = ser.filter_serials(conn, limit=2, offset=2)
    page3 = ser.filter_serials(conn, limit=2, offset=4)
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    all_sns = [r["sn"] for r in ser.filter_serials(conn)]
    assert [r["sn"] for r in page1] + [r["sn"] for r in page2] + [
        r["sn"] for r in page3
    ] == all_sns

    # 无 limit 时行为不变（全量）
    assert len(ser.filter_serials(conn)) == 5


def test_filter_limit_offset_rejects_negative(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValueError):
        ser.filter_serials(conn, limit=-1)
    with pytest.raises(ValueError):
        ser.filter_serials(conn, limit=1, offset=-1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_db_serials.py::test_filter_limit_offset_and_count tests/test_db_serials.py::test_filter_limit_offset_rejects_negative -v`

Expected: FAIL（`count_serials` 不存在或 `limit` 被当成 unknown filter）

- [ ] **Step 3: 实现**

在 `serials.py`：

1. 把现有 `filter_serials` 里构建 `conditions`/`params` 的循环抽成 `_build_filter_clause(filters: dict[str, Any]) -> tuple[list[str], list[Any]]`（遇 unknown key 仍 `ValueError`）。
2. `count_serials`：

```python
def count_serials(conn: sqlite3.Connection, **filters: Any) -> int:
    conditions, params = _build_filter_clause(filters)
    sql = "SELECT COUNT(*) AS n FROM serial_numbers"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    row = conn.execute(sql, params).fetchone()
    return int(row["n"])
```

3. `filter_serials` 签名改为显式 keyword-only 的 limit/offset，**不要**把它们放进 `**filters`：

```python
def filter_serials(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    offset: int | None = None,
    **filters: Any,
) -> list[dict[str, Any]]:
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")
    if offset is not None and offset < 0:
        raise ValueError("offset must be >= 0")
    if offset is not None and limit is None:
        raise ValueError("offset requires limit")
    conditions, params = _build_filter_clause(filters)
    sql = "SELECT * FROM serial_numbers"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY created_at DESC, sn"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, 0 if offset is None else offset])
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
```

注意：既有调用 `filter_serials(conn, sn=sn)` 等仍合法（keyword filters）。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_db_serials.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/db/serials.py tests/test_db_serials.py
git commit -m "feat(db): add count_serials and filter limit/offset"
```

---

### Task 2: SnService 透传

**Files:**
- Modify: `src/sn_manager/app/services.py`
- Modify: `tests/test_services.py`（若无分页相关测试则追加；文件已存在）

**Interfaces:**
- Consumes: `ser.count_serials`、`ser.filter_serials`
- Produces:
  - `SnService.filter(self, *, limit: int | None = None, offset: int | None = None, **criteria: Any) -> list[dict[str, Any]]`
  - `SnService.count(self, **criteria: Any) -> int`

- [ ] **Step 1: 写失败测试**

在 `tests/test_services.py` 追加（按该文件既有风格导入；型号/批次码与该文件其它成功用例保持一致）：

```python
def test_service_count_and_filter_pagination(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="1",
        market="0",
        prod_date=date(2026, 8, 2),
        count=3,
    )
    assert svc.count() == 3
    assert len(svc.filter(limit=2, offset=0)) == 2
    assert len(svc.filter(limit=2, offset=2)) == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_services.py::test_service_count_and_filter_pagination -v`

Expected: FAIL（`count` 不存在或 `filter` 不接受 limit）

- [ ] **Step 3: 实现**

```python
def filter(
    self,
    *,
    limit: int | None = None,
    offset: int | None = None,
    **criteria: Any,
) -> list[dict[str, Any]]:
    return ser.filter_serials(self.conn, limit=limit, offset=offset, **criteria)

def count(self, **criteria: Any) -> int:
    return ser.count_serials(self.conn, **criteria)
```

`generate` 内 `ser.filter_serials(self.conn, sn=sn)` 不变。

- [ ] **Step 4: 跑通相关测试**

Run: `uv run pytest tests/test_services.py tests/test_db_serials.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/app/services.py tests/test_services.py
git commit -m "feat(app): expose SnService.count and filter pagination"
```

---

### Task 3: 主窗口分页 UI、查询中态、数量标签 N

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`
- Create: `tests/test_query_pagination.py`
- Modify: `tests/test_results_count_label.py`

**Interfaces:**
- Consumes: `SnService.count`、`SnService.filter(limit=, offset=)`
- Produces（`MainWindow`）:
  - 模块常量 `PAGE_SIZE = 200`
  - `_total_count: int`、`_page: int`、`_query_criteria: dict[str, Any]`、`_memory_rows: list[dict] | None`（None=DB 模式）
  - `_prev_page_btn`、`_next_page_btn`、`_page_label`
  - `_set_query_busy(busy: bool) -> None`
  - `_page_count() -> int`
  - `_update_page_controls() -> None`
  - `_load_db_page(*, show_busy: bool) -> None`
  - `_show_memory_page() -> None`
  - `_on_query` / `_on_prev_page` / `_on_next_page`
  - `_update_count_label`：`f"共 {self._total_count} 条，已选 {len(self._selected_sns())} 条"`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_query_pagination.py`：

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import sn_manager.gui.main_window as mw
from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_query_paginates_and_count_is_total(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mw, "PAGE_SIZE", 2)
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="1",
        market="0",
        prod_date=date(2026, 8, 2),
        count=5,
    )
    win = MainWindow(svc)
    win._on_query()
    assert win._total_count == 5
    assert win._table.rowCount() == 2
    assert win._count_label.text() == "共 5 条，已选 0 条"
    assert win._page_label.text() == "第 1 / 3 页"
    assert not win._prev_page_btn.isEnabled()
    assert win._next_page_btn.isEnabled()

    win._on_next_page()
    assert win._page == 2
    assert win._table.rowCount() == 2
    assert win._page_label.text() == "第 2 / 3 页"
    assert win._prev_page_btn.isEnabled()

    win._on_next_page()
    assert win._page == 3
    assert win._table.rowCount() == 1
    assert not win._next_page_btn.isEnabled()

    win._on_select_all()
    assert win._count_label.text() == "共 5 条，已选 1 条"


def test_set_query_busy_updates_chrome(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win._set_query_busy(True)
    assert win._query_btn.text() == "查询中…"
    assert not win._query_btn.isEnabled()
    assert not win._generate_btn.isEnabled()
    assert not win._master_btn.isEnabled()
    assert not win._select_all_btn.isEnabled()
    assert not win._prev_page_btn.isEnabled()
    assert not win._next_page_btn.isEnabled()
    win._set_query_busy(False)
    assert win._query_btn.text() == "查询"
    assert win._query_btn.isEnabled()
```

更新 `tests/test_results_count_label.py` 中 `test_count_label_after_populate_and_select`：在 `_populate_table` 前设置 `win._total_count = 3`。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_query_pagination.py tests/test_results_count_label.py -v`

Expected: FAIL（缺控件 / 缺方法 / 数量文案仍用 rowCount）

- [ ] **Step 3: 实现主窗口**

1. 文件顶部增加 `PAGE_SIZE = 200`；在 QtWidgets import 中加入 `QApplication`（若尚未导入）。
2. `MainWindow.__init__`（或构建 UI 后）初始化：

```python
self._total_count = 0
self._page = 1
self._query_criteria: dict[str, Any] = {}
self._memory_rows: list[dict[str, Any]] | None = None
```

3. `_build_results_panel` 底部行改为：

```text
[_count_label] [_prev_page_btn] [_page_label] [_next_page_btn] …stretch… [改状态] [导出]
```

- `_prev_page_btn = QPushButton("上一页")`
- `_next_page_btn = QPushButton("下一页")`
- `_page_label = QLabel("第 1 / 1 页")`
- 初始禁用上一页/下一页

4. `_wire_signals` 连接上一页/下一页。

5. 辅助方法：

```python
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

def _update_count_label(self) -> None:
    n = self._total_count
    m = len(self._selected_sns())
    self._count_label.setText(f"共 {n} 条，已选 {m} 条")

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
```

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/test_query_pagination.py tests/test_results_count_label.py tests/test_status_colors.py tests/test_results_table_beijing_time.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_query_pagination.py tests/test_results_count_label.py
git commit -m "feat(gui): paginate query results with busy state"
```

---

### Task 4: 生成结果内存分页

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`（`_on_generate`）
- Modify: `tests/test_query_pagination.py`

**Interfaces:**
- Consumes: `_show_memory_page`、`PAGE_SIZE`、`_total_count`、`_memory_rows`
- Produces: `_apply_generated_rows(rows) -> None`；`_on_generate` 成功后调用它

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_query_pagination.py`：

```python
def test_generate_uses_memory_pagination(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mw, "PAGE_SIZE", 2)
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    win = MainWindow(svc)
    rows = svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="1",
        market="0",
        prod_date=date(2026, 8, 2),
        count=5,
    )
    win._apply_generated_rows(rows)
    assert win._memory_rows is not None
    assert win._total_count == 5
    assert win._table.rowCount() == 2
    assert len(win._selected_sns()) == 2
    win._on_next_page()
    assert win._page == 2
    assert win._query_btn.text() == "查询"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_query_pagination.py::test_generate_uses_memory_pagination -v`

Expected: FAIL（缺 `_apply_generated_rows`）

- [ ] **Step 3: 实现**

```python
def _apply_generated_rows(self, rows: list[dict[str, Any]]) -> None:
    self._memory_rows = rows
    self._total_count = len(rows)
    self._page = 1
    self._query_criteria = {}
    self._show_memory_page()
    self._table.selectAll()

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
```

确认内存翻页路径不调用 `_set_query_busy`。`_on_query` 开头 `self._memory_rows = None` 切回 DB 模式。

- [ ] **Step 4: 全量回归**

Run: `uv run pytest -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_query_pagination.py
git commit -m "feat(gui): paginate generated SN rows in memory"
```

---

### Task 5: 使用手册

**Files:**
- Modify: `docs/user-manual.md`（§6 查询）

- [ ] **Step 1: 更新文案**

将 §6 中步骤 2–3 与「多选与全选」改为：

```markdown
2. 点击 **查询**。查询进行中时按钮显示「查询中…」，相关操作按钮暂不可用。
3. 右侧显示匹配结果（**每页最多 200 条**）；可用 **上一页** / **下一页** 浏览。底部显示 `共 N 条，已选 M 条`（N 为总匹配数，M 为当前页选中数），并显示 `第 p / P 页`。

### 多选与全选

- 单击选中一行；可用 Ctrl / Shift 多选（与常见桌面表格一致）。
- **全选**：选中**当前页**结果表中的全部行（跨页需翻页后分别操作；改状态 / 导出同样仅作用于当前页选中行）。
- 未选中任何行时，**改状态**与**导出**按钮为禁用状态。
```

- [ ] **Step 2: 目视确认无过时「全表即全部结果」表述**

- [ ] **Step 3: Commit**

```bash
git add docs/user-manual.md
git commit -m "docs: document query pagination and busy state"
```

---

## Spec coverage (self-review)

| Spec 项 | Task |
| -------- | ---- |
| LIMIT/OFFSET + count | Task 1–2 |
| 每页 200、翻页 UI | Task 3 |
| 仅当前页操作 | Task 3–4 |
| N=总数 M=本页选中 | Task 3 |
| 查询中… + 禁用 | Task 3 |
| 生成内存分页、翻页不 busy | Task 4 |
| 再查询退出内存模式 | Task 3 `_on_query` |
| 错误结束 busy + MessageBox | Task 3 |
| 手册 | Task 5 |
| 不做线程/跨页全选/可调页大小 | 未列入任务 |

## Placeholder / type check

- `PAGE_SIZE`、`_memory_rows`、`_apply_generated_rows`、`count`/`filter` 签名在各 Task 一致
- 测试用 `monkeypatch` 将 `PAGE_SIZE` 改为 2，避免插入数百行
