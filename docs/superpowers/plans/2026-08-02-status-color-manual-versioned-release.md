# 状态着色、使用手册与版本化 Windows 发布 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 查询结果状态列着色；发行包附带 `user-manual.md` 并在左侧提供「帮助」打开；Windows CI 产物目录与 zip 带 `git describe` 版本号。

**Architecture:** 状态色在 `_populate_table` 用 `ForegroundRole` 设置。手册路径由 `resolve_user_manual_path()` 解析（frozen：exe 同目录；开发：`docs/user-manual.md`）。构建脚本复制手册到 onedir 根；Windows CI 再按 `app_version.txt` 重命名目录并打带顶层文件夹的 zip。

**Tech Stack:** Python 3.12、PySide6、PyInstaller、Bash、GitHub Actions（Windows pwsh）。

## Global Constraints

- 状态文案不变：「未使用 / 已使用 / 作废」；作废红色，不改名为「废弃」
- 颜色：已使用 `#2E7D32`；作废 `#C62828`；未使用不设前景色
- 手册文件名在发行包根目录为 `user-manual.md`（由 `docs/user-manual.md` 复制）
- Windows 产物：`sn-manager-windows-<version>.zip`，zip 内一层同名目录；version 来自 `app_version.txt`（空则 `unknown`）
- Linux `build.sh` 只复制手册，不版本化目录/zip 名
- 规格：`docs/superpowers/specs/2026-08-02-status-color-manual-versioned-release-design.md`

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/gui/main_window.py` | 状态列前景色；「帮助」按钮与打开逻辑 |
| `tests/test_status_colors.py` | 状态列颜色单测 |
| `src/sn_manager/app/paths.py` | `resolve_user_manual_path() -> Path \| None` |
| `tests/test_paths.py` | 手册路径解析单测 |
| `src/sn_manager/app/__init__.py` | 可选导出 `resolve_user_manual_path` |
| `tests/test_help_button.py` | 帮助按钮存在与点击打开 |
| `scripts/build.sh` | 复制手册到 `dist/sn-manager/` |
| `.github/workflows/release-windows-gui.yml` | 复制手册 + 版本化目录/zip/artifact |
| `README.md` / `docs/user-manual.md` | 发行包文件名与帮助入口说明 |
| `docs/superpowers/specs/2026-07-31-windows-ci-release-design.md` | 同步产物命名约定 |

---

### Task 1: 查询结果状态列着色

**Files:**
- Create: `tests/test_status_colors.py`
- Modify: `src/sn_manager/gui/main_window.py`（`_populate_table` 及可选颜色常量）

**Interfaces:**
- Consumes: 现有 `_TABLE_COLUMNS`、`_STATUS_LABELS`、`Status`、`_populate_table`
- Produces: 状态列 item 按状态设置/不设置 `ForegroundRole`

- [ ] **Step 1: 写失败单测**

创建 `tests/test_status_colors.py`：

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from sn_manager.app.services import SnService
from sn_manager.core.status import Status
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow, _TABLE_COLUMNS


def _status_col() -> int:
    return next(i for i, (key, _) in enumerate(_TABLE_COLUMNS) if key == "status")


def _row(sn: str, status: str) -> dict:
    data = {key: "" for key, _ in _TABLE_COLUMNS}
    data["sn"] = sn
    data["status"] = status
    return data


def test_status_column_colors(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win._populate_table(
        [
            _row("A1", Status.UNUSED.value),
            _row("A2", Status.USED.value),
            _row("A3", Status.VOID.value),
        ]
    )
    col = _status_col()
    unused = win._table.item(0, col)
    used = win._table.item(1, col)
    void = win._table.item(2, col)
    assert unused is not None and used is not None and void is not None
    assert unused.data(Qt.ItemDataRole.ForegroundRole) is None
    assert used.foreground().color() == QColor("#2E7D32")
    assert void.foreground().color() == QColor("#C62828")
```

- [ ] **Step 2: 跑测确认失败**

Run: `uv run pytest tests/test_status_colors.py -v`

Expected: FAIL（未使用可能仍无 ForegroundRole，但 used/void 颜色断言失败）

- [ ] **Step 3: 最小实现**

在 `main_window.py` 顶部附近（`_STATUS_LABELS` 旁）增加：

```python
from PySide6.QtGui import QColor  # 若尚未导入

_STATUS_FOREGROUND: dict[str, QColor] = {
    Status.USED.value: QColor("#2E7D32"),
    Status.VOID.value: QColor("#C62828"),
}
```

在 `_populate_table` 创建 item 后：

```python
item = QTableWidgetItem(display)
item.setData(Qt.ItemDataRole.UserRole, row.get("sn"))
if key == "status":
    color = _STATUS_FOREGROUND.get(str(value))
    if color is not None:
        item.setForeground(color)
self._table.setItem(row_idx, col_idx, item)
```

- [ ] **Step 4: 跑测确认通过**

Run: `uv run pytest tests/test_status_colors.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_status_colors.py src/sn_manager/gui/main_window.py
git commit -m "$(cat <<'EOF'
feat(gui): color status column by unused/used/void

EOF
)"
```

---

### Task 2: `resolve_user_manual_path` + 「帮助」按钮

**Files:**
- Modify: `src/sn_manager/app/paths.py`
- Modify: `tests/test_paths.py`
- Modify: `src/sn_manager/app/__init__.py`（导出 `resolve_user_manual_path`）
- Modify: `src/sn_manager/gui/main_window.py`
- Create: `tests/test_help_button.py`

**Interfaces:**
- Consumes: `app_dir()`（frozen 同目录）；`sys.frozen`
- Produces: `resolve_user_manual_path() -> Path | None`（存在则返回绝对路径，否则 `None`）

- [ ] **Step 1: 写路径解析失败单测**

在 `tests/test_paths.py` 追加：

```python
from sn_manager.app.paths import resolve_user_manual_path


def test_resolve_user_manual_frozen_beside_exe(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "dist" / "sn-manager.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    manual = exe.parent / "user-manual.md"
    manual.write_text("# help\n", encoding="utf-8")
    monkeypatch.setattr(paths_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_mod.sys, "executable", str(exe))
    assert resolve_user_manual_path() == manual.resolve()


def test_resolve_user_manual_frozen_missing(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "dist" / "sn-manager.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths_mod.sys, "executable", str(exe))
    assert resolve_user_manual_path() is None


def test_resolve_user_manual_dev_docs(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    manual = docs / "user-manual.md"
    manual.write_text("# help\n", encoding="utf-8")
    # 将模块「安装」路径伪装在 tmp 包树下，使向上查找落到 tmp_path
    pkg = tmp_path / "src" / "sn_manager" / "app"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(paths_mod.sys, "frozen", False, raising=False)
    monkeypatch.setattr(paths_mod, "__file__", str(pkg / "paths.py"))
    monkeypatch.chdir(tmp_path)
    assert resolve_user_manual_path() == manual.resolve()
```

- [ ] **Step 2: 跑测确认失败**

Run: `uv run pytest tests/test_paths.py -v`

Expected: FAIL（`resolve_user_manual_path` 未定义）

- [ ] **Step 3: 实现 `resolve_user_manual_path`**

在 `src/sn_manager/app/paths.py`：

```python
_USER_MANUAL_PACKAGED = "user-manual.md"
_USER_MANUAL_DEV = Path("docs") / "user-manual.md"
_MAX_WALK_UP = 8


def resolve_user_manual_path() -> Path | None:
    """返回本地使用手册路径；找不到则 None。"""
    if getattr(sys, "frozen", False):
        candidate = app_dir() / _USER_MANUAL_PACKAGED
        return candidate.resolve() if candidate.is_file() else None

    candidates: list[Path] = [Path.cwd() / _USER_MANUAL_DEV]
    here = Path(__file__).resolve().parent
    for i, parent in enumerate([here, *here.parents]):
        if i > _MAX_WALK_UP:
            break
        path = parent / _USER_MANUAL_DEV
        if path not in candidates:
            candidates.append(path)
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None
```

在 `src/sn_manager/app/__init__.py` 导出：

```python
from sn_manager.app.paths import default_db_path, resolve_user_manual_path
# ...
__all__ = [..., "resolve_user_manual_path"]
```

- [ ] **Step 4: 跑路径单测通过**

Run: `uv run pytest tests/test_paths.py -v`

Expected: PASS

- [ ] **Step 5: 写帮助按钮失败单测**

创建 `tests/test_help_button.py`：

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtWidgets import QMessageBox

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_help_button_exists_above_version(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    assert win._help_btn.text() == "帮助"
    left = win._filter_panel.layout()
    help_idx = left.indexOf(win._help_btn)
    ver_idx = left.indexOf(win._version_label)
    assert help_idx >= 0 and ver_idx >= 0
    assert help_idx < ver_idx


def test_help_opens_manual(qapp, tmp_path: Path, monkeypatch) -> None:
    manual = tmp_path / "user-manual.md"
    manual.write_text("# x\n", encoding="utf-8")
    monkeypatch.setattr(
        "sn_manager.gui.main_window.resolve_user_manual_path",
        lambda: manual,
    )
    opened: list = []
    monkeypatch.setattr(
        "sn_manager.gui.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win._help_btn.click()
    assert len(opened) == 1
    assert Path(opened[0].toLocalFile()) == manual


def test_help_missing_shows_warning(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sn_manager.gui.main_window.resolve_user_manual_path",
        lambda: None,
    )
    warned = MagicMock()
    monkeypatch.setattr(QMessageBox, "warning", warned)
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    win._help_btn.click()
    warned.assert_called_once()
```

说明：`MainWindow` 需保留左侧面板引用为 `self._filter_panel`（若当前局部变量无名，在 `_build_ui` / `_build_filter_panel` 中赋给 `self._filter_panel` 以便测序；若不想暴露 layout，可将「顺序」断言改为仅检查按钮存在 + 打开行为，并删掉 `indexOf` 断言）。

**推荐简化（若 `_filter_panel` 尚不存在）：** 测试只断言按钮文案与打开/警告行为，不测 layout 下标；布局在实现注释/代码审查中保证「帮助在版本号上方」。

简化版 `test_help_button_exists`：

```python
def test_help_button_exists(qapp, tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    assert win._help_btn.text() == "帮助"
```

- [ ] **Step 6: 跑帮助单测确认失败**

Run: `uv run pytest tests/test_help_button.py -v`

Expected: FAIL（无 `_help_btn`）

- [ ] **Step 7: 实现帮助按钮**

`main_window.py` 增加导入：

```python
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from sn_manager.app.paths import resolve_user_manual_path
```

（`QColor` 若 Task 1 已加则勿重复。）

在 `_build_filter_panel` 中，`layout.addStretch()` 之后、`_version_label` 之前：

```python
self._help_btn = QPushButton("帮助")
layout.addWidget(self._help_btn)
```

在信号连接处（与其它按钮一起）：

```python
self._help_btn.clicked.connect(self._on_help)
```

新增方法：

```python
def _on_help(self) -> None:
    path = resolve_user_manual_path()
    if path is None:
        QMessageBox.warning(self, "帮助", "未找到使用手册文件（user-manual.md）。")
        return
    ok = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    if not ok:
        QMessageBox.warning(self, "帮助", f"无法打开使用手册：\n{path}")
```

确保 `QMessageBox` 已导入（文件中若已有则复用）。

- [ ] **Step 8: 跑测通过**

Run: `uv run pytest tests/test_paths.py tests/test_help_button.py tests/test_main_window_version.py -v`

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/sn_manager/app/paths.py src/sn_manager/app/__init__.py \
  src/sn_manager/gui/main_window.py tests/test_paths.py tests/test_help_button.py
git commit -m "$(cat <<'EOF'
feat: add Help button to open packaged user manual

EOF
)"
```

---

### Task 3: 构建复制手册 + Windows 版本化 zip + 文档

**Files:**
- Modify: `scripts/build.sh`
- Modify: `.github/workflows/release-windows-gui.yml`
- Modify: `README.md`
- Modify: `docs/user-manual.md`
- Modify: `docs/superpowers/specs/2026-07-31-windows-ci-release-design.md`（产物命名段落）

**Interfaces:**
- Consumes: `app_version.txt`、`docs/user-manual.md`、`dist/sn-manager/`
- Produces: onedir 根含 `user-manual.md`；Windows `sn-manager-windows-<ver>.zip`（含顶层同名目录）

- [ ] **Step 1: 更新 `scripts/build.sh`**

在 PyInstaller 成功后追加复制：

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

./scripts/git-version.sh > app_version.txt

uv run pyinstaller \
  --noconfirm \
  --windowed \
  --name sn-manager \
  --paths src \
  --collect-submodules PySide6 \
  --add-data "app_version.txt:." \
  src/sn_manager/__main__.py

cp -f docs/user-manual.md dist/sn-manager/user-manual.md

echo "Built: dist/sn-manager/sn-manager"
```

- [ ] **Step 2: 更新 Windows workflow**

将 `.github/workflows/release-windows-gui.yml` 的 Zip / Upload 段改为（在 Build 之后）：

```yaml
      - name: Copy user manual into onedir
        shell: pwsh
        run: |
          Copy-Item -LiteralPath "docs/user-manual.md" `
            -Destination "dist/sn-manager/user-manual.md" -Force

      - name: Zip onedir with versioned folder name
        shell: pwsh
        run: |
          $ver = (Get-Content -LiteralPath "app_version.txt" -Raw).Trim()
          if ([string]::IsNullOrWhiteSpace($ver)) { $ver = "unknown" }
          $base = "sn-manager-windows-$ver"
          $src = Join-Path $env:GITHUB_WORKSPACE "dist/sn-manager"
          $staged = Join-Path $env:GITHUB_WORKSPACE $base
          $exe = Join-Path $src "sn-manager.exe"
          $zip = Join-Path $env:GITHUB_WORKSPACE "$base.zip"
          if (-not (Test-Path -LiteralPath $exe)) { throw "Missing $exe" }
          if (-not (Test-Path -LiteralPath (Join-Path $src "user-manual.md"))) {
            throw "Missing user-manual.md in onedir"
          }
          if (Test-Path -LiteralPath $staged) { Remove-Item -LiteralPath $staged -Recurse -Force }
          if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
          Move-Item -LiteralPath $src -Destination $staged
          Compress-Archive -Path $staged -DestinationPath $zip
          if (-not (Test-Path -LiteralPath $zip)) { throw "Missing $zip" }
          Get-Item -LiteralPath $zip | Format-List Name, Length
          "ZIP_NAME=$base.zip" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
          "ARTIFACT_NAME=$base" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8

      - name: Upload workflow artifact (manual runs / backup)
        uses: actions/upload-artifact@v4
        with:
          name: ${{ env.ARTIFACT_NAME }}
          path: ${{ env.ZIP_NAME }}
          if-no-files-found: error

      - name: Upload to GitHub Release
        if: github.ref_type == 'tag'
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ github.ref_name }}
          files: ${{ env.ZIP_NAME }}
          fail_on_unmatched_files: true
          generate_release_notes: true
```

删除旧的固定名 `sn-manager-windows.zip` / artifact `sn-manager-windows` 步骤，避免重复。

注意：`Compress-Archive -Path $staged` 会把**整个文件夹**作为 zip 内顶层目录（符合规格 A）。

- [ ] **Step 3: 更新用户文档**

`README.md` §2.1：将固定 `sn-manager-windows.zip` 改为说明下载 **`sn-manager-windows-<version>.zip`**（version 形如 `v2.0.0-0-g29a42ac`），解压得到同名文件夹；文件夹内含 `sn-manager.exe` 与 `user-manual.md`。补充：主界面左下「帮助」可打开手册。

`docs/user-manual.md`：
- §2.1：同上 zip 命名
- §2.2：解压后目录内可见 `user-manual.md`
- §2.3 表格：增加 `user-manual.md` 一行
- §3 左侧：按钮增加 **帮助**；说明点击用系统默认程序打开同目录（或开发态仓库）手册

`docs/superpowers/specs/2026-07-31-windows-ci-release-design.md`：将 `sn-manager-windows.zip` / artifact 名改为带版本的形式，并注明打入 `user-manual.md`。

- [ ] **Step 4: 本地快速校验（Linux）**

若本机可跑 PyInstaller（可选）：

```bash
./scripts/build.sh
test -f dist/sn-manager/user-manual.md
```

至少确认脚本语法：

```bash
bash -n scripts/build.sh
```

Expected: 无输出、退出码 0

- [ ] **Step 5: 回归相关单测**

Run: `uv run pytest tests/test_status_colors.py tests/test_paths.py tests/test_help_button.py tests/test_main_window_version.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/build.sh .github/workflows/release-windows-gui.yml \
  README.md docs/user-manual.md \
  docs/superpowers/specs/2026-07-31-windows-ci-release-design.md
git commit -m "$(cat <<'EOF'
build: ship user-manual and versioned Windows release zip

EOF
)"
```

---

## Spec coverage (self-review)

| 规格要求 | 任务 |
|----------|------|
| 状态列三色（未使用默认 / 已用绿 / 作废红） | Task 1 |
| 文案仍为「作废」 | Task 1（不改 labels） |
| onedir 根 `user-manual.md`（Win+Linux） | Task 3 |
| 「帮助」在版本号上方，系统默认打开 | Task 2 |
| 找不到手册时提示 | Task 2 |
| Windows `sn-manager-windows-<ver>` 目录+zip+artifact | Task 3 |
| Linux 不版本化命名 | Task 3（build.sh 仅 cp） |
| 更新 README / user-manual | Task 3 |

无 TBD/占位；`resolve_user_manual_path` 签名在 Task 2 前后一致。
