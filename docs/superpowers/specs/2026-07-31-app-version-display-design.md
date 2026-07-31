# 主界面应用版本号展示设计

日期：2026-07-31  
状态：待用户审阅  
关联：`scripts/git-version.sh`；修订 `docs/superpowers/specs/2026-07-31-windows-ci-release-design.md` 中「不引入 app_version.txt」的表述

## 1. 背景与目标

产线使用打包后的 SN Manager 时需要确认构建来源。在主界面左侧筛选栏底部展示应用版本号，格式与 `scripts/git-version.sh` 一致（`git describe --tags --always --long`，失败则为 `unknown`）。

**成功标准**

- 主界面左下显示纯版本字符串（无「版本」等前缀），在左侧栏内水平居中
- 打包产物内版本来自构建时写入的 `app_version.txt`
- 开发态无该文件时，可回退到实时 `git describe`，再否则 `unknown`
- `pyproject.toml` / 包内 `__version__` 不作为界面版本来源

## 2. 版本字符串来源与解析

### 2.1 格式

与 `scripts/git-version.sh` 输出相同：`git describe --tags --always --long` 的单行结果（读写时均 `strip`）；拿不到则为 `unknown`。

### 2.2 文件约定

- 路径：仓库根目录 `app_version.txt`（构建工作目录为仓库根时写出）
- 内容：一行版本字符串
- 该文件由构建生成，**不入库**；`.gitignore` 改为忽略 `/app_version.txt`，并去掉已过时的 `scripts/app_version.txt` 忽略项（若仍存在）

### 2.3 运行时解析顺序

单一函数（放在 `sn_manager.app` 层，如 `resolve_app_version() -> str`）：

1. 读取 `app_version.txt`：
   - frozen：`Path(sys._MEIPASS) / "app_version.txt"`（与 `--add-data ...:.` 对应）
   - 开发态：先试 `Path.cwd() / "app_version.txt"`；若无，再从包安装路径向上查找名为 `app_version.txt` 的文件（最多若干层，通常落到仓库根）
   - 读到且 strip 后非空则采用
2. 否则：若本机有 git，在检测到的仓库根（或 `cwd`）执行与脚本相同的 `describe`
3. 否则：返回 `unknown`

解析失败（文件读失败、git 失败等）不得抛到 UI；降级到下一步或 `unknown`。

### 2.4 `git-version.sh`

- 将脚本内仓库根解析改为 `dirname/..`（与 `build.sh` 一致），保证 `git -C` 与写出路径语义清晰
- 构建侧调用：`./scripts/git-version.sh > app_version.txt`（或等价重定向到仓库根该文件）

## 3. 主界面布局

在左侧筛选面板 `_build_filter_panel` 中，于「查询 / 生成 / 主数据」与 `addStretch()` **之后**增加只读 `QLabel`：

```
│ 筛选条件 …          │
│ [查询]              │
│ [生成]              │
│ [主数据]            │
│                     │  ← stretch
│   <version string>  │  ← 水平居中
└─────────────────────┴──
```

- 文案：直接为 `resolve_app_version()` 返回值
- 对齐：在左侧栏宽度内水平居中（`AlignHCenter`）
- 样式：小号、次要色，不抢筛选区焦点；无边框/卡片
- 不写入窗口标题；不随查询刷新；不参与业务逻辑

## 4. 构建与 CI

| 入口 | 改动 |
| ---- | ------ |
| `scripts/build.sh` | PyInstaller 前生成仓库根 `app_version.txt`；增加 `--add-data "app_version.txt:."`（Linux `:`） |
| `.github/workflows/release-windows-gui.yml` | 构建前写出同文件（可用 bash 调 `git-version.sh`，或等价 `git describe`）；`--add-data` 使用 Windows `;` 分隔 |
| Windows CI 设计/计划文档 | 删除或改写「不引入 `app_version.txt`」；改为：为界面版本展示**有意**引入该文件 |

`checkout` 的 `fetch-depth: 0` 已满足 `git describe` 需要 tag 历史。

## 5. 测试

- 单测 `resolve_app_version()`：有文件读文件；无文件时 mock git 成功/失败与 `unknown` 回退
- GUI：手工确认左下居中与文案；可选断言标签文本等于解析结果（不强制截图）

## 6. 非目标

- 不同步界面版本到 `pyproject.toml` / `__version__`
- 不做检查更新 / 联网拉取版本
- 不改右侧结果区布局
- 不把应用版本写入数据库或导出文件

## 7. 风险与注意

- PyInstaller `--add-data` 在 Windows / Linux 分隔符不同，脚本与 CI 需分别写对
- frozen 与开发态文件查找路径必须测到，避免打包后恒为 `unknown`
- `git describe --long` 字符串可能较长，左侧栏约 280px；小号字 + 居中即可，不做省略号策略（若极端过长可后续再加）
