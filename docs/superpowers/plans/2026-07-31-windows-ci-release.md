# Windows CI 自动发布 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除本地 Windows PyInstaller 脚本，改为 GitHub Actions 在 tag / 手动触发时构建 onedir zip 并（仅 tag）发布到 Release。

**Architecture:** 新增单一 workflow `release-windows-gui.yml`（`windows-latest` + uv + PyInstaller onedir → zip → artifact；tag 时 `softprops/action-gh-release`）。保留 `scripts/build.sh`；同步 README / PRD / 既有设计规格中的 Windows 打包说明。

**Tech Stack:** GitHub Actions、`astral-sh/setup-uv`、Python 3.12、uv、PyInstaller、`actions/upload-artifact@v4`、`softprops/action-gh-release@v2`。

## Global Constraints

- 产物形态：PyInstaller **onedir**，再打成 `sn-manager-windows.zip`（非 onefile）
- 触发：`workflow_dispatch`（仅 artifact）+ push tags `v*` / `V*`（artifact + Release）
- 删除 `scripts/build.ps1`；保留 `scripts/build.sh`
- PyInstaller 参数与删除前 `build.ps1` 一致：`--noconfirm --windowed --name sn-manager --paths src --collect-submodules PySide6`，入口 `src/sn_manager/__main__.py`
- 不做 Linux CI；不引入 `app_version.txt`
- 规格来源：`docs/superpowers/specs/2026-07-31-windows-ci-release-design.md`

## File Structure

| 文件 | 职责 |
| ---- | ---- |
| `.github/workflows/release-windows-gui.yml` | Windows 构建、打包 zip、上传 artifact、tag 时发 Release |
| `scripts/build.ps1` | **删除**（本地 Windows 打包入口） |
| `scripts/build.sh` | 不变（Linux 本地打包） |
| `README.md` | Windows 获取方式改为 Release / Actions；Linux 仍本地脚本 |
| `docs/PRD.md` | 轻量：Windows 交付改为 CI |
| `docs/superpowers/specs/2026-07-30-sn-manager-design.md` | 轻量：打包交付改为 Windows CI + Linux 本地脚本 |

---

### Task 1: 新增 Windows release workflow

**Files:**
- Create: `.github/workflows/release-windows-gui.yml`

**Interfaces:**
- Consumes: 仓库根 `pyproject.toml` / `uv.lock`、`src/sn_manager/__main__.py`
- Produces: artifact `sn-manager-windows`（内容为 `sn-manager-windows.zip`）；tag 时 Release 附件同名 zip

- [ ] **Step 1: 创建目录并写入完整 workflow**

创建文件 `.github/workflows/release-windows-gui.yml`，内容必须为：

```yaml
name: Release Windows GUI

on:
  push:
    tags:
      - "v*"
      - "V*"
  # Actions → 本 workflow → Run workflow；仅构建并上传 artifact，不创建 Release
  workflow_dispatch:

permissions:
  contents: write

jobs:
  windows-gui:
    runs-on: windows-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"
          enable-cache: true

      - name: Install dependencies
        run: uv sync

      - name: Build executable (PyInstaller onedir)
        shell: pwsh
        run: |
          uv run pyinstaller `
            --noconfirm `
            --windowed `
            --name sn-manager `
            --paths src `
            --collect-submodules PySide6 `
            src/sn_manager/__main__.py

      - name: Zip onedir and verify
        shell: pwsh
        run: |
          $dir = Join-Path $env:GITHUB_WORKSPACE "dist/sn-manager"
          $exe = Join-Path $dir "sn-manager.exe"
          $zip = Join-Path $env:GITHUB_WORKSPACE "sn-manager-windows.zip"
          if (-not (Test-Path -LiteralPath $exe)) { throw "Missing $exe" }
          if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
          Compress-Archive -Path (Join-Path $dir "*") -DestinationPath $zip
          if (-not (Test-Path -LiteralPath $zip)) { throw "Missing $zip" }
          Get-Item -LiteralPath $zip | Format-List Name, Length

      - name: Upload workflow artifact (manual runs / backup)
        uses: actions/upload-artifact@v4
        with:
          name: sn-manager-windows
          path: sn-manager-windows.zip
          if-no-files-found: error

      - name: Upload to GitHub Release
        if: github.ref_type == 'tag'
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ github.ref_name }}
          files: sn-manager-windows.zip
          fail_on_unmatched_files: true
          generate_release_notes: true
```

- [ ] **Step 2: 静态核对 workflow 要点**

在仓库根执行：

```bash
test -f .github/workflows/release-windows-gui.yml
grep -q 'workflow_dispatch' .github/workflows/release-windows-gui.yml
grep -q 'sn-manager-windows.zip' .github/workflows/release-windows-gui.yml
grep -q 'softprops/action-gh-release' .github/workflows/release-windows-gui.yml
grep -q 'collect-submodules PySide6' .github/workflows/release-windows-gui.yml
```

Expected: 每条命令 exit code 0。

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release-windows-gui.yml
git commit -m "$(cat <<'EOF'
ci: add Windows GUI release workflow

EOF
)"
```

---

### Task 2: 删除本地 Windows 打包并更新 README

**Files:**
- Delete: `scripts/build.ps1`
- Modify: `README.md`（「使用打包产物」与相关注意事项）

**Interfaces:**
- Consumes: Task 1 的 workflow 行为（artifact / Release / zip 名）
- Produces: 用户文档与仓库入口一致（无 `build.ps1`）

- [ ] **Step 1: 删除 `scripts/build.ps1`**

```bash
rm scripts/build.ps1
test ! -f scripts/build.ps1
test -f scripts/build.sh
```

Expected: `build.ps1` 不存在，`build.sh` 仍在。

- [ ] **Step 2: 更新 `README.md` 打包相关章节**

将「使用打包产物」整节替换为：

```markdown
## 使用打包产物

### Windows

由 GitHub Actions 构建 **onedir** 并打成 `sn-manager-windows.zip`：

| 场景 | 做法 |
| ---- | ---- |
| 正式发布 | 推送 `v*` / `V*` tag（如 `v0.1.0`）→ 等待 [Release Windows GUI](.github/workflows/release-windows-gui.yml) → 从 GitHub Release 下载 zip |
| 试构建 | Actions → Release Windows GUI → Run workflow → 从 Artifacts 下载（不创建 Release） |

解压后运行 `sn-manager.exe`。可执行文件与 `sn_manager.db` 位于同一目录，便于备份与迁移。

### Linux

| 构建命令 | 启动方式 |
| -------- | -------- |
| `./scripts/build.sh` | `./dist/sn-manager/sn-manager` |

同样为 **onedir**：产物在 `dist/sn-manager/`。
```

将「注意事项」中「分平台构建」一条替换为：

```markdown
- **分平台构建**：Windows 可执行文件由 GitHub Actions（`windows-latest`）构建；Linux 在本地用 `scripts/build.sh` 构建。PyInstaller 不支持可靠交叉编译。
```

不要改动「运行环境」「数据备份」「开发」「软件架构」等无关段落的实质内容（可随上下文微调措辞，但勿扩写新功能）。

- [ ] **Step 3: 核对 README 不再引用 `build.ps1`**

```bash
grep -n 'build.ps1\|build\.ps1' README.md || true
grep -q 'sn-manager-windows.zip' README.md
grep -q 'scripts/build.sh' README.md
```

Expected: 第一条无匹配行（或仅 `|| true` 后空）；后两条 exit 0。

- [ ] **Step 4: Commit**

```bash
git add -u scripts/build.ps1 README.md
git commit -m "$(cat <<'EOF'
chore: drop local Windows build script; document CI release

EOF
)"
```

---

### Task 3: 同步 PRD 与既有设计规格表述

**Files:**
- Modify: `docs/PRD.md`
- Modify: `docs/superpowers/specs/2026-07-30-sn-manager-design.md`

**Interfaces:**
- Consumes: 设计规格 `2026-07-31-windows-ci-release-design.md` 第 4 节
- Produces: 文档与「Windows CI + Linux 本地脚本」一致

- [ ] **Step 1: 更新 `docs/PRD.md`**

在「基本要求」中，将：

```markdown
- **运行环境**：Windows 或 Linux 单机；需能分别打包出 **Windows 可执行文件** 与 **Linux 可执行文件**（PyInstaller）。
```

改为：

```markdown
- **运行环境**：Windows 或 Linux 单机；Windows 可执行文件由 GitHub Actions（PyInstaller）发布，Linux 可执行文件由本地 PyInstaller 脚本构建。
```

在「技术方案 / 选型」中，将：

```markdown
- **方案**：桌面 GUI（PySide6）+ 本地 SQLite + 领域核心库；用 **PyInstaller** 分别打包 Windows（`.exe`）与 Linux 可执行文件
```

改为：

```markdown
- **方案**：桌面 GUI（PySide6）+ 本地 SQLite + 领域核心库；用 **PyInstaller** 打包：Windows 经 CI 产出 onedir zip，Linux 经本地脚本产出 onedir
```

将打包约束保留为已有表述即可（已含「或在对应系统的 CI 中构建」）。若验收相关条目仍写「Windows / Linux 各自打包后…」，改为：

```markdown
- Windows：从 Release / Actions artifact 获取 zip 后启动与读写库文件的手工验证；Linux：本地打包后同等验证
```

（仅当 `docs/PRD.md` 中确有对应「手工验证」 bullet 时替换；无则跳过该 bullet。）

- [ ] **Step 2: 更新 `docs/superpowers/specs/2026-07-30-sn-manager-design.md`**

将概要表中打包一行改为：

```markdown
| 打包 | Windows：GitHub Actions PyInstaller onedir zip；Linux：本地 `scripts/build.sh` |
```

将「## 7. 打包与交付」中构建相关两条改为：

```markdown
- 交付：Windows 从 GitHub Release（或试构建 artifact）获取 `sn-manager-windows.zip`；Linux 用 `scripts/build.sh` 生成 onedir；说明备份 `sn_manager.db` 即可在同平台迁移历史数据
- 构建：Windows 在 `windows-latest` CI 上构建；Linux 在本地 Linux 环境构建；不把跨 OS 交叉编译作为要求
```

手工验收中涉及 Windows 打包的表述改为「使用 CI 产物 zip」，勿要求本地 `build.ps1`。

- [ ] **Step 3: 确认无残留 `build.ps1` 引用（实现范围内）**

```bash
rg -n 'build\.ps1' README.md docs/PRD.md docs/superpowers/specs/2026-07-30-sn-manager-design.md docs/superpowers/specs/2026-07-31-windows-ci-release-design.md .github || true
test ! -f scripts/build.ps1
```

Expected: 设计规格 `2026-07-31-...` 可提及「删除 build.ps1」作为历史目标；`README.md` / `PRD.md` / `2026-07-30-...-design.md` / `.github` 中不应再把 `build.ps1` 当作现行入口。历史 plan `docs/superpowers/plans/2026-07-30-sn-manager.md` **不要改**。

- [ ] **Step 4: Commit**

```bash
git add docs/PRD.md docs/superpowers/specs/2026-07-30-sn-manager-design.md
git commit -m "$(cat <<'EOF'
docs: align PRD and design with Windows CI packaging

EOF
)"
```

---

## Spec coverage (self-review)

| 规格要求 | 对应 Task |
| -------- | --------- |
| 删除 `scripts/build.ps1` | Task 2 |
| 保留 `scripts/build.sh` | Task 2 校验 |
| `workflow_dispatch` + tag `v*`/`V*` | Task 1 |
| onedir → `sn-manager-windows.zip` | Task 1 |
| artifact 始终上传；Release 仅 tag | Task 1 |
| uv + Python 3.12 + 原 PyInstaller 参数 | Task 1 |
| 更新 README | Task 2 |
| 轻量更新 PRD + 2026-07-30 设计规格 | Task 3 |
| 不做 Linux CI / onefile / app_version | 未加入任何 Task |

无 TBD/占位；产物名与 README 一致为 `sn-manager-windows.zip`。
