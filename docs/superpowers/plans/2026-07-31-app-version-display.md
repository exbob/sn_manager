# 主界面应用版本号展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `git-version.sh` 格式解析应用版本，构建时写入 `app_version.txt` 打进包，并在主界面左侧栏底部水平居中显示纯版本字符串。

**Architecture:** 新增 `sn_manager.app.version.resolve_app_version()`：优先读 `app_version.txt`（frozen 用 `_MEIPASS`，开发态 cwd / 向上查找），否则 `git describe --tags --always --long`，再否则 `unknown`。`MainWindow` 左侧面板底部用 `QLabel` 展示。`build.sh` 与 Windows CI 构建前生成文件并 `--add-data` 打入。

**Tech Stack:** Python 3.12、PySide6、PyInstaller、Bash、GitHub Actions（Windows）。

## Global Constraints

- 版本格式：`git describe --tags --always --long` 单行（strip）；失败为 `unknown`
- 文件路径：仓库根 `app_version.txt`；不入库；`.gitignore` 用 `/app_version.txt`
- 界面：纯版本字符串、无前缀；左侧筛选栏底部、水平居中；小号次要色
- 不把界面版本同步到 `pyproject.toml` / `__version__`
- 规格：`docs/superpowers/specs/2026-07-31-app-version-display-design.md`

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `src/sn_manager/app/version.py` | `resolve_app_version()` 及文件/git 查找 |
| `tests/test_app_version.py` | 解析顺序单测 |
| `src/sn_manager/app/__init__.py` | 导出 `resolve_app_version`（可选，与现有风格一致即可） |
| `src/sn_manager/gui/main_window.py` | 左侧底部版本 `QLabel` |
| `tests/test_export_dialog.py` 或新建 `tests/test_main_window_version.py` | 断言标签文案 |
| `scripts/git-version.sh` | 仓库根修正；纳入版本控制 |
| `scripts/build.sh` | 生成文件 + `--add-data` |
| `.github/workflows/release-windows-gui.yml` | 生成文件 + Windows `--add-data` |
| `.gitignore` | `/app_version.txt`；去掉 `scripts/app_version.txt` |
| `docs/superpowers/specs/2026-07-31-windows-ci-release-design.md` | 改为允许/要求 `app_version.txt` |
| `docs/superpowers/plans/2026-07-31-windows-ci-release.md` | 同步去掉「不引入」约束（轻量） |
| `docs/superpowers/specs/2026-07-31-app-version-display-design.md` | 状态改为已确认 |

---

### Task 1: `resolve_app_version` + `git-version.sh` + `.gitignore`

**Files:**
- Create: `src/sn_manager/app/version.py`
- Create: `tests/test_app_version.py`
- Modify: `src/sn_manager/app/__init__.py`
- Modify: `scripts/git-version.sh`（若尚未按仓库根修正；当前为 untracked，一并纳入）
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 无（stdlib：`sys`、`subprocess`、`pathlib`）
- Produces: `resolve_app_version() -> str`

- [ ] **Step 1: 写失败单测**

创建 `tests/test_app_version.py`：

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import sn_manager.app.version as version_mod
from sn_manager.app.version import resolve_app_version


def test_reads_app_version_file_from_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod.sys, "frozen", False, raising=False)
    if hasattr(version_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(version_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app_version.txt").write_text("v1.2.3-0-gabcdef0\n", encoding="utf-8")
    monkeypatch.setattr(version_mod, "_git_describe", lambda _cwd: "should-not-use")
    assert resolve_app_version() == "v1.2.3-0-gabcdef0"


def test_frozen_reads_meipass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(version_mod.sys, "_MEIPASS", str(tmp_path), raising=False)
    (tmp_path / "app_version.txt").write_text("packaged-ver\n", encoding="utf-8")
    monkeypatch.setattr(version_mod, "_git_describe", lambda _cwd: "should-not-use")
    assert resolve_app_version() == "packaged-ver"


def test_falls_back_to_git_describe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod.sys, "frozen", False, raising=False)
    if hasattr(version_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(version_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(version_mod, "_walk_app_version_files", lambda: [])
    monkeypatch.setattr(version_mod, "_git_describe", lambda _cwd: "v0.1.0-5-gdeadbeef")
    assert resolve_app_version() == "v0.1.0-5-gdeadbeef"


def test_unknown_when_no_file_and_no_git(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(version_mod.sys, "frozen", False, raising=False)
    if hasattr(version_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(version_mod.sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(version_mod, "_walk_app_version_files", lambda: [])
    monkeypatch.setattr(version_mod, "_git_describe", lambda _cwd: None)
    assert resolve_app_version() == "unknown"
```

- [ ] **Step 2: 跑测确认失败**

Run: `uv run pytest tests/test_app_version.py -v`

Expected: FAIL（模块或符号不存在）

- [ ] **Step 3: 实现 `version.py`**

创建 `src/sn_manager/app/version.py`：

```python
"""应用版本解析（界面展示用，与 scripts/git-version.sh 同格式）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_APP_VERSION_NAME = "app_version.txt"
_MAX_WALK_UP = 8


def _read_version_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def _walk_app_version_files() -> list[Path]:
    """开发态候选路径：cwd，再从本模块向上最多 _MAX_WALK_UP 层。"""
    candidates: list[Path] = []
    cwd_file = Path.cwd() / _APP_VERSION_NAME
    candidates.append(cwd_file)
    here = Path(__file__).resolve().parent
    for i, parent in enumerate([here, *here.parents]):
        if i > _MAX_WALK_UP:
            break
        path = parent / _APP_VERSION_NAME
        if path not in candidates:
            candidates.append(path)
    return candidates


def _git_describe(cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "describe", "--tags", "--always", "--long"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    text = (completed.stdout or "").strip()
    return text or None


def resolve_app_version() -> str:
    """返回界面用版本字符串；永不抛给调用方。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            found = _read_version_file(Path(meipass) / _APP_VERSION_NAME)
            if found is not None:
                return found
    else:
        for path in _walk_app_version_files():
            found = _read_version_file(path)
            if found is not None:
                return found

    described = _git_describe(Path.cwd())
    if described is not None:
        return described
    return "unknown"
```

- [ ] **Step 4: 更新 `app/__init__.py` 导出**

在 `src/sn_manager/app/__init__.py` 中增加：

```python
from sn_manager.app.version import resolve_app_version
```

并加入 `__all__`：`"resolve_app_version"`。

- [ ] **Step 5: 修正并纳入 `scripts/git-version.sh`**

将文件内容设为：

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

VERSION=""
if command -v git >/dev/null 2>&1; then
        VERSION="$(git -C "${ROOT_DIR}" describe --tags --always --long 2>/dev/null || true)"
fi

if [[ -z "${VERSION:-}" ]]; then
        VERSION="unknown"
fi

printf "%s\n" "${VERSION}"
```

确保可执行：`chmod +x scripts/git-version.sh`。

- [ ] **Step 6: 更新 `.gitignore`**

将 `scripts/app_version.txt` 替换为：

```
/app_version.txt
```

- [ ] **Step 7: 跑测确认通过**

Run: `uv run pytest tests/test_app_version.py -v`

Expected: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add src/sn_manager/app/version.py src/sn_manager/app/__init__.py \
  tests/test_app_version.py scripts/git-version.sh .gitignore
git commit -m "$(cat <<'EOF'
feat: resolve app version from file or git describe

EOF
)"
```

---

### Task 2: 主界面左侧底部展示版本

**Files:**
- Modify: `src/sn_manager/gui/main_window.py`（`_build_filter_panel`）
- Create: `tests/test_main_window_version.py`

**Interfaces:**
- Consumes: `resolve_app_version() -> str`
- Produces: `MainWindow` 左侧底部 `QLabel`（属性名 `_version_label`），文案为解析结果

- [ ] **Step 1: 写失败 GUI 单测**

创建 `tests/test_main_window_version.py`：

```python
from __future__ import annotations

from pathlib import Path

from sn_manager.app.services import SnService
from sn_manager.db.connection import connect
from sn_manager.gui.main_window import MainWindow


def test_main_window_shows_resolved_version(qapp, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sn_manager.gui.main_window.resolve_app_version",
        lambda: "v9.9.9-1-gtest000",
    )
    conn = connect(tmp_path / "t.db")
    win = MainWindow(SnService(conn))
    assert win._version_label.text() == "v9.9.9-1-gtest000"
    assert int(win._version_label.alignment()) & 0x0004  # AlignHCenter == 0x0004
```

（若项目已有 `Qt.AlignmentFlag.AlignHCenter` 断言习惯，改为：

```python
from PySide6.QtCore import Qt
assert win._version_label.alignment() & Qt.AlignmentFlag.AlignHCenter
```

）

- [ ] **Step 2: 跑测确认失败**

Run: `uv run pytest tests/test_main_window_version.py -v`

Expected: FAIL（无 `_version_label` 或 import 失败）

- [ ] **Step 3: 改 `main_window.py`**

1. 增加导入：

```python
from sn_manager.app.version import resolve_app_version
```

2. 在 `_build_filter_panel` 中，`layout.addStretch()` **之后**追加：

```python
        self._version_label = QLabel(resolve_app_version())
        self._version_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        font = self._version_label.font()
        font.setPointSize(max(8, font.pointSize() - 2))
        self._version_label.setFont(font)
        self._version_label.setStyleSheet("color: #666666;")
        layout.addWidget(self._version_label)
```

保持：按钮 → `addStretch()` → 版本标签；文案无前缀。

- [ ] **Step 4: 跑测确认通过**

Run: `uv run pytest tests/test_main_window_version.py tests/test_app_version.py -v`

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/sn_manager/gui/main_window.py tests/test_main_window_version.py
git commit -m "$(cat <<'EOF'
feat: show app version on main window filter panel

EOF
)"
```

---

### Task 3: 构建脚本、Windows CI 与文档同步

**Files:**
- Modify: `scripts/build.sh`
- Modify: `.github/workflows/release-windows-gui.yml`
- Modify: `docs/superpowers/specs/2026-07-31-windows-ci-release-design.md`
- Modify: `docs/superpowers/plans/2026-07-31-windows-ci-release.md`（去掉「不引入 app_version.txt」类约束）
- Modify: `docs/superpowers/specs/2026-07-31-app-version-display-design.md`（状态 → 已确认）

**Interfaces:**
- Consumes: `scripts/git-version.sh` 输出
- Produces: 打进 PyInstaller 包的根级 `app_version.txt`（`--add-data` 目标 `.`）

- [ ] **Step 1: 更新 `scripts/build.sh`**

完整文件应为：

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

echo "Built: dist/sn-manager/sn-manager"
```

- [ ] **Step 2: 更新 Windows workflow 构建步骤**

在 `Install dependencies` 与 `Build executable` 之间增加一步（或在 Build 脚本开头）：

```yaml
      - name: Write app_version.txt
        shell: bash
        run: ./scripts/git-version.sh > app_version.txt
```

并将 Build 的 pyinstaller 调用改为包含：

```powershell
          uv run pyinstaller `
            --noconfirm `
            --windowed `
            --name sn-manager `
            --paths src `
            --collect-submodules PySide6 `
            --add-data "app_version.txt;." `
            src/sn_manager/__main__.py
```

注意：Windows `--add-data` 分隔符为 `;`。

- [ ] **Step 3: 修订 Windows CI 设计规格**

在 `docs/superpowers/specs/2026-07-31-windows-ci-release-design.md` §3 中，将「不引入版本写入文件…」改为：

> 构建前用 `scripts/git-version.sh` 写出仓库根 `app_version.txt`，并以 `--add-data` 打进包，供主界面展示应用版本（见 `2026-07-31-app-version-display-design.md`）。

- [ ] **Step 4: 修订 Windows CI 计划中的约束**

在 `docs/superpowers/plans/2026-07-31-windows-ci-release.md` 的 Global Constraints / 相关表格中，删除或改写「不引入 `app_version.txt`」；若计划正文含完整 workflow YAML 副本，同步补上 Write 步骤与 `--add-data`（与实际 workflow 一致）。

- [ ] **Step 5: 将应用版本规格状态改为已确认**

`docs/superpowers/specs/2026-07-31-app-version-display-design.md` 头部：`状态：已确认`。

- [ ] **Step 6: 冒烟（可选但推荐）**

在仓库根：

```bash
./scripts/git-version.sh > app_version.txt
uv run pytest tests/test_app_version.py tests/test_main_window_version.py -v
head -n 1 app_version.txt
```

Expected: 测试 PASS；`app_version.txt` 一行非空（有 git 时非 `unknown`）。不必完整跑 PyInstaller（耗时长），除非本机已有习惯。

- [ ] **Step 7: Commit**

```bash
git add scripts/build.sh .github/workflows/release-windows-gui.yml \
  docs/superpowers/specs/2026-07-31-windows-ci-release-design.md \
  docs/superpowers/plans/2026-07-31-windows-ci-release.md \
  docs/superpowers/specs/2026-07-31-app-version-display-design.md
git commit -m "$(cat <<'EOF'
build: embed app_version.txt in Linux and Windows packages

EOF
)"
```

---

## Self-Review (plan vs spec)

| 规格项 | 对应任务 |
| ---- | ---- |
| `resolve_app_version` 顺序（文件 → git → unknown） | Task 1 |
| frozen `_MEIPASS` / 开发 cwd+向上查找 | Task 1 |
| `git-version.sh` 仓库根 | Task 1 |
| `.gitignore` `/app_version.txt` | Task 1 |
| 左下纯字符串、水平居中、小号次要色 | Task 2 |
| `build.sh` / Windows CI `--add-data` | Task 3 |
| 修订「不引入 app_version.txt」 | Task 3 |
| 不改 `__version__` / 右侧布局 / 导出 | 未引入相关改动 |

无 TBD；`resolve_app_version` 签名在 Task 1/2 一致。
