# 产品型号与硬件批次关联 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将硬件批次改为从属于产品型号（联合主键 + 按型号名称），并在主数据 / 生成 / 筛选中落实型号→批次联动。

**Architecture:** `hardware_batches` 改为 `(product_model, code)` 主键；db 层按型号过滤与按双键删除引用检查；`MasterSnapshot.hardware_batches` 变为 `(product_model, batch_code, name)`；主数据对话框在型号 Tab 内嵌套批次表；生成与筛选下拉随型号级联刷新。开发期不迁移旧库。

**Tech Stack:** Python ≥3.12、SQLite、PySide6、pytest、uv。

## Global Constraints

- 批次主键：`(product_model, code)`；同码可在不同型号下并存且名称不同
- 生成 / 筛选：未选型号时批次不可用；选了型号后批次仅该型号下项
- 主数据：三 Tab（型号 / 单位 / 市场）；型号 Tab 上下布局（型号表 + 当前型号批次表）
- 删除：有下属批次不可删型号；批次被 SN 引用（同型号+批次）不可删
- 不做旧库迁移（删 `sn_manager.db` 重建）
- 规格：`docs/superpowers/specs/2026-08-02-product-model-hardware-batch-link-design.md`
- 同步修订：`docs/PRD.md`、`docs/user-manual.md`
- 历史 spec（`2026-07-30` / `2026-07-31-master-data-names`）中「全局独立批次」以本规格为准，不必改历史正文

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/db/schema.py` | `hardware_batches` DDL 改为联合主键 |
| `src/sn_manager/db/master_data.py` | 按型号 list/upsert/delete；删型号检查下属批次；引用检查按双键 |
| `src/sn_manager/app/services.py` | `MasterSnapshot` 新形状；批次同步；生成前校验归属 |
| `src/sn_manager/gui/master_data_dialog.py` | 嵌套型号/批次 UI；收集三元组快照 |
| `src/sn_manager/gui/generate_dialog.py` | 型号变更刷批次下拉 |
| `src/sn_manager/gui/main_window.py` | 筛选型号→批次联动 |
| `tests/test_db_master.py` 等 | 适配新 API 与联动行为 |
| `docs/PRD.md`、`docs/user-manual.md` | 文档同步 |

---

### Task 1: Schema 与 db 层型号隶属批次 API

**Files:**
- Modify: `src/sn_manager/db/schema.py`
- Modify: `src/sn_manager/db/master_data.py`
- Modify: `tests/test_db_master.py`

**Interfaces:**
- Produces:
  - DDL: `hardware_batches(product_model TEXT NOT NULL, code TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY (product_model, code))`（不强制 SQL FOREIGN KEY）
  - `list_hardware_batches(conn, product_model: str | None = None) -> list[dict]`：行含 `product_model`, `code`, `name`；`product_model` 非空时过滤并规范化大写；排序 `ORDER BY product_model, code`
  - `upsert_hardware_batch(conn, product_model: str, code: str, name: str, *, commit: bool = True) -> None`：校验型号与批次编码；型号须已存在于 `product_models`，否则 `ValidationError`（文案含「产品型号」或不存在）
  - `add_hardware_batch(conn, product_model: str, code: str, name: str) -> None`
  - `delete_hardware_batch(conn, product_model: str, code: str, *, commit: bool = True) -> None`：若存在 SN `product_model=? AND hw_batch=?` 则 `ValidationError`（「已被序列号引用」）
  - `delete_product_model`：若该型号下仍有 `hardware_batches` 行，先 `ValidationError`（「请先删除该型号下的硬件批次」）；再检查 SN 对型号的引用（现有逻辑）
  - `hardware_batch_exists(conn, product_model: str, code: str) -> bool`：供服务层生成校验

- [ ] **Step 1: 写失败测试**

在 `tests/test_db_master.py` 增加/改写：

```python
def test_same_batch_code_different_models_and_names(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "示波器")
    md.add_product_model(conn, "SCP4A", "采集器")
    md.add_hardware_batch(conn, "SVG14", "01", "国产化FPGA")
    md.add_hardware_batch(conn, "SCP4A", "01", "国产Wi-Fi模块")
    svg = md.list_hardware_batches(conn, "SVG14")
    scp = md.list_hardware_batches(conn, "SCP4A")
    assert [(r["code"], r["name"]) for r in svg] == [("01", "国产化FPGA")]
    assert [(r["code"], r["name"]) for r in scp] == [("01", "国产Wi-Fi模块")]


def test_list_hardware_batches_all_includes_product_model(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "示波器")
    md.add_hardware_batch(conn, "SVG14", "01", "一批")
    rows = md.list_hardware_batches(conn)
    assert rows[0]["product_model"] == "SVG14"


def test_upsert_batch_requires_existing_product(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    with pytest.raises(ValidationError, match="产品型号"):
        md.upsert_hardware_batch(conn, "SVG14", "01", "一批")


def test_delete_product_with_batches_raises(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "示波器")
    md.add_hardware_batch(conn, "SVG14", "01", "一批")
    with pytest.raises(ValidationError, match="请先删除该型号下的硬件批次"):
        md.delete_product_model(conn, "SVG14")


def test_delete_batch_referenced_by_serial_raises(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "测试型号")
    md.add_hardware_batch(conn, "SVG14", "05", "第五批")
    conn.execute(
        "INSERT INTO serial_numbers("
        "sn, version, product_model, hw_batch, factory, market, "
        "prod_year, prod_month, prod_day, seq, status, created_at, updated_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "ASVG140521261CF000",
            "A",
            "SVG14",
            "05",
            "1",
            "0",
            2026,
            1,
            2,
            0,
            "unused",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
        ),
    )
    conn.commit()
    with pytest.raises(ValidationError, match="已被序列号引用"):
        md.delete_hardware_batch(conn, "SVG14", "05")


def test_delete_unreferenced_batch(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "示波器")
    md.add_hardware_batch(conn, "SVG14", "01", "一批")
    md.delete_hardware_batch(conn, "SVG14", "01")
    assert md.list_hardware_batches(conn, "SVG14") == []


def test_hardware_batch_exists(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "示波器")
    md.add_hardware_batch(conn, "SVG14", "01", "一批")
    assert md.hardware_batch_exists(conn, "svg14", "01") is True
    assert md.hardware_batch_exists(conn, "SVG14", "99") is False
```

并改写既有：

```python
def test_upsert_rejects_non_alnum_batch(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "示波器")
    with pytest.raises(ValidationError, match="硬件批次只能包含字母和数字"):
        md.upsert_hardware_batch(conn, "SVG14", "0!", "坏批次")
    assert md.list_hardware_batches(conn) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_db_master.py -v`

Expected: FAIL（旧 schema / 旧 `upsert_hardware_batch` 签名）

- [ ] **Step 3: 最小实现**

`schema.py` 中：

```sql
CREATE TABLE IF NOT EXISTS hardware_batches (
    product_model TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (product_model, code)
);
```

`master_data.py` 要点：

```python
def list_hardware_batches(
    conn: sqlite3.Connection, product_model: str | None = None
) -> list[dict[str, Any]]:
    if product_model is None:
        rows = conn.execute(
            "SELECT product_model, code, name FROM hardware_batches "
            "ORDER BY product_model, code"
        ).fetchall()
    else:
        model = validate_product_code(product_model)
        rows = conn.execute(
            "SELECT product_model, code, name FROM hardware_batches "
            "WHERE product_model = ? ORDER BY code",
            (model,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_hardware_batch(
    conn: sqlite3.Connection,
    product_model: str,
    code: str,
    name: str,
    *,
    commit: bool = True,
) -> None:
    model = validate_product_code(product_model)
    batch = validate_hardware_batch_code(code)
    exists = conn.execute(
        "SELECT 1 FROM product_models WHERE code = ? LIMIT 1", (model,)
    ).fetchone()
    if exists is None:
        raise ValidationError(f"产品型号不存在：{model}")
    conn.execute(
        "INSERT OR REPLACE INTO hardware_batches (product_model, code, name) "
        "VALUES (?, ?, ?)",
        (model, batch, validate_name(name)),
    )
    _maybe_commit(conn, commit=commit)


def delete_hardware_batch(
    conn: sqlite3.Connection,
    product_model: str,
    code: str,
    *,
    commit: bool = True,
) -> None:
    model = product_model.upper()
    batch = code.upper()
    row = conn.execute(
        "SELECT 1 FROM serial_numbers WHERE product_model = ? AND hw_batch = ? LIMIT 1",
        (model, batch),
    ).fetchone()
    if row is not None:
        raise ValidationError(f"编码 {batch} 已被序列号引用，无法删除")
    conn.execute(
        "DELETE FROM hardware_batches WHERE product_model = ? AND code = ?",
        (model, batch),
    )
    _maybe_commit(conn, commit=commit)


def delete_product_model(
    conn: sqlite3.Connection, code: str, *, commit: bool = True
) -> None:
    normalized = code.upper()
    child = conn.execute(
        "SELECT 1 FROM hardware_batches WHERE product_model = ? LIMIT 1",
        (normalized,),
    ).fetchone()
    if child is not None:
        raise ValidationError("请先删除该型号下的硬件批次")
    _assert_not_referenced(conn, "product_models", normalized)
    conn.execute("DELETE FROM product_models WHERE code = ?", (normalized,))
    _maybe_commit(conn, commit=commit)


def hardware_batch_exists(
    conn: sqlite3.Connection, product_model: str, code: str
) -> bool:
    model = validate_product_code(product_model)
    batch = validate_hardware_batch_code(code)
    row = conn.execute(
        "SELECT 1 FROM hardware_batches WHERE product_model = ? AND code = ? LIMIT 1",
        (model, batch),
    ).fetchone()
    return row is not None
```

注意：`list_codes` / `_REF_COLUMN` 对 `hardware_batches` 的旧「仅按 `hw_batch` 单列引用」路径不再用于 `delete_hardware_batch`；可保留 `_REF_COLUMN` 给其它表，或从 `_MASTER_TABLES` 特殊处理，避免 `list_codes(conn, "hardware_batches")` 被误用——推荐让 `list_hardware_batches` 不再调用 `list_codes`。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_db_master.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/db/schema.py src/sn_manager/db/master_data.py tests/test_db_master.py
git commit -m "$(cat <<'EOF'
feat(db): scope hardware batches under product models

EOF
)"
```

---

### Task 2: SnService 快照同步与生成归属校验

**Files:**
- Modify: `src/sn_manager/app/services.py`
- Modify: `tests/test_services.py`
- Modify: `tests/test_master_data_dialog.py`（仅 `MasterSnapshot` / `apply_master_data` 调用处，若本任务跑全量失败则一并改）

**Interfaces:**
- Consumes: Task 1 的 `list_hardware_batches` / `upsert_hardware_batch` / `delete_hardware_batch` / `hardware_batch_exists` / `delete_product_model`
- Produces:
  - `MasterSnapshot.hardware_batches: list[tuple[str, str, str]]` → `(product_model, batch_code, name)`
  - `replace_master_data`：先 upsert 全部型号；再按快照同步批次（删多余、upsert 目标）；再删快照中不存在的型号；再同步单位/市场；失败 rollback
  - `generate`：若 `not md.hardware_batch_exists(...)` 则 `ValidationError`（「所选硬件批次不属于该产品型号」）

- [ ] **Step 1: 写失败测试**

```python
def test_generate_and_filter(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "SVG14", "05", "第五批")
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


def test_generate_rejects_batch_not_under_model(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_product(conn, "SCP4A", "采集器")
    md.upsert_hardware_batch(conn, "SCP4A", "05", "别的批次")
    svc = SnService(conn)
    with pytest.raises(ValidationError, match="不属于该产品型号"):
        svc.generate(
            product_model="SVG14",
            hw_batch="05",
            factory="2",
            market="1",
            prod_date=date(2026, 1, 12),
            count=1,
        )


def test_generate_rejects_missing_master_pair(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    with pytest.raises(ValidationError, match="不属于该产品型号"):
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


def test_replace_master_data_with_scoped_batches(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=[("SVG14", "示波器"), ("SCP4A", "采集器")],
        hardware_batches=[
            ("SVG14", "01", "国产化FPGA"),
            ("SCP4A", "01", "国产Wi-Fi模块"),
        ],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    svc.replace_master_data(snapshot)
    assert [(r["code"], r["name"]) for r in md.list_hardware_batches(conn, "SVG14")] == [
        ("01", "国产化FPGA")
    ]
    assert [(r["code"], r["name"]) for r in md.list_hardware_batches(conn, "SCP4A")] == [
        ("01", "国产Wi-Fi模块")
    ]


def test_replace_master_data_refuses_delete_model_with_batches(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示波器")
    md.upsert_hardware_batch(conn, "SVG14", "01", "一批")
    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=[],
        hardware_batches=[],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    # 同步应先删批次再删型号；空快照应成功清空
    svc.replace_master_data(snapshot)
    assert md.list_product_models(conn) == []
    assert md.list_hardware_batches(conn) == []
```

将原 `test_generate_does_not_insert_master_data` 替换为上面的 `test_generate_rejects_missing_master_pair`。

所有 `MasterSnapshot(..., hardware_batches=[("01", "一批")])` 改为三元组，并保证对应型号也在 `product_models` 中。

`test_replace_master_data_rolls_back_on_referenced_delete`：快照去掉 `SVG14` 时，若库中有批次 `SVG14/05`，须先在准备数据里 upsert 批次，或保持无批次仅型号被 SN 引用——现有测试仅引用型号编码即可继续用 `hardware_batches=[]`。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_services.py -v`

Expected: FAIL（签名 / 校验未实现）

- [ ] **Step 3: 最小实现**

`MasterSnapshot`：

```python
@dataclass(frozen=True)
class MasterSnapshot:
    product_models: list[tuple[str, str]]
    hardware_batches: list[tuple[str, str, str]]
    factories: list[tuple[str, str]]
    markets: list[tuple[str, str]]
```

`generate` 开头：

```python
if not md.hardware_batch_exists(self.conn, product_model, hw_batch):
    raise ValidationError("所选硬件批次不属于该产品型号（或不存在）")
```

`replace_master_data` 同步逻辑（替换原 `_sync_named` 对批次的调用）：

```python
# 1) upsert all models in snapshot
for code, name in validated.product_models:
    md.upsert_product(self.conn, code, name, commit=False)

# 2) sync batches: delete existing not in desired; upsert desired
desired_batches = {
    (pm, bc): nm for pm, bc, nm in validated.hardware_batches
}
existing = {
    (r["product_model"], r["code"]) for r in md.list_hardware_batches(self.conn)
}
for key in existing - set(desired_batches):
    md.delete_hardware_batch(self.conn, key[0], key[1], commit=False)
for (pm, bc), nm in sorted(desired_batches.items()):
    md.upsert_hardware_batch(self.conn, pm, bc, nm, commit=False)

# 3) delete models not in snapshot (will fail if batches remain — already removed)
desired_models = {code for code, _ in validated.product_models}
existing_models = {r["code"] for r in md.list_product_models(self.conn)}
for code in existing_models - desired_models:
    md.delete_product_model(self.conn, code, commit=False)

# 4) factories / markets via existing _sync_named
```

`_validate_snapshot` 中：

```python
hardware_batches=[
    (
        md.validate_product_code(pm),
        md.validate_hardware_batch_code(bc),
        md.validate_name(name),
    )
    for pm, bc, name in snapshot.hardware_batches
],
```

并校验：每个批次的 `pm` 必须出现在本快照的 `product_models` 编码集合中，否则 `ValidationError`（「产品型号不存在」或「批次所属型号未在快照中」）。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_services.py tests/test_master_data_dialog.py::test_apply_master_data_alias -v`

Expected: PASS（`test_apply_master_data_alias` 已改为三元组）

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/app/services.py tests/test_services.py tests/test_master_data_dialog.py
git commit -m "$(cat <<'EOF'
feat(app): sync scoped batches and validate on generate

EOF
)"
```

---

### Task 3: 主数据对话框嵌套型号/批次

**Files:**
- Modify: `src/sn_manager/gui/master_data_dialog.py`
- Modify: `tests/test_master_data_dialog.py`

**Interfaces:**
- Consumes: `MasterSnapshot` 三元组；`md.list_product_models` / `list_hardware_batches`
- Produces: 三 Tab UI；型号选中驱动批次表；`_collect_snapshot` 产出全部型号下批次三元组

- [ ] **Step 1: 写失败测试**

```python
def test_master_data_dialog_has_three_tabs_no_batch_tab(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    dlg = MasterDataDialog(SnService(conn))
    tabs = dlg.findChild(__import__("PySide6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget)
    assert tabs is not None
    labels = [tabs.tabText(i) for i in range(tabs.count())]
    assert labels == ["型号", "单位", "市场"]


def test_master_data_dialog_batches_follow_selected_model(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "SVG14", "示波器")
    md.add_product_model(conn, "SCP4A", "采集器")
    md.add_hardware_batch(conn, "SVG14", "01", "国产化FPGA")
    md.add_hardware_batch(conn, "SCP4A", "01", "国产Wi-Fi模块")
    dlg = MasterDataDialog(SnService(conn))
    dlg._model_table.selectRow(0)
    dlg._on_model_selection_changed()
    codes = [
        dlg._batch_table.item(r, 0).text()
        for r in range(dlg._batch_table.rowCount())
    ]
    # 取决于排序：SVG14 在前
    assert codes == ["01"]
    assert dlg._batch_table.item(0, 1).text() == "国产化FPGA"


def test_master_data_dialog_accept_writes_scoped_batches(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    dlg = MasterDataDialog(SnService(conn))
    dlg._add_row(dlg._model_table)
    row = dlg._model_table.rowCount() - 1
    dlg._model_table.setItem(row, 0, QTableWidgetItem("SVG14"))
    dlg._model_table.setItem(row, 1, QTableWidgetItem("示波器"))
    dlg._model_table.selectRow(row)
    dlg._on_model_selection_changed()
    dlg._add_row(dlg._batch_table)
    dlg._batch_table.setItem(0, 0, QTableWidgetItem("01"))
    dlg._batch_table.setItem(0, 1, QTableWidgetItem("国产化FPGA"))
    # 将编辑中的批次写回内存缓存的关键：实现须在切型号/确认前 flush 当前批次表
    dlg._on_accept()
    batches = md.list_hardware_batches(conn, "SVG14")
    assert [(r["code"], r["name"]) for r in batches] == [("01", "国产化FPGA")]


def test_apply_master_data_alias(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    snapshot = MasterSnapshot(
        product_models=[("ABC12", "样机")],
        hardware_batches=[("ABC12", "01", "一批")],
        factories=[("1", "自己生产"), ("2", "赛威思")],
        markets=[("0", "不限"), ("1", "中国"), ("2", "韩国"), ("3", "美国")],
    )
    svc.apply_master_data(snapshot)
    assert [r["code"] for r in md.list_product_models(conn)] == ["ABC12"]
    assert md.list_hardware_batches(conn, "ABC12")[0]["name"] == "一批"
```

更新 `test_master_data_dialog_loads_seed_data`：不再断言独立批次 Tab 列数来自第四页；改为断言型号页存在 `_batch_table`。  
更新 `test_master_tables_use_no_focus_delegate`：仍检查 `_batch_table`。  
`test_master_data_dialog_referenced_delete_keeps_open`：清空型号表确认时，若无下属批次，仍因 SN 引用失败——保持即可。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_master_data_dialog.py -v`

Expected: FAIL（仍为四 Tab / 全局批次）

- [ ] **Step 3: 最小实现**

结构建议：

1. 去掉「批次」Tab。  
2. 型号 Tab 用垂直布局：上 `_model_table` + 添加/删除；下标签「硬件批次」+ `_batch_table` + 添加/删除。  
3. 内存字典 `_batches_by_model: dict[str, list[tuple[str, str]]]`，在 `_load_from_db` 从 `list_hardware_batches(conn)` 填入。  
4. `_on_model_selection_changed`：先把当前批次表写回 `_batches_by_model[旧型号]`；再加载新选中型号的批次到表；无选中则清空并禁用批次添加/删除。  
5. 切换型号前 / `_on_accept` 前必须 flush。  
6. `_collect_snapshot`：先 flush；收集型号；展开 `_batches_by_model` 为三元组；同型号内批次编码去重校验（重复则 `QMessageBox`「该型号下批次编码重复」）。  
7. 删除型号行时：同时丢掉 `_batches_by_model` 中对应项；若实现为「确认时才真正删库」，对话框内删行即可。

未选中型号时批次「添加」按钮 `setEnabled(False)`。

对话框可略增高：`self.resize(560, 520)`。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_master_data_dialog.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/master_data_dialog.py tests/test_master_data_dialog.py
git commit -m "$(cat <<'EOF'
feat(gui): nest hardware batches under model in master data

EOF
)"
```

---

### Task 4: 生成对话框型号→批次联动

**Files:**
- Modify: `src/sn_manager/gui/generate_dialog.py`
- Modify: `tests/test_generate_dialog.py`

**Interfaces:**
- Consumes: `md.list_hardware_batches(conn, product_model=...)`
- Produces: 型号 `currentIndexChanged` 时刷新批次；无型号时批次清空

- [ ] **Step 1: 写失败测试**

```python
def test_generate_dialog_batch_filtered_by_model(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示波器")
    md.upsert_product(conn, "SCP4A", "采集器")
    md.upsert_hardware_batch(conn, "SVG14", "01", "国产化FPGA")
    md.upsert_hardware_batch(conn, "SCP4A", "01", "国产Wi-Fi模块")
    dlg = GenerateDialog(SnService(conn))
    dlg._model_combo.setCurrentIndex(dlg._model_combo.findData("SVG14"))
    texts = [dlg._batch_combo.itemText(i) for i in range(dlg._batch_combo.count())]
    assert texts == ["01 国产化FPGA"]
    dlg._model_combo.setCurrentIndex(dlg._model_combo.findData("SCP4A"))
    texts = [dlg._batch_combo.itemText(i) for i in range(dlg._batch_combo.count())]
    assert texts == ["01 国产Wi-Fi模块"]


def test_generate_dialog_accept_params(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "SVG14", "05", "第五批")
    # ... 其余与现有测试相同，ensure 选中型号后再选批次
```

改写文件中所有 `upsert_hardware_batch(conn, "05", ...)` 为带型号参数。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_generate_dialog.py -v`

Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
def _load_master_data(self) -> None:
    conn = self._service.conn
    self._model_combo.blockSignals(True)
    self._model_combo.clear()
    for row in md.list_product_models(conn):
        self._model_combo.addItem(f"{row['code']} {row['name']}", row["code"])
    self._model_combo.blockSignals(False)
    for row in md.list_factories(conn):
        self._factory_combo.addItem(f"{row['code']} {row['name']}", row["code"])
    for row in md.list_markets(conn):
        self._market_combo.addItem(f"{row['code']} {row['name']}", row["code"])
    self._model_combo.currentIndexChanged.connect(self._reload_batches)
    self._reload_batches()


def _reload_batches(self) -> None:
    self._batch_combo.clear()
    model = self._model_combo.currentData()
    if not model:
        return
    for row in md.list_hardware_batches(self._service.conn, str(model)):
        self._batch_combo.addItem(f"{row['code']} {row['name']}", row["code"])
```

注意：构造时若 `currentIndexChanged` 在 `addItem` 过程触发，用 `blockSignals` 或先连信号再 `_reload_batches` 一次即可。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_generate_dialog.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/generate_dialog.py tests/test_generate_dialog.py
git commit -m "$(cat <<'EOF'
feat(gui): cascade hardware batch combo in generate dialog

EOF
)"
```

---

### Task 5: 主界面筛选型号→批次联动

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`
- Modify: `tests/test_filter_combos.py`

**Interfaces:**
- Consumes: `md.list_hardware_batches(conn, product_model=...)`
- Produces: 型号「不限」时批次仅空白项且不可选有效批次；选型号后批次含空白 + 该型号批次

- [ ] **Step 1: 写失败测试**

```python
def test_filter_batch_disabled_until_model_selected(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示波器")
    md.upsert_hardware_batch(conn, "SVG14", "01", "一批")
    win = MainWindow(SnService(conn))
    assert win._model_combo.currentData() in (None, "")
    assert win._batch_combo.count() == 1  # 仅空白
    assert win._batch_combo.itemData(0) in (None, "")


def test_filter_batch_lists_only_selected_model(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示波器")
    md.upsert_product(conn, "SCP4A", "采集器")
    md.upsert_hardware_batch(conn, "SVG14", "01", "国产化FPGA")
    md.upsert_hardware_batch(conn, "SCP4A", "01", "国产Wi-Fi模块")
    win = MainWindow(SnService(conn))
    win._model_combo.setCurrentIndex(win._model_combo.findData("SVG14"))
    assert win._batch_combo.findData("01") > 0
    assert "01 国产化FPGA" in [
        win._batch_combo.itemText(i) for i in range(win._batch_combo.count())
    ]
    assert "国产Wi-Fi" not in "".join(
        win._batch_combo.itemText(i) for i in range(win._batch_combo.count())
    )


def test_build_criteria_uses_combo_data(qapp, tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.upsert_product(conn, "SVG14", "示例外壳机")
    md.upsert_hardware_batch(conn, "SVG14", "05", "第五批")
    win = MainWindow(SnService(conn))
    win._model_combo.setCurrentIndex(win._model_combo.findData("SVG14"))
    win._batch_combo.setCurrentIndex(win._batch_combo.findData("05"))
    # ...
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_filter_combos.py -v`

Expected: FAIL

- [ ] **Step 3: 最小实现**

在 `_wire_signals` 中：

```python
self._model_combo.currentIndexChanged.connect(self._reload_filter_batch_combo)
```

```python
def _reload_filter_master_combos(self) -> None:
    # fill model/factory/market as today; then:
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
```

型号变更时若旧批次码在新型号下不存在，回落到空白项。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_filter_combos.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_filter_combos.py
git commit -m "$(cat <<'EOF'
feat(gui): cascade hardware batch filter by product model

EOF
)"
```

---

### Task 6: 文档同步与全量回归

**Files:**
- Modify: `docs/PRD.md`
- Modify: `docs/user-manual.md`
- Fix any remaining callers broken by API change（全库搜索 `upsert_hardware_batch(` / `hardware_batches=[(`）

**Interfaces:**
- Consumes: 规格全文
- Produces: PRD / 手册与行为一致；`uv run pytest` 全绿

- [ ] **Step 1: 更新 PRD**

`docs/PRD.md` 主数据表改为：

```markdown
| `product_models` | `code` CHAR(5) UNIQUE, `name` | 产品型号 |
| `hardware_batches` | `(product_model, code)` PK, `name` | 硬件批次从属于型号；同码可在不同型号下含义不同 |
```

主数据维护：三 Tab；型号内维护批次；删除规则（有批次不可删型号；批次按型号+批次查 SN 引用）。  
生成/查询：型号→批次联动说明。

- [ ] **Step 2: 更新使用手册**

`docs/user-manual.md`：

- §4：页签改为型号/单位/市场；说明在型号下维护批次；举例 SVG14/SCP4A 同码异义；删除限制补充「须先删下属批次」
- §5：先选型号再选批次；换型号清空批次
- §6（查询）：型号不限时不可按批次筛；选型号后批次可「不限」或选具体批次

- [ ] **Step 3: 全量测试并修残余**

Run: `uv run pytest -v`

Expected: PASS  

若其它测试仍用旧 `upsert_hardware_batch(conn, code, name)`，全部改为带 `product_model`。

- [ ] **Step 4: Commit**

```bash
git add docs/PRD.md docs/user-manual.md
# 以及本任务中为通过测试而修改的任何测试/源码文件
git add -u
git commit -m "$(cat <<'EOF'
docs: document model-scoped hardware batches

EOF
)"
```

---

## Self-Review (plan vs spec)

| Spec 要求 | 对应任务 |
| --------- | -------- |
| `(product_model, code)` 主键与同码异义 | Task 1 |
| 生成前校验归属 | Task 2 |
| MasterSnapshot 三元组与同步顺序 | Task 2 |
| 主数据嵌套 UI、三 Tab、删除规则 | Task 1+3 |
| 生成级联 | Task 4 |
| 筛选级联（型号不限→批次不可用） | Task 5 |
| PRD + user-manual | Task 6 |
| 无旧库迁移 | Global Constraints / Task 1 DDL |
| 非目标：跨型号按批次码筛 | Task 5 仅空白项，不列出全局批次 |

无 TBD/占位；API 命名在各 Task Interfaces 中前后一致。
