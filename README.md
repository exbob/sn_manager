# sn-manager

## 1. 项目简介

单机桌面工具：在本机**生成、查询、导出**设备序列号（当前支持 **Version A**，固定 17 位）。数据存本机 SQLite（`sn_manager.db`），**无需联网、无登录**，面向 Windows 单机使用。

**技术方案概要**：Python（≥3.12）+ [uv](https://docs.astral.sh/uv/)；界面 **PySide6**；持久化 **SQLite**；发行包用 **PyInstaller**（onedir）。分层为 `sn_gui → sn_app → sn_core + sn_db`。

| 文档 | 说明 |
| ---- | ---- |
| [`docs/PRD.md`](docs/PRD.md) | 产品需求与规则 |
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | 设计规格 |
| [`docs/user-manual.md`](docs/user-manual.md) | 使用手册（功能与逐步操作） |

---

## 2. 使用方法

### 2.1 获取 Windows 发行版并启动

1. 打开本仓库 GitHub **Releases**，下载 **`sn-manager-windows-<version>.zip`**（version 形如 `v2.0.0-0-g29a42ac`，与构建时的 `git describe` 一致）。
2. 也可在 Actions 中手动 **Run workflow** 做试构建，从该次运行的 Artifacts 下载同名 zip（不创建 Release）。
3. 完整解压到本机目录，得到同名文件夹；运行其中的 `sn-manager.exe`（勿只拷贝单个 exe）。解压目录内另有 **`user-manual.md`**（使用手册）。
4. 首次运行会在 exe **同目录**自动创建或使用 **`sn_manager.db`**。
5. 主界面左下「**帮助**」可用系统默认程序打开同目录手册；左下角同时显示构建版本号。

**数据库文件`sn_manager.db`非常重要，所有数据都保存在这里！**

### 2.2 大致用法

典型顺序：

1. **主数据**：维护产品型号、硬件批次，并确认生产单位、市场等下拉项。
2. **生成**：选择型号/批次/单位/市场、生产日期与数量，确认后写入；右侧展示本批新 SN。
3. **查询**：左侧设条件后点「查询」；结果表可多选 / 全选。
4. **改状态 / 导出**：选中行后可改「未使用 / 已使用 / 作废」，或导出烧写 txt 和/或 Excel。

详细的使用方法见 **[`docs/user-manual.md`](docs/user-manual.md)**。

### 2.3 重要注意事项

- **统一管理**：最好由一个人统一生成和管理设备序列号，不要多人管理。
- **勿多开**：同一台机器不要多个实例同时打开同一 `sn_manager.db`，以免 SQLite 冲突或损坏数据。
- **备份**：数据库文件`sn_manager.db`非常重要，所有数据都保存在这里！可以定期备份，恢复前先关闭程序再覆盖。
- **整目录使用**：发行包为 onedir，请保留解压后的完整目录结构。

### 2.4 Linux 可执行文件（可选）

Linux 需在本机打包（PyInstaller 不支持可靠交叉编译）：

```bash
./scripts/build.sh
./dist/sn-manager/sn-manager
```

---

## 3. 开发说明

### 3.1 环境

- 操作系统：Linux（含 WSL）或 Windows 均可开发
- Python ≥ **3.12**，包管理使用 **[uv](https://docs.astral.sh/uv/)**
- **中文字体（Linux/WSL）**：界面为中文。若乱码或方框，可安装 `fonts-noto-cjk`，或将 `NotoSansCJK-Regular.ttc` 放到 `~/.local/share/fonts/` 后执行 `fc-cache -f`

### 3.2 运行与测试

```bash
uv sync
uv run sn-manager          # 开发态启动；数据库为当前工作目录下的 sn_manager.db
uv run pytest -v
```

### 3.3 构建

| 平台 | 方式 |
| ---- | ---- |
| Windows | GitHub Actions：`Release Windows GUI`（tag 发 Release，或 `workflow_dispatch` 出 artifact） |
| Linux | `./scripts/build.sh` → `dist/sn-manager/sn-manager` |

构建前会生成 `app_version.txt`（不入库），打包进产物供主界面左下角显示版本；构建后会把 `docs/user-manual.md` 复制为 onedir 根目录的 `user-manual.md`。Windows CI 的 zip / artifact 名为 `sn-manager-windows-<version>`。

### 3.4 软件架构

单向依赖，便于核心逻辑单测：

```
sn_gui (PySide6)
    → sn_app（事务编排、批量生成、导出与可选改状态）
        → sn_core（SN 编解码 / 校验 / 状态规则）
        → sn_db（SQLite 持久化与序号分配）
```

源码位于 `src/sn_manager/`。规则与数据模型细节见 [`docs/PRD.md`](docs/PRD.md)；功能级设计见 [`docs/superpowers/specs/`](docs/superpowers/specs/)。
