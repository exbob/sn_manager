# 状态着色、使用手册与版本化 Windows 发布设计

日期：2026-08-02  
状态：已确认  
关联：`src/sn_manager/gui/main_window.py`；`scripts/build.sh`；`.github/workflows/release-windows-gui.yml`；`docs/user-manual.md`；`docs/superpowers/specs/2026-07-31-windows-ci-release-design.md`；`docs/superpowers/specs/2026-07-31-app-version-display-design.md`

## 1. 背景与目标

三项小优化，提升查询结果可读性、交付物自说明性，以及多版本并存时的产物辨识度：

1. 主界面查询结果「状态」列按状态着色
2. 将 `docs/user-manual.md` 随发行包发布，并在左侧栏提供「帮助」入口
3. Windows CI 的发布目录与 zip 文件名带上 `git describe` 版本号

**成功标准**

- 未使用：默认文字色；已使用：绿色；作废：红色（文案仍为「作废」，不改为「废弃」）
- 解压后的 Windows/Linux onedir 根目录可见 `user-manual.md`；主界面左侧底部「帮助」可用系统默认程序打开该文件
- Windows artifact / Release 附件形如 `sn-manager-windows-v2.0.0-0-g29a42ac.zip`，解压得到同名文件夹
- Linux `build.sh` 仅增加手册复制，**不**改目录/zip 版本命名

## 2. 状态列着色

### 2.1 行为

在 `MainWindow._populate_table` 填充表格时，对 `status` 列的 `QTableWidgetItem` 设置前景色：

| `Status` 值 | 显示文案 | 前景色 |
|-------------|----------|--------|
| `unused` | 未使用 | 不设置（跟随默认） |
| `used` | 已使用 | `#2E7D32` |
| `void` | 作废 | `#C62828` |

颜色通过 `QColor` + `Qt.ItemDataRole.ForegroundRole`（或 `setForeground`）设置。其它列、筛选下拉、改状态对话框、导出逻辑不变。

### 2.2 测试

单测在查询填表后断言状态列对应行的前景色（未使用无自定义前景 / 已使用绿 / 作废红）。

## 3. 使用手册打包与「帮助」

### 3.1 打包位置

构建完成后，将仓库 `docs/user-manual.md` **复制为** onedir 根目录下的 `user-manual.md`（与 `sn-manager` / `sn-manager.exe` 同级）：

- Windows CI：在 zip 之前复制进 `dist/sn-manager/`
- Linux `scripts/build.sh`：构建结束后同样复制到 `dist/sn-manager/user-manual.md`

不依赖 PyInstaller `--add-data` 将手册藏入 `_MEIPASS`/`_internal`，以便用户浏览解压目录时能直接看到。

### 3.2 界面

- 左侧筛选栏底部：在版本号标签**上方**增加 `QPushButton("帮助")`
- 点击：解析本地手册路径后，用 `QDesktopServices.openUrl(QUrl.fromLocalFile(path))` 打开
- 路径解析顺序：
  1. frozen：`Path(sys.executable).resolve().parent / "user-manual.md"`
  2. 开发态：从仓库根（或包路径向上）定位 `docs/user-manual.md`
- 文件不存在或无法打开：`QMessageBox` 提示，不抛未捕获异常

路径解析可放在 `sn_manager.app.paths`（或邻近小函数），与现有 `default_db_path` / 版本解析风格一致；GUI 只负责按钮与打开。

### 3.3 测试

- 解析函数：临时目录模拟 exe 旁手册；开发态指向仓库 docs
- 主窗口：存在「帮助」按钮；可 mock `QDesktopServices.openUrl` 验证点击传入正确路径（可选，以不脆为原则）

## 4. Windows 版本化产物命名

### 4.1 版本字符串

读取构建已生成的仓库根 `app_version.txt`（与界面版本同源，`strip` 后使用）。若为空则回退为 `unknown`。

产物基名：`sn-manager-windows-<version>`  
示例：`sn-manager-windows-v2.0.0-0-g29a42ac`

### 4.2 CI 步骤（概念顺序）

1. 现有：checkout → uv sync → 写 `app_version.txt` → PyInstaller → `dist/sn-manager/`
2. 复制 `docs/user-manual.md` → `dist/sn-manager/user-manual.md`
3. 将 `dist/sn-manager` 重命名或复制为工作区根下的 `sn-manager-windows-<version>/`
4. 将该文件夹压成 `sn-manager-windows-<version>.zip`（zip 内含一层同名顶层目录）
5. `upload-artifact` 的 `name` 与 `path`、Release `files` 均指向该 zip（artifact 名可与 zip 主名一致）

Linux `build.sh`：**不**做版本化重命名/zip；仅保证手册复制。

### 4.3 文档

更新 `README.md`、`docs/user-manual.md`，以及 Windows CI 相关 design/plan 中固定文件名 `sn-manager-windows.zip` 的表述，说明正式包名为带版本后缀的 zip，解压得到同名目录。

## 5. 非目标

- 不把「作废」改名为「废弃」
- 不内嵌 HTML 帮助窗或转换 Markdown 渲染
- 不给 Linux 本地产物加版本化目录/zip 名
- 不改 `pyproject.toml` / `__version__` 作为发布命名来源

## 6. 风险与注意

- Windows 上 `.md` 的默认关联因机器而异（记事本或其它）；属已接受的「系统默认程序」行为
- `Compress-Archive` 需对**含顶层文件夹**的路径打包，避免再次压成「无外层目录」的扁平 zip
- 版本字符串中的字符对 Windows 文件名通常安全（`git describe` 常见形式）；若出现非法字符需在实现时替换（当前预期无需）
