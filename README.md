# sn-manager

产线单机桌面工具：本地生成、查询、导出设备序列号（Version A），数据存本机 SQLite，无需联网。

## 运行环境

- **操作系统**：Windows 或 Linux 单机
- **中文字体（Linux/WSL 必看）**：界面为中文。若中文显示为乱码或方框，说明系统缺少中文字体。任选其一：
  - `sudo apt install fonts-noto-cjk`（推荐）
  - 或将 `NotoSansCJK-Regular.ttc` 放到 `~/.local/share/fonts/` 后执行 `fc-cache -f`
- **数据文件**：与可执行文件同目录的 `sn_manager.db`（首次运行自动创建）
- **开发运行**（需 Python ≥3.12 与 [uv](https://docs.astral.sh/uv/)）：

```bash
uv sync
uv run sn-manager
```

开发态下数据库位于当前工作目录的 `sn_manager.db`。

## 使用打包产物

| 平台 | 构建命令 | 启动方式 |
| ---- | -------- | -------- |
| Linux | `./scripts/build.sh` | `./dist/sn-manager/sn-manager` |
| Windows | `.\scripts\build.ps1` | `dist\sn-manager\sn-manager.exe` |

采用 **onedir** 打包：可执行文件与 `sn_manager.db` 位于同一目录（`dist/sn-manager/`），便于备份与迁移。

## 数据备份

定期复制 `sn_manager.db` 到安全位置即可整库备份。恢复时将文件放回可执行文件同目录，覆盖前请先关闭程序。

## 注意事项

- **勿双开**：同一台机器上不要同时运行多个实例指向同一 `sn_manager.db`，否则可能导致 SQLite 写入冲突或数据损坏。
- **分平台构建**：PyInstaller 需在目标操作系统上构建（Linux 脚本产出 Linux 可执行文件，Windows 脚本产出 `.exe`），不支持可靠交叉编译。

## 开发

```bash
uv sync
uv run pytest -v
```

## 软件架构

PySide6 GUI → 应用服务层 → 领域核心（SN 编解码）+ SQLite 持久化。详见 `PRD.md` 与设计规格 `docs/superpowers/specs/`。
