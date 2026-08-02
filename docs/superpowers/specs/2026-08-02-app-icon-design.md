# 应用图标设计

日期：2026-08-02  
状态：已确认  
关联：`src/sn_manager/__main__.py`；`scripts/build.sh`；`.github/workflows/release-windows-gui.yml`；`sn-manager.spec`

## 1. 背景与目标

sn-manager 为 PySide6 桌面工具，当前窗口标题栏 / 任务栏与 Windows `sn-manager.exe` 均使用系统默认图标，辨识度不足。

**成功标准**

- 运行时窗口与任务栏显示自定义应用图标
- Windows 发行包中的 `sn-manager.exe` 显示同一套视觉的文件图标
- 图标资源缺失时静默降级为系统默认图标，不弹窗、不中断启动

## 2. 视觉规格

- **形态**：圆形底 + 居中字母 **SN**（粗体无衬线）
- **颜色**：底 `#EA580C`，字 `#FFFFFF`；画布透明；无描边
- **构图**：圆约占画布 88%–90%；字母垂直居中略偏视觉中线，保证 16×16 仍可辨认
- **风格**：简洁工具感字母标（非条码/芯片插画）

## 3. 资源与文件布局

目录：`assets/icons/`

| 文件 | 用途 |
| ---- | ---- |
| `sn-manager.svg` | 矢量源文件（入库） |
| `sn-manager.png` | 256×256，运行时 `QIcon`（入库） |
| `sn-manager.ico` | 多尺寸（至少含 16 / 32 / 48 / 256），Windows exe 图标（入库） |

可选：`scripts/export-icon.sh`，从 SVG 导出 PNG/ICO。若构建环境缺少转换工具，以仓库内预生成的 PNG/ICO 为准。

图标不进入业务层或数据库；仅 GUI 启动与打包脚本引用。

## 4. 运行时接入

在 `src/sn_manager/__main__.py` 创建 `QApplication` 后、创建主窗口前：

1. 解析图标路径（建议小函数，如 `resolve_app_icon_path() -> Path | None`）
2. 若路径有效：`app.setWindowIcon(QIcon(str(path)))`
3. 路径无效或文件缺失：跳过，不抛错、不弹窗

**路径解析约定**（对齐既有 `resolve_user_manual_path` / `resolve_app_version` 风格）

- 运行时只用 `sn-manager.png`；`.ico` 仅给 PyInstaller `--icon`，不参与 `QIcon` 加载
- frozen：`Path(sys._MEIPASS) / "assets" / "icons" / "sn-manager.png"`（须与下方 `--add-data` 目标一致）；文件不存在则 `None`
- 开发态：候选顺序为 `Path.cwd() / "assets/icons/sn-manager.png"`，再从解析函数所在模块 `__file__` 向上最多若干层查找同相对路径；命中且为文件则返回，否则 `None`

## 5. 打包（exe 文件图标）

`--add-data` **固定**纳入整个 `assets/icons` 目录，目标名为 `assets/icons`（Linux `:` / Windows `;`），以便 frozen 路径为 `_MEIPASS/assets/icons/sn-manager.png`。

| 入口 | 改动 |
| ---- | ---- |
| `scripts/build.sh` | `--icon assets/icons/sn-manager.ico`；`--add-data "assets/icons:assets/icons"` |
| `.github/workflows/release-windows-gui.yml` | `--icon ...`；`--add-data "assets/icons;assets/icons"` |
| `sn-manager.spec` | `EXE(..., icon='assets/icons/sn-manager.ico')`；`datas` 纳入 `assets/icons`（若继续使用 spec） |

Linux 本地打包：窗口/任务栏图标仍生效；`.exe` 文件图标仅 Windows 相关。

## 6. 测试

- 单测路径解析：资源存在时返回可用路径；缺失时返回 `None` 且不抛错
- 不做截图或像素级 GUI 断言；手工确认窗口图标与 Windows 资源管理器中 exe 图标

## 7. 非目标

- 不制作安装程序 / 开始菜单快捷方式单独图标资源（与 exe 同源即可）
- 不引入 Qt `.qrc` 资源系统
- 不改动业务功能、窗口标题文案或应用整体主题/样式（仅图标资源与接入）
