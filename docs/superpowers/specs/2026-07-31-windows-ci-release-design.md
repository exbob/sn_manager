# Windows CI 自动发布设计

日期：2026-07-31  
状态：已确认

## 1. 背景与目标

当前 Windows 可执行文件依赖本机 `scripts/build.ps1`（PyInstaller onedir）。改为在 GitHub Actions 上构建并发布，对齐 [axes-previewer `release-windows-gui.yml`](https://github.com/exbob/axes-previewer/blob/main/.github/workflows/release-windows-gui.yml) 的触发与发布模式。

**成功标准**
- 删除本地 Windows 打包入口（`scripts/build.ps1`）
- 保留 Linux 本地打包（`scripts/build.sh`）
- 支持手动触发与 tag 触发
- 产物为 onedir 目录的 zip；解压后可运行 `sn-manager.exe`，`sn_manager.db` 仍位于可执行文件同目录

## 2. 触发与发布行为

| 触发 | 行为 |
| ---- | ---- |
| `workflow_dispatch` | 构建 + 上传 workflow artifact；**不**创建 Release |
| `push` tags `v*` / `V*` | 构建 + 上传 artifact + 用 `softprops/action-gh-release` 挂到该 tag 的 GitHub Release（`generate_release_notes: true`） |

`permissions.contents: write`（Release 需要）。

## 3. 构建与产物

- Runner：`windows-latest`
- Python：3.12；通过 **uv** 安装依赖（与仓库开发方式一致：`uv sync`，确保含 PyInstaller 与运行时依赖）
- PyInstaller 参数与现有 Windows 脚本一致（onedir，非 onefile）：
  - `--noconfirm --windowed --name sn-manager --paths src --collect-submodules PySide6`
  - 入口：`src/sn_manager/__main__.py`
- 将 `dist/sn-manager/` 整理为 **`sn-manager-windows-<version>/`**（`<version>` 来自 `app_version.txt`，如 `v2.0.0-0-g29a42ac`），并打成同名 **`.zip`**（zip 内含一层同名顶层目录）
- Artifact / Release 附件名与上述 zip 一致（形如 `sn-manager-windows-v2.0.0-0-g29a42ac`）
- 校验：zip、包内 `sn-manager.exe`、以及同目录 `user-manual.md` 存在后再上传
- 构建前用 `scripts/git-version.sh` 写出仓库根 `app_version.txt`，并以 `--add-data` 打进包，供主界面展示应用版本（见 `2026-07-31-app-version-display-design.md`）
- 构建后将 `docs/user-manual.md` 复制为 onedir 根目录 `user-manual.md`（与 exe 同级）

## 4. 仓库改动范围

| 动作 | 路径 |
| ---- | ---- |
| 新增 | `.github/workflows/release-windows-gui.yml` |
| 删除 | `scripts/build.ps1` |
| 保留 | `scripts/build.sh` |
| 更新 | `README.md`：Windows 改为从 Release / Actions artifact 获取；Linux 仍本地构建 |
| 轻量更新 | `docs/PRD.md`、`docs/superpowers/specs/2026-07-30-sn-manager-design.md` 中「Windows 本地脚本打包」表述改为 CI |

`README.en.md` 目前为占位模板，本次不强制改写。

## 5. 文档对用户的说明要点

- 正式发布：打 `v*` tag（如 `v0.1.0`）→ 等待 Action → 从 Release 下载 `sn-manager-windows-<version>.zip`
- 试构建：Actions → 本 workflow → Run workflow → 从 Artifacts 下载同名 zip
- 解压后得到同名文件夹，启动 `sn-manager.exe`；同目录含 `sn_manager.db`（首次运行创建）与 `user-manual.md`
- Linux：继续 `./scripts/build.sh`（产物目录名仍为 `dist/sn-manager`，会复制手册）

## 6. 非目标

- 不做 Linux CI 打包
- 不改为 onefile
- 不保留或封装本地 Windows 打包脚本
- 不交叉编译

## 7. 风险与注意

- PySide6 + PyInstaller 在 Windows runner 上体积与耗时较大，属预期
- onedir zip 体积大于 onefile，但符合现有备份/同目录 DB 策略
- 仓库需已启用 Actions，且 tag 推送权限可用
