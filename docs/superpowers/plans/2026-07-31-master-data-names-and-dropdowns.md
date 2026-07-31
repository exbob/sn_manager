# 主数据名称与下拉筛选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 四类主数据统一「编码 + 名称」（名称 ≤64）；筛选与生成仅能下拉选择主数据，不能临时新增。

**Architecture:** Schema 为型号/批次增加 `name`；db 层统一 `validate_name` 与带名称 upsert；`MasterSnapshot` 四类均为 `(code, name)` 并用 `_sync_named`；GUI 主数据四 Tab 两列，筛选/生成用不可编辑 `QComboBox`（展示 `编码 名称`）。开发期不迁移旧库。

**Tech Stack:** Python ≥3.12、SQLite、PySide6、pytest、uv。

## Global Constraints

- 名称：去首尾空白后非空；长度 ≤ 64（Unicode 字符）；可中文；不参与 SN 编码
- 筛选/生成：型号、批次、单位、市场仅不可编辑下拉；主数据是唯一编辑入口
- 生成不再 `_ensure_master` / 临时写入主数据
- 不做旧库迁移（删 `sn_manager.db` 重建）
- 规格：`docs/superpowers/specs/2026-07-31-master-data-names-and-dropdowns-design.md`
- 同步修订：`docs/PRD.md`、`docs/superpowers/specs/2026-07-30-sn-manager-design.md`

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/db/schema.py` | DDL：型号/批次加 `name` |
| `src/sn_manager/db/master_data.py` | `validate_name`；upsert 带 `name` |
| `src/sn_manager/app/services.py` | `MasterSnapshot` 改类型；四类 `_sync_named`；去掉 `_ensure_master` |
| `src/sn_manager/gui/master_data_dialog.py` | 型号/批次改为两列表；收集 `(code, name)` |
| `src/sn_manager/gui/generate_dialog.py` | 四项不可编辑下拉，`编码 名称` |
| `src/sn_manager/gui/main_window.py` | 筛选四项下拉；主数据确认后刷新 |
| `tests/test_db_master.py` 等 | 适配名称 API 与新行为 |
| `docs/PRD.md`、`docs/superpowers/specs/2026-07-30-sn-manager-design.md` | 文档同步 |

---

### Task 1: Schema 与主数据名称校验 / upsert

**Files:**
- Modify: `src/sn_manager/db/schema.py`
- Modify: `src/sn_manager/db/master_data.py`
- Modify: `tests/test_db_master.py`

**Interfaces:**
- Produces:
  - `NAME_MAX_LENGTH: int = 64`
  - `validate_name(name: str, field_label: str = "名称") -> str`（strip；空则 `ValidationError`；`len > 64` 则 `ValidationError`）
  - `upsert_product(conn, code: str, name: str, *, commit: bool = True) -> None`
  - `upsert_hardware_batch(conn, code: str, name: str, *, commit: bool = True) -> None`
  - `add_product_model(conn, code: str, name: str) -> None`
  - `add_hardware_batch(conn, code: str, name: str) -> None`
  - `upsert_factory` / `upsert_market`：写入前调用 `validate_name`

- [ ] **Step 1: 写失败测试**

在 `tests/test_db_master.py` 中，把既有调用改为带名称，并新增名称校验测试：

```python
def test_add_and_list_product(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "svg14", "示例外壳机")
    row = md.list_product_models(conn)[0]
    assert row["code"] == "SVG14"
    assert row["name"] == "示例外壳机"


def test_upsert_rejects_empty_product_name(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="名称不能为空"):
        md.upsert_product(conn, "SVG14", "  ")


def test_upsert_rejects_long_product_name(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="名称长度不能超过64"):
        md.upsert_product(conn, "SVG14", "中" * 65)


def test_upsert_factory_rejects_long_name(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="名称长度不能超过64"):
        md.upsert_factory(conn, "9", "x" * 65)
```

同步改写本文件内其它 `add_product_model(conn, "...")` 为传入名称（如 `"测试型号"`）；`upsert_product(conn, "ABC")` 长度失败用例改为 `upsert_product(conn, "ABC", "短")`。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_db_master.py -v`

Expected: FAIL（schema 无 name、或 upsert 签名不匹配）

- [ ] **Step 3: 最小实现**

`schema.py` 中：

```sql
CREATE TABLE IF NOT EXISTS product_models (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hardware_batches (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
```

`master_data.py` 增加：

```python
NAME_MAX_LENGTH = 64


def validate_name(name: str, field_label: str = "名称") -> str:
    normalized = name.strip()
    if not normalized:
        raise ValidationError(f"{field_label}不能为空")
    if len(normalized) > NAME_MAX_LENGTH:
        raise ValidationError(f"{field_label}长度不能超过{NAME_MAX_LENGTH}")
    return normalized
```

`upsert_product` / `upsert_hardware_batch` 增加 `name` 参数，校验后：

```python
conn.execute(
    "INSERT OR REPLACE INTO product_models (code, name) VALUES (?, ?)",
    (normalized, validate_name(name)),
)
```

`upsert_factory` / `upsert_market` 在写入前对 `name` 调用 `validate_name`。

- [ ] **Step 4: 测试通过**

Run: `uv run pytest tests/test_db_master.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/db/schema.py src/sn_manager/db/master_data.py tests/test_db_master.py
git commit -m "$(cat <<'EOF'
feat(db): 型号与批次增加名称并统一名称校验

EOF
)"
```

---

### Task 2: SnService 快照类型与去掉 ensure_master

**Files:**
- Modify: `src/sn_manager/app/services.py`
- Modify: `tests/test_services.py`
- Modify: `tests/test_master_data_dialog.py`（仅 `MasterSnapshot` / `add_product_model` 调用处，若本任务跑全量失败则一并改）

**Interfaces:**
- Consumes: `md.validate_name`、`md.upsert_product(conn, code, name, commit=...)`、`md.upsert_hardware_batch(...)`
- Produces:
  - `MasterSnapshot.product_models: list[tuple[str, str]]`
  - `MasterSnapshot.hardware_batches: list[tuple[str, str]]`
  - `generate(..., ensure_master` 参数删除）；删除 `_ensure_master`
  - `replace_master_data`：型号/批次改走 `_sync_named`

- [ ] **Step 1: 写失败 / 更新测试**

`tests/test_services.py`：

```python
def test_generate_and_filter(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "05", "第五批")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="svg14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    assert len(rows) == 1
    assert rows[0]["sn"] == "ASVG140521261C000"
    found = svc.filter(product_model="SVG14")
    assert len(found) == 1


def test_generate_does_not_insert_master_data(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    assert md.list_product_models(conn) == []
    svc.generate(
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 1, 12),
        count=1,
    )
    assert md.list_product_models(conn) == []
    assert md.list_hardware_batches(conn) == []


def test_replace_master_data_rolls_back_on_referenced_delete(tmp_path: Path):
    # ... 前置 upsert_product(conn, "SVG14", "...") 与 "OTHER"
    snapshot = MasterSnapshot(
        product_models=[("OTHER", "其它")],
        hardware_batches=[],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    # 断言不变


def test_replace_master_data_rejects_invalid_product_code(tmp_path: Path):
    snapshot = MasterSnapshot(
        product_models=[("ABC", "短")],
        hardware_batches=[],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    # 期望 ValidationError 产品型号长度


def test_replace_master_data_rejects_long_name(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=[("SVG14", "中" * 65)],
        hardware_batches=[],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    with pytest.raises(ValidationError, match="名称长度不能超过64"):
        svc.replace_master_data(snapshot)
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_services.py -v`

Expected: FAIL（`MasterSnapshot` 类型或仍有 `ensure_master` 写入）

- [ ] **Step 3: 最小实现**

```python
@dataclass(frozen=True)
class MasterSnapshot:
    product_models: list[tuple[str, str]]
    hardware_batches: list[tuple[str, str]]
    factories: list[tuple[str, str]]
    markets: list[tuple[str, str]]
```

`generate`：删除 `ensure_master` 参数与 `_ensure_master` 调用及方法体。

`replace_master_data`：型号/批次改为 `_sync_named`，upsert 传入 name：

```python
self._sync_named(
    md.list_product_models,
    set(validated.product_models),
    md.delete_product_model,
    lambda code, name: md.upsert_product(self.conn, code, name, commit=False),
    commit=False,
)
# hardware_batches 同理
```

可删除仅被型号/批次使用的 `_sync_codes`（若已无调用方）。

`_validate_snapshot`：

```python
return MasterSnapshot(
    product_models=[
        (md.validate_product_code(code), md.validate_name(name))
        for code, name in snapshot.product_models
    ],
    hardware_batches=[
        (md.validate_hardware_batch_code(code), md.validate_name(name))
        for code, name in snapshot.hardware_batches
    ],
    factories=[
        (md.validate_factory_code(code), md.validate_name(name))
        for code, name in snapshot.factories
    ],
    markets=[
        (md.validate_market_code(code), md.validate_name(name))
        for code, name in snapshot.markets
    ],
)
```

- [ ] **Step 4: 测试通过**

Run: `uv run pytest tests/test_services.py tests/test_db_master.py -v`

Expected: PASS（若 `test_master_data_dialog` 因快照类型失败，留到 Task 3 修复）

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/app/services.py tests/test_services.py
git commit -m "$(cat <<'EOF'
feat(app): 主数据快照统一带名称并取消生成时写入主数据

EOF
)"
```

---

### Task 3: 主数据对话框四类均为编码 + 名称

**Files:**
- Modify: `src/sn_manager/gui/master_data_dialog.py`
- Modify: `tests/test_master_data_dialog.py`

**Interfaces:**
- Consumes: `MasterSnapshot(product_models=[(code,name), ...], ...)`
- Produces: 型号/批次表两列；`_collect_snapshot` 返回带名称快照

- [ ] **Step 1: 更新测试**

```python
def test_master_data_dialog_cancel_does_not_write(qapp, tmp_path: Path):
    # ...
    dlg._add_row(dlg._model_table)
    row = dlg._model_table.rowCount() - 1
    dlg._model_table.setItem(row, 0, QTableWidgetItem("NEW01"))
    dlg._model_table.setItem(row, 1, QTableWidgetItem("新品"))
    dlg.reject()
    assert md.list_product_models(conn) == []


def test_master_data_dialog_accept_writes_new_model(qapp, tmp_path: Path):
    # ...
    dlg._model_table.setItem(row, 0, QTableWidgetItem("svg14"))
    dlg._model_table.setItem(row, 1, QTableWidgetItem("示例外壳机"))
    dlg._on_accept()
    rows = md.list_product_models(conn)
    assert [(r["code"], r["name"]) for r in rows] == [("SVG14", "示例外壳机")]


def test_master_data_dialog_reject_empty_name(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    dlg = MasterDataDialog(SnService(conn))
    dlg._add_row(dlg._model_table)
    row = dlg._model_table.rowCount() - 1
    dlg._model_table.setItem(row, 0, QTableWidgetItem("SVG14"))
    dlg._model_table.setItem(row, 1, QTableWidgetItem(""))
    warnings: list[tuple] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
    dlg._on_accept()
    assert warnings
    assert "名称" in warnings[0][2]
    assert md.list_product_models(conn) == []


def test_apply_master_data_alias(qapp, tmp_path: Path):
    snapshot = MasterSnapshot(
        product_models=[("ABC12", "样机")],
        hardware_batches=[("01", "一批")],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    # ...
```

引用删除用例中的 `md.add_product_model(conn, "SVG14")` 改为带名称。

断言 `dlg._model_table.columnCount() == 2`（可放在 loads 测试中）。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_master_data_dialog.py -v`

Expected: FAIL（仍为一列表或 snapshot 类型错误）

- [ ] **Step 3: 最小实现**

- `_model_table` / `_batch_table` 改为 `_make_named_table("型号编码", "名称")` / `_make_named_table("批次编码", "名称")`
- 删除 `_make_code_table`、`_fill_code_table`、`_collect_codes`（若无引用）
- `_load_from_db` 对型号/批次调用 `_fill_named_table`
- `_collect_snapshot` 四类均 `_collect_named`

- [ ] **Step 4: 测试通过**

Run: `uv run pytest tests/test_master_data_dialog.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/master_data_dialog.py tests/test_master_data_dialog.py
git commit -m "$(cat <<'EOF'
feat(gui): 主数据型号与批次支持名称编辑

EOF
)"
```

---

### Task 4: 生成对话框仅下拉选择

**Files:**
- Modify: `src/sn_manager/gui/generate_dialog.py`
- Modify: `tests/test_generate_dialog.py`

**Interfaces:**
- Consumes: `md.list_product_models` / `list_hardware_batches`（含 `name`）
- Produces: 型号/批次不可编辑；`currentData()` 取编码；展示 `f"{code} {name}"`

- [ ] **Step 1: 更新测试**

```python
def test_generate_dialog_loads_named_items(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "05", "第五批")
    dlg = GenerateDialog(SnService(conn))
    assert dlg._model_combo.isEditable() is False
    assert dlg._batch_combo.isEditable() is False
    assert dlg._model_combo.itemText(0) == "SVG14 示例外壳机"
    assert dlg._model_combo.itemData(0) == "SVG14"
    assert dlg._batch_combo.itemText(0) == "05 第五批"
    assert dlg._factory_combo.itemText(0).startswith("1 ")


def test_generate_dialog_returns_params_on_accept(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "05", "第五批")
    dlg = GenerateDialog(SnService(conn))
    dlg._model_combo.setCurrentIndex(0)
    dlg._batch_combo.setCurrentIndex(0)
    dlg._factory_combo.setCurrentIndex(0)
    dlg._market_combo.setCurrentIndex(0)
    dlg._count_spin.setValue(3)
    dlg._on_accept()
    params = dlg.params()
    assert params is not None
    assert params.product_model == "SVG14"
    assert params.hw_batch == "05"
    assert params.count == 3


def test_generate_dialog_warns_when_model_missing(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    dlg = GenerateDialog(SnService(conn))
    warnings: list[tuple] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
    dlg._on_accept()
    assert warnings
    assert "主数据" in warnings[0][2]
```

`test_main_window_generate_*` 仍可用 stub，无需改对话框加载；若 generate 服务依赖主数据行则保持 stub 直接调服务（当前不依赖）。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_generate_dialog.py -v`

Expected: FAIL（仍 editable 或用 currentText）

- [ ] **Step 3: 最小实现**

- 去掉型号/批次 `setEditable(True)`
- `_load_master_data`：四类均 `addItem(f"{code} {name}", code)`
- `_on_accept`：用 `currentData()`；若任一 `currentData()` 为 `None` 或 index < 0，提示：`请先在主数据中维护型号、批次、单位与市场。`（或对空列表更具体：「请选择型号」等；空列表与未选统一指向主数据即可）

```python
product_model = self._model_combo.currentData()
hw_batch = self._batch_combo.currentData()
factory = self._factory_combo.currentData()
market = self._market_combo.currentData()
if not product_model or not hw_batch or not factory or not market:
    QMessageBox.warning(self, "生成", "请先在主数据中维护并选择型号、批次、单位与市场。")
    return
```

- [ ] **Step 4: 测试通过**

Run: `uv run pytest tests/test_generate_dialog.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/generate_dialog.py tests/test_generate_dialog.py
git commit -m "$(cat <<'EOF'
feat(gui): 生成对话框型号批次改为仅下拉选择

EOF
)"
```

---

### Task 5: 主界面筛选下拉与主数据后刷新

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`
- Modify: `tests/test_master_data_dialog.py` 或新建 `tests/test_filter_combos.py`（优先新建，避免拖长）

**Interfaces:**
- Consumes: `md.list_*`
- Produces: `_model_combo` 等四项；`_reload_filter_master_combos()`；`_build_criteria` 用 `currentData()`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_filter_combos.py`：

```python
from pathlib import Path

from PySide6.QtWidgets import QComboBox, QDialog

from sn_manager.app.services import SnService
from sn_manager.db import master_data as md
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_filter_fields_are_combos_with_blank(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    win = MainWindow(SnService(conn))
    assert isinstance(win._model_combo, QComboBox)
    assert win._model_combo.isEditable() is False
    assert win._model_combo.itemText(0) == ""
    assert win._model_combo.itemData(0) in (None, "")
    assert win._model_combo.findData("SVG14") > 0
    assert "SVG14 示例外壳机" in [
        win._model_combo.itemText(i) for i in range(win._model_combo.count())
    ]


def test_build_criteria_uses_combo_data(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "05", "第五批")
    win = MainWindow(SnService(conn))
    win._model_combo.setCurrentIndex(win._model_combo.findData("SVG14"))
    win._batch_combo.setCurrentIndex(win._batch_combo.findData("05"))
    win._factory_combo.setCurrentIndex(win._factory_combo.findData("1"))
    win._market_combo.setCurrentIndex(win._market_combo.findData("0"))
    criteria = win._build_criteria()
    assert criteria["product_model"] == "SVG14"
    assert criteria["hw_batch"] == "05"
    assert criteria["factory"] == "1"
    assert criteria["market"] == "0"


def test_master_data_accept_reloads_filter_combos(qapp, tmp_path: Path, monkeypatch):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    win = MainWindow(svc)

    class _AcceptDialog:
        def __init__(self, service, parent=None) -> None:
            md.upsert_product(service.conn, "ZZZ99", "新机")

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("sn_manager.gui.main_window.MasterDataDialog", _AcceptDialog)
    win._on_master_data()
    assert win._model_combo.findData("ZZZ99") > 0
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_filter_combos.py -v`

Expected: FAIL（仍为 `QLineEdit` / 无 `_model_combo`）

- [ ] **Step 3: 最小实现**

在 `_build_filter_panel`：将 `_model_edit` 等改为 `QComboBox()`，`setEditable(False)`。

增加：

```python
def _reload_filter_master_combos(self) -> None:
    def fill(combo: QComboBox, rows: list[dict]) -> None:
        current = combo.currentData()
        combo.clear()
        combo.addItem("", None)
        for row in rows:
            combo.addItem(f"{row['code']} {row['name']}", row["code"])
        idx = combo.findData(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    conn = self._service.conn
    fill(self._model_combo, md.list_product_models(conn))
    fill(self._batch_combo, md.list_hardware_batches(conn))
    fill(self._factory_combo, md.list_factories(conn))
    fill(self._market_combo, md.list_markets(conn))
```

构造筛选面板末尾或 `__init__` 中调用一次 `_reload_filter_master_combos()`。

`_build_criteria`：

```python
if code := self._model_combo.currentData():
    criteria["product_model"] = code
# batch / factory / market 同理
```

`_on_master_data`：若 `dialog.exec()` 为 Accepted，调用 `_reload_filter_master_combos()`。

导入 `master_data as md`（若尚未导入）。

- [ ] **Step 4: 测试通过**

Run: `uv run pytest tests/test_filter_combos.py tests/test_master_data_dialog.py tests/test_generate_dialog.py tests/test_services.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_filter_combos.py
git commit -m "$(cat <<'EOF'
feat(gui): 筛选条件型号批次单位市场改为下拉

EOF
)"
```

---

### Task 6: 同步 PRD 与既有设计文档 + 全量测试

**Files:**
- Modify: `docs/PRD.md`
- Modify: `docs/superpowers/specs/2026-07-30-sn-manager-design.md`

**Interfaces:** 无代码接口；文档与规格一致。

- [ ] **Step 1: 修订 PRD**

在 `docs/PRD.md`：

- 主数据表：`product_models` / `hardware_batches` 增加 `name`；注明四类名称非空、≤64
- 「主数据维护」：删除「生成对话框内可临时新增」；改为四类仅在主数据对话框维护；生成/筛选仅下拉
- 「生成 SN」：选（非填）型号/批次等
- 「查询」：型号/批次/单位/市场仅下拉
- 「关键流程」：去掉「必要时写入主数据」

示例表行：

```markdown
| `product_models` | `code` CHAR(5) UNIQUE, `name` | 产品型号，如 SVG14 / 名称说明含义（≤64） |
| `hardware_batches` | `code` CHAR(2) UNIQUE, `name` | 硬件批次，如 05 / 名称说明含义（≤64） |
| `factories` | `code` CHAR(1) UNIQUE, `name` | 生产单位；名称 ≤64 |
| `markets` | `code` CHAR(1) UNIQUE, `name` | 市场；名称 ≤64 |
```

- [ ] **Step 2: 修订 2026-07-30 设计文档**

- 决策表「主数据」行：改为对话框维护；生成/筛选仅下拉，不可临时新增
- §4.1：型号/批次 schema 含 `name`；名称规则
- 生成流程步骤：删除「临时新增并保存」

- [ ] **Step 3: 全量回归**

Run: `uv run pytest -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add docs/PRD.md docs/superpowers/specs/2026-07-30-sn-manager-design.md
git commit -m "$(cat <<'EOF'
docs: 同步主数据名称与下拉筛选的 PRD 与设计

EOF
)"
```

---

## Self-Review

1. **Spec coverage:** 名称必填≤64、四类统一、筛选/生成下拉、去掉 ensure_master、PRD+旧设计同步、无迁移 —— 均有对应 Task。
2. **Placeholders:** 无 TBD；关键代码与命令已写出。
3. **Types:** `MasterSnapshot` 四类均为 `list[tuple[str, str]]`；upsert 均带 `name`；GUI 用 `currentData()` 取编码。
