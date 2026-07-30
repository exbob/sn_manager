# SN Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付单机 PySide6 SN 管理工具：Version A 生成/查询/改状态/导出，SQLite 持久化，并可在 Windows / Linux 上用 PyInstaller 分别打包。

**Architecture:** `sn_core`（无 I/O 编解码）→ `sn_db`（SQLite）→ `sn_app`（事务与导出）→ `sn_gui`（主界面+对话框）。源码包布局在 `src/sn_manager/`。

**Tech Stack:** Python ≥3.12、uv、PySide6、sqlite3 标准库、openpyxl、pytest、PyInstaller。

**Spec:** `docs/superpowers/specs/2026-07-30-sn-manager-design.md`、`PRD.md`

## Global Constraints

- Python `>=3.12`；用 `uv` 管理依赖与虚拟环境
- 首期仅 Version A；两位年按 `2000+YY`
- 状态：`unused` | `used` | `void`；作废不回收 `seq`
- 序号维度：`(product_model, hw_batch, prod_year, prod_month, prod_day)`，`seq` 0–4095
- `prod_*` 存公历整数；字母入库前转大写
- 数据文件：与可执行文件同目录的 `sn_manager.db`
- GUI 中文；无登录；勿依赖跨 OS 交叉编译
- 提交信息用英文 conventional commits（`feat:` / `test:` / `chore:`）

---

## File Structure

```
src/sn_manager/
  __init__.py
  __main__.py                 # python -m sn_manager
  core/
    __init__.py
    errors.py                 # SnError, ValidationError, SequenceExhaustedError
    status.py                 # Status enum
    version_a.py              # encode / decode / validate fields
  db/
    __init__.py
    schema.py                 # DDL + seed SQL
    connection.py             # open/migrate/seed
    master_data.py            # product/batch/factory/market CRUD
    serials.py                # allocate, insert, filter, update status
  app/
    __init__.py
    paths.py                  # resolve db path next to exe/script
    services.py               # generate, filter, set_status, master apply
    export.py                 # excel + burn txt
  gui/
    __init__.py
    main_window.py
    generate_dialog.py
    master_data_dialog.py
    export_dialog.py
    widgets.py                # shared small helpers if needed
tests/
  test_version_a.py
  test_db_serials.py
  test_services.py
  test_export.py
scripts/
  build.sh                    # Linux PyInstaller
  build.ps1                   # Windows PyInstaller
pyproject.toml
main.py                       # thin wrapper → sn_manager.__main__
```

---

### Task 1: 项目脚手架与依赖

**Files:**
- Modify: `pyproject.toml`
- Create: `src/sn_manager/__init__.py`, `src/sn_manager/__main__.py`
- Modify: `main.py`
- Create: `tests/conftest.py`（可先空）

**Interfaces:**
- Produces: 可安装包 `sn_manager`；`uv run pytest` 可运行（0 tests OK）

- [ ] **Step 1: 更新 `pyproject.toml`**

```toml
[project]
name = "sn-manager"
version = "0.1.0"
description = "设备序列号管理（Version A）"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "PySide6>=6.6",
    "openpyxl>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pyinstaller>=6.0",
]

[project.scripts]
sn-manager = "sn_manager.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sn_manager"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

若当前 uv 项目用不同 build backend，保持与仓库一致，但必须能把 `src/sn_manager` 装进环境。

- [ ] **Step 2: 创建包入口**

`src/sn_manager/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/sn_manager/__main__.py`:

```python
def main() -> None:
    # GUI 在后续 Task 接入；先占位以便打包入口稳定
    raise SystemExit("GUI not wired yet; run after Task 8+")


if __name__ == "__main__":
    main()
```

`main.py`:

```python
from sn_manager.__main__ import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 安装依赖并确认 pytest**

Run:

```bash
cd /home/lsc/workspace/sn-manager
uv add PySide6 openpyxl
uv add --dev pytest pyinstaller
uv run pytest -q
```

Expected: `no tests ran` 或 `0 passed`（无失败）

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock main.py src/sn_manager tests/conftest.py
git commit -m "chore: scaffold sn_manager package and dependencies"
```

---

### Task 2: `sn_core` — Status 与 Version A 编解码

**Files:**
- Create: `src/sn_manager/core/errors.py`
- Create: `src/sn_manager/core/status.py`
- Create: `src/sn_manager/core/version_a.py`
- Create: `src/sn_manager/core/__init__.py`
- Test: `tests/test_version_a.py`

**Interfaces:**
- Produces:
  - `class Status(StrEnum): UNUSED="unused"; USED="used"; VOID="void"`
  - `class SnFields` dataclass: `version, product_model, hw_batch, factory, market, prod_year, prod_month, prod_day, seq`
  - `encode_version_a(fields: SnFields) -> str`
  - `decode_version_a(sn: str) -> SnFields`
  - `validate_generation_input(...)` 校验并返回规范化 `SnFields` 所需分量（日期用 `datetime.date`）
  - 月码：`1-9,A,B,C`；日码：`1-9,A-V`（1–31）；年：`prod_year % 100` 两位，解码 `2000+yy`
  - 异常：`ValidationError`、消息中文可在 app 层包装，core 可用英文 key 或中文短句（统一中文）

- [ ] **Step 1: 写失败测试（示例 SN 往返）**

`tests/test_version_a.py`:

```python
from datetime import date

import pytest

from sn_manager.core.version_a import (
    SnFields,
    decode_version_a,
    encode_version_a,
    month_to_code,
    day_to_code,
)


def test_encode_prd_example():
    fields = SnFields(
        version="A",
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_year=2026,
        prod_month=12,
        prod_day=1,
        seq=0xF04,
    )
    assert encode_version_a(fields) == "ASVG140521261CF04"


def test_decode_prd_example():
    f = decode_version_a("ASVG140521261CF04")
    assert f.product_model == "SVG14"
    assert f.prod_year == 2026
    assert f.prod_month == 12
    assert f.prod_day == 1
    assert f.seq == 0xF04


def test_roundtrip_month_day_boundaries():
    for month in range(1, 13):
        for day in (1, 9, 10, 30, 31):
            if month == 2 and day > 29:
                continue
            if month in (4, 6, 9, 11) and day > 30:
                continue
            try:
                date(2026, month, day)
            except ValueError:
                continue
            fields = SnFields(
                version="A",
                product_model="ABC12",
                hw_batch="01",
                factory="1",
                market="0",
                prod_year=2026,
                prod_month=month,
                prod_day=day,
                seq=0,
            )
            assert decode_version_a(encode_version_a(fields)) == fields


def test_reject_bad_length():
    with pytest.raises(Exception):
        decode_version_a("SHORT")


def test_seq_fff():
    fields = SnFields(
        version="A",
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_year=2026,
        prod_month=1,
        prod_day=1,
        seq=0xFFF,
    )
    assert encode_version_a(fields).endswith("FFF")
```

- [ ] **Step 2: Run 确认失败**

```bash
uv run pytest tests/test_version_a.py -v
```

Expected: FAIL（import 或属性不存在）

- [ ] **Step 3: 实现 `errors.py` / `status.py` / `version_a.py`**

实现要点：

- `MONTH_CODES = "123456789ABC"`（index month-1）
- `DAY_CODES = "123456789ABCDEFGHIJKLMNOPQRSTUV"`（31 chars）
- `seq` → 三位大写十六进制 `f"{seq:03X}"`
- `encode` 前断言 `0 <= seq <= 0xFFF`，型号长度 5、批次 2 等
- `decode` 校验总长 17、version=`A`、字符集

`core/__init__.py` 导出常用符号。

- [ ] **Step 4: Run 确认通过**

```bash
uv run pytest tests/test_version_a.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/core tests/test_version_a.py
git commit -m "feat: add Version A encode/decode core"
```

---

### Task 3: SQLite 建库、种子与主数据 CRUD

**Files:**
- Create: `src/sn_manager/db/schema.py`
- Create: `src/sn_manager/db/connection.py`
- Create: `src/sn_manager/db/master_data.py`
- Create: `src/sn_manager/db/__init__.py`
- Test: `tests/test_db_master.py`

**Interfaces:**
- Produces:
  - `connect(db_path: Path) -> sqlite3.Connection`（`row_factory=sqlite3.Row`，执行 schema+seed）
  - `list_codes(conn, table) -> list[...]`
  - `upsert_product(conn, code: str)` 等；`delete_*` 若被 `serial_numbers` 引用则抛 `ValidationError`（中文消息）
  - 种子：factories `1/自己生产`,`2/赛威思`；markets `0/不限`,`1/中国`,`2/韩国`,`3/美国`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

import pytest

from sn_manager.db.connection import connect
from sn_manager.db import master_data as md


def test_seed_factories_and_markets(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    factories = md.list_factories(conn)
    assert {f["code"] for f in factories} >= {"1", "2"}
    markets = md.list_markets(conn)
    assert {m["code"] for m in markets} >= {"0", "1", "2", "3"}


def test_add_and_list_product(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    md.add_product_model(conn, "svg14")  # 应转大写
    assert md.list_product_models(conn)[0]["code"] == "SVG14"
```

- [ ] **Step 2: Run 确认失败**

```bash
uv run pytest tests/test_db_master.py -v
```

- [ ] **Step 3: 实现 schema + connection + master_data**

`serial_numbers` 表字段与 spec §4.2 一致；索引按 spec。  
`connect`：若文件不存在则创建；`executescript` DDL；seed 用 `INSERT OR IGNORE`。

- [ ] **Step 4: Run 确认通过**

```bash
uv run pytest tests/test_db_master.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/db tests/test_db_master.py
git commit -m "feat: add sqlite schema, seed, and master data CRUD"
```

---

### Task 4: 序号分配与 SN 查询/改状态

**Files:**
- Create: `src/sn_manager/db/serials.py`
- Test: `tests/test_db_serials.py`

**Interfaces:**
- Consumes: `encode_version_a`, `SnFields`, `Status`, `connect`
- Produces:
  - `allocate_and_insert(conn, *, product_model, hw_batch, factory, market, prod_date: date, count: int) -> list[str]`
  - 同一写事务：`MAX(seq)+1`；若 `start+count-1 > 4095` 抛 `SequenceExhaustedError`（消息含「请更换生产日期或硬件批次」）
  - `filter_serials(conn, **filters) -> list[dict]`
  - `update_statuses(conn, sns: list[str], status: Status) -> int`
  - 新行 `status=unused`；`created_at`/`updated_at` 为 UTC ISO-8601

- [ ] **Step 1: 写失败测试**

```python
from datetime import date
from pathlib import Path

import pytest

from sn_manager.core.errors import SequenceExhaustedError
from sn_manager.core.status import Status
from sn_manager.db.connection import connect
from sn_manager.db import serials as ser


def test_allocate_sequential(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    sns = ser.allocate_and_insert(
        conn,
        product_model="SVG14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 12, 1),
        count=2,
    )
    assert len(sns) == 2
    assert sns[0].endswith("000")
    assert sns[1].endswith("001")


def test_void_does_not_recycle(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    d = date(2026, 1, 1)
    kwargs = dict(
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_date=d,
    )
    s1 = ser.allocate_and_insert(conn, count=1, **kwargs)[0]
    ser.update_statuses(conn, [s1], Status.VOID)
    s2 = ser.allocate_and_insert(conn, count=1, **kwargs)[0]
    assert s2.endswith("001")


def test_exhaust_raises(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    d = date(2026, 1, 2)
    kwargs = dict(
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_date=d,
    )
    # 直接插入 seq=4095 的边界：先插入 4095 个太慢；改为手工插入 max 行后请求 1
    import sqlite3
    from sn_manager.core.version_a import SnFields, encode_version_a

    fields = SnFields(
        version="A",
        product_model="ABC12",
        hw_batch="01",
        factory="1",
        market="0",
        prod_year=2026,
        prod_month=1,
        prod_day=2,
        seq=4095,
    )
    sn = encode_version_a(fields)
    conn.execute(
        "INSERT INTO serial_numbers(sn, version, product_model, hw_batch, factory, market, "
        "prod_year, prod_month, prod_day, seq, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sn, "A", "ABC12", "01", "1", "0", 2026, 1, 2, 4095, "unused", "t", "t"),
    )
    conn.commit()
    with pytest.raises(SequenceExhaustedError):
        ser.allocate_and_insert(conn, count=1, **kwargs)
```

- [ ] **Step 2–4: 红→实现→绿**（同前模式）

实现时用 `BEGIN IMMEDIATE` 或单连接事务包住 MAX+INSERT。

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/db/serials.py tests/test_db_serials.py
git commit -m "feat: allocate serial numbers and update status in sqlite"
```

---

### Task 5: `sn_app` 服务层（生成/筛选/主数据应用）

**Files:**
- Create: `src/sn_manager/app/paths.py`
- Create: `src/sn_manager/app/services.py`
- Create: `src/sn_manager/app/__init__.py`
- Test: `tests/test_services.py`

**Interfaces:**
- Produces:
  - `default_db_path() -> Path` — frozen 时用 `sys.executable` 目录，否则用项目/`cwd` 旁约定：`Path(sys.executable).resolve().parent / "sn_manager.db"` when `getattr(sys, "frozen", False)` else `Path.cwd() / "sn_manager.db"`（开发可接受）
  - `class SnService:` 持有 `conn`
  - `generate(self, *, product_model, hw_batch, factory, market, prod_date, count, ensure_master=True) -> list[dict]`
  - `filter(self, **criteria) -> list[dict]`
  - `set_status(self, sns: list[str], status: Status) -> None`
  - `replace_master_data(self, snapshot: MasterSnapshot) -> None` — 供主数据对话框「确认」一次性写入（实现可用：校验后增删改；简单做法：对四类表按对话框提交的完整列表同步）
  - 生成时 `ensure_master=True`：缺失的型号/批次/单位/市场 `INSERT OR IGNORE`

- [ ] **Step 1: 测试 generate N=1 与 filter**

```python
from datetime import date
from pathlib import Path

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect


def test_generate_and_filter(tmp_path: Path):
    conn = connect(tmp_path / "t.db")
    svc = SnService(conn)
    rows = svc.generate(
        product_model="svg14",
        hw_batch="05",
        factory="2",
        market="1",
        prod_date=date(2026, 12, 1),
        count=1,
    )
    assert len(rows) == 1
    assert rows[0]["sn"] == "ASVG140521261CF04"
    found = svc.filter(product_model="SVG14")
    assert len(found) == 1
```

- [ ] **Step 2–4: 红→实现→绿**

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/app tests/test_services.py
git commit -m "feat: add SnService for generate and filter"
```

---

### Task 6: 导出 Excel 与烧写 txt

**Files:**
- Create: `src/sn_manager/app/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Produces:
  - `export_excel(rows: list[dict], path: Path) -> None`
  - `export_burn_txt(sns: list[str], directory: Path) -> list[Path]` — 写 `sn_{sn}.txt`，内容一行 SN，已存在则覆盖
  - `export_burn_and_mark_used(svc, sns, directory, mark_used: bool) -> None` — 先全部写文件成功，若 `mark_used` 再 `set_status(..., USED)`；写失败不改状态

- [ ] **Step 1: 测试**

```python
from pathlib import Path

from openpyxl import load_workbook

from sn_manager.app.export import export_burn_txt, export_excel


def test_excel_and_burn(tmp_path: Path):
    rows = [
        {
            "sn": "ASVG140521261CF04",
            "product_model": "SVG14",
            "hw_batch": "05",
            "factory": "2",
            "market": "1",
            "prod_year": 2026,
            "prod_month": 12,
            "prod_day": 1,
            "seq": 0xF04,
            "status": "unused",
            "created_at": "t",
            "updated_at": "t",
        }
    ]
    xlsx = tmp_path / "out.xlsx"
    export_excel(rows, xlsx)
    wb = load_workbook(xlsx)
    assert wb.active["A2"].value == "ASVG140521261CF04"

    paths = export_burn_txt(["ASVG140521261CF04"], tmp_path)
    p = tmp_path / "sn_ASVG140521261CF04.txt"
    assert p in paths
    assert p.read_text(encoding="utf-8") == "ASVG140521261CF04"
```

- [ ] **Step 2–4: 红→实现→绿**

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/app/export.py tests/test_export.py
git commit -m "feat: export excel and burn txt files"
```

---

### Task 7: GUI — 主窗口骨架（查询/全选/改状态/导出按钮位）

**Files:**
- Create: `src/sn_manager/gui/main_window.py`
- Create: `src/sn_manager/gui/__init__.py`
- Modify: `src/sn_manager/__main__.py`

**Interfaces:**
- Consumes: `SnService`, `default_db_path`, `Status`
- Produces: `MainWindow(service: SnService)` 可 `show()`
- 布局严格按 spec §6：左筛选+查询/生成/主数据；右表+全选；右下改状态、导出
- 无选中时禁用「改状态」「导出」
- 「查询」调用 `service.filter` 刷新表
- 「全选」选中当前表全部行
- 本 Task 生成/主数据/导出对话框可先 `QMessageBox.information` 占位，下一 Task 替换

手工验证（无自动化强制）：

```bash
uv run python -m sn_manager
```

Expected: 窗口打开，中文标签可见，点查询不崩溃（空结果 OK）

- [ ] **Step 1: 实现 MainWindow + 启动**

`__main__.py`:

```python
import sys
from PySide6.QtWidgets import QApplication, QMessageBox

from sn_manager.app.paths import default_db_path
from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    db_path = default_db_path()
    try:
        conn = connect(db_path)
    except OSError as e:
        QMessageBox.critical(None, "错误", f"无法打开数据库：{db_path}\n{e}")
        raise SystemExit(1) from e
    service = SnService(conn)
    win = MainWindow(service)
    win.setWindowTitle("设备序列号管理")
    win.resize(1100, 700)
    win.show()
    raise SystemExit(app.exec())
```

筛选字段至少：完整 SN、型号、批次、单位、市场、状态下拉、日期从/到。

结果表列：SN、型号、批次、单位、市场、年、月、日、序号、状态、创建时间。

- [ ] **Step 2: 手工启动确认**

```bash
uv run python -m sn_manager
```

- [ ] **Step 3: Commit**

```bash
git add src/sn_manager/gui src/sn_manager/__main__.py
git commit -m "feat: add main window query UI shell"
```

---

### Task 8: GUI — 生成对话框

**Files:**
- Create: `src/sn_manager/gui/generate_dialog.py`
- Modify: `src/sn_manager/gui/main_window.py`

**Interfaces:**
- Produces: `GenerateDialog` → `Accepted` 时返回生成参数；主窗口调用 `service.generate`，**用本批结果替换**表格并全选这些行
- 字段：型号/批次（可编辑下拉，来自主数据）、单位、市场、日期（默认今天）、数量 N≥1
- 失败时 `QMessageBox.warning` 显示 `SequenceExhaustedError` 等中文消息

- [ ] **Step 1: 实现对话框并接线到「生成」**

- [ ] **Step 2: 手工验证** 生成 1 条，右侧仅该条且选中；生成触顶场景可用测试库预置

- [ ] **Step 3: Commit**

```bash
git add src/sn_manager/gui/generate_dialog.py src/sn_manager/gui/main_window.py
git commit -m "feat: add generate dialog wired to SnService"
```

---

### Task 9: GUI — 主数据对话框（确认才落库）

**Files:**
- Create: `src/sn_manager/gui/master_data_dialog.py`
- Modify: `src/sn_manager/gui/main_window.py`、必要时 `services.py`

**Interfaces:**
- 对话框加载当前四类主数据到可编辑列表/表格
- **取消**：不调用写库
- **确认**：调用 `service.apply_master_data(...)`；引用中的删除被拒绝时提示并保持对话框打开或回滚本次确认

- [ ] **Step 1: 实现 + 接线**

- [ ] **Step 2: 手工验证** 取消后重启数据不变；确认后可见新型号

- [ ] **Step 3: Commit**

```bash
git add src/sn_manager/gui/master_data_dialog.py src/sn_manager/gui/main_window.py src/sn_manager/app/services.py
git commit -m "feat: add master data dialog with commit-on-accept"
```

---

### Task 10: GUI — 改状态与导出对话框

**Files:**
- Create: `src/sn_manager/gui/export_dialog.py`
- Modify: `src/sn_manager/gui/main_window.py`

**Interfaces:**
- 「改状态」：选中行 → 选择 `unused/used/void` → `set_status` → 刷新选中行显示
- 「导出」：对话框选 Excel 或烧写目录；烧写可勾选「导出后标为已使用」；仅选中行

- [ ] **Step 1: 实现 + 接线**

- [ ] **Step 2: 手工验证** 无选中按钮禁用；导出 xlsx 与 `sn_*.txt`；勾选标 used 后状态变化；故意失败路径不改状态（可选）

- [ ] **Step 3: Commit**

```bash
git add src/sn_manager/gui/export_dialog.py src/sn_manager/gui/main_window.py
git commit -m "feat: wire status change and export dialogs"
```

---

### Task 11: PyInstaller 双平台脚本与 README

**Files:**
- Create: `scripts/build.sh`
- Create: `scripts/build.ps1`
- Create: `sn_manager.spec`（可选，或脚本内联参数）
- Modify: `README.md`（中文使用/备份/勿双开写）
- Modify: `.gitignore`（加入 `build/`、`dist/`、`*.spec` 若生成在根目录、`sn_manager.db`）

**Interfaces:**
- Linux: `./scripts/build.sh` → `dist/sn-manager`（名可调整，文档写清）
- Windows: `.\scripts\build.ps1` → `dist\sn-manager.exe`
- 使用 `--onefile` 或 `--onedir`：优先 `--onedir` 便于同目录放 `sn_manager.db`；若 onefile，说明首次运行在 exe 旁建库

推荐 `--onedir`，数据文件与可执行文件同目录更直观。

`scripts/build.sh` 示例：

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pyinstaller \
  --noconfirm \
  --windowed \
  --name sn-manager \
  --paths src \
  src/sn_manager/__main__.py
```

- [ ] **Step 1: 写脚本与 README 段落**（运行环境、备份 db、两端分别构建）

- [ ] **Step 2: 在当前 Linux 上执行 build.sh 并启动产物做冒烟**

```bash
chmod +x scripts/build.sh
./scripts/build.sh
# 按 dist 实际路径启动
```

- [ ] **Step 3: Commit**

```bash
git add scripts README.md .gitignore sn_manager.spec
git commit -m "chore: add PyInstaller build scripts and usage notes"
```

---

### Task 12: 全量回归与规格核对

**Files:** 无新功能；修 bug only

- [ ] **Step 1: 跑全量测试**

```bash
uv run pytest -v
```

Expected: 全部 PASS

- [ ] **Step 2: 对照 spec 勾选**

| Spec 项 | 验证方式 |
|--------|----------|
| Version A 示例 SN | test + 手工生成 |
| N 数量统一入口 | 手工 |
| 触顶提示 | test_db_serials |
| 作废不回收 | test |
| 主数据确认/取消 | 手工 |
| 选中导出 / 全选 / 改状态位置 | 手工 |
| 烧写覆盖与 mark used | test_export + 手工 |
| 双平台构建说明 | README |

- [ ] **Step 3: 若有修复则提交**

```bash
git commit -m "fix: ..."
```

---

## Plan Self-Review

**Spec coverage:**
- core/db/app/gui/打包均有 Task
- UI 布局 §6 → Task 7–10
- 导出双模式 → Task 6+10
- 双平台 → Task 11（Windows 脚本在 Linux CI 上无法实跑，文档+脚本交付）

**Placeholders:** 无 TBD；GUI 手工步骤已写明命令

**Type consistency:** `Status`、`SnFields`、`SnService.generate/filter/set_status`、`allocate_and_insert` 命名在任务间一致

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-30-sn-manager.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 Task 派一个新子代理，Task 间复查，迭代快  

**2. Inline Execution** — 本会话用 executing-plans 按检查点批量执行  

Which approach?
