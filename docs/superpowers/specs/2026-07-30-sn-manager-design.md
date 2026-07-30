# SN Manager 设计规格

**日期**：2026-07-30  
**状态**：待用户审阅  
**关联**：产品需求见仓库根目录 `PRD.md`

## 1. 背景与目标

产线单机桌面工具（Windows 或 Linux）：本地生成、查询、管理设备序列号（SN），数据存本机，无需联网。用 Python + uv 开发，PyInstaller **分别**打包 Windows 与 Linux 可执行文件。

首期只实现 SN **Version A**（17 字符），版本首字符预留扩展。

## 2. 已确认需求摘要

| 项 | 决策 |
| ---- | ------ |
| 部署 | 单机本地（Windows 或 Linux），无多机共享、无登录 |
| UI | PySide6；主界面=查询；生成/主数据为对话框 |
| 打包 | PyInstaller 产出 Windows `.exe` 与 Linux 可执行文件（宜在目标 OS / 对应 CI 上构建） |
| 存储 | SQLite 单文件 `sn_manager.db` |
| 生成 | 对话框；统一「数量 N」；N=1 为单个；成功后右侧展示并默认选中 |
| 主数据 | 对话框维护；生成时下拉 + 可临时新增并保存；确认生效/取消作废 |
| 生产日期 | 默认当天，可改（支持补录） |
| 状态 | `unused` / `used` / `void`；选中行后点「改状态」；作废不回收序号 |
| 导出 | 须选中行；对话框选 Excel 或烧写 txt；烧写可选标 used；提供「全选」 |
| 序号用尽 | 拒绝整批，提示更换生产日期或硬件批次 |

## 3. 架构

### 3.1 分层

单向依赖，便于核心逻辑单测、日后可选加 CLI 而不改业务：

```
sn_gui (PySide6)
  → sn_app   应用服务：编排事务、批量生成、导出与可选状态更新
      → sn_core   SN 编解码、字段校验、状态枚举（无 I/O）
      → sn_db     SQLite 访问、序号分配、查询与更新
```

### 3.2 包/模块边界

| 单元 | 职责 | 依赖 |
| ---- | ------ | ------ |
| `sn_core` | Version A encode/decode；字符集与日期码表；`Status` 枚举 | 无 |
| `sn_db` | 表结构、迁移/建表、CRUD、事务内分配 seq | `sn_core`（可选仅用类型） |
| `sn_app` | `generate(n)`、`query`/`filter`、`set_status`、`export_excel`、`export_burn_txt` | `sn_core`, `sn_db` |
| `sn_gui` | 页面与控件；不直接写 SQL | `sn_app` |

### 3.3 数据文件位置

优先：与可执行文件同目录的 `sn_manager.db`（开发态可为项目数据目录）。启动时若无法创建/打开，中文报错并给出路径。Windows / Linux 均采用同一「相对可执行文件目录」策略，便于说明与备份。

## 4. 数据库设计

### 4.1 主数据

- `product_models(code TEXT PRIMARY KEY)` — 长度 5，字母数字大写
- `hardware_batches(code TEXT PRIMARY KEY)` — 长度 2
- `factories(code TEXT PRIMARY KEY, name TEXT)` — 长度 1；种子：1 自己生产、2 赛威思
- `markets(code TEXT PRIMARY KEY, name TEXT)` — 长度 1；种子：0 不限、1 中国、2 韩国、3 美国

删除主数据：若该编码已被任意 `serial_numbers` 引用，则拒绝删除并提示；未被引用才可删。SN 行上的型号/批次等为冗余存储，不随主数据级联改写。

### 4.2 `serial_numbers`

- `sn TEXT PRIMARY KEY`
- 解析列：`version`, `product_model`, `hw_batch`, `factory`, `market`, `prod_year`, `prod_month`, `prod_day`, `seq`
- `status TEXT NOT NULL` — `unused` | `used` | `void`
- `created_at`, `updated_at` — ISO 或 Unix 时间，实现时统一一种
- **UNIQUE** `(product_model, hw_batch, prod_year, prod_month, prod_day, seq)`

索引建议：`(product_model, hw_batch, prod_year, prod_month, prod_day)`、`status`、生产日相关筛选列按查询需要补齐。

### 4.3 序号分配算法

在同一写事务中：

1. `SELECT MAX(seq) FROM serial_numbers WHERE …维度…`
2. 起始 `start = (max or -1) + 1`；若 `start + n - 1 > 4095` → 抛业务错误，事务回滚
3. 对 `seq in [start, start+n)` 编码并 INSERT，`status=unused`

作废只改 `status`，不删除行，故 `MAX(seq)` 仍占用，满足「不回收」。

## 5. 应用行为

### 5.1 生成

1. 校验各字段（含日期与 N≥1）
2. 主数据缺失则插入（用户选择「新增并保存」路径）
3. 按 §4.3 分配并提交
4. 返回 SN 列表供 UI 展示/复制

错误文案要点：序号不足时明确「请更换生产日期或硬件批次」。

### 5.2 查询与状态

- 主界面左侧筛选（型号、批次、单位、市场、日期范围、状态、完整 SN 等）→「查询」刷新右侧表
- 右侧多选 +「全选」；「改状态」对选中行三态任意更新，写 `updated_at`

### 5.3 导出

- 仅导出**当前选中行**；无选中时「导出」禁用
- 导出对话框：选择 Excel 或烧写 txt
- Excel：选中行 → 单文件 `.xlsx`（SN、各解析字段、状态、时间戳）
- 烧写：目录下 `sn_<设备序列号>.txt`，内容仅一行 SN  
  - 选项「导出后标为已使用」：全部文件写成功后，再批量 `status=used`；任一文失败则不改状态并报告失败项

## 6. GUI 布局

不做登录、不做网络同步。启动后进入主界面（查询）。

```
┌──────────────────┬────────────────────────────────────────┐
│ 筛选条件         │  结果表（可多选）                        │
│ …                │  [全选]  [改状态]                       │
│                  │                                        │
│ [查询]           │                                        │
│ [生成]           │                                        │
│ [主数据]         │                         [导出]（右下）  │
└──────────────────┴────────────────────────────────────────┘
```

| 操作 | 行为 |
| ---- | ------ |
| 查询 | 按左侧条件查库，填充右侧表 |
| 生成 | 模态对话框填条件与 N → 确认则生成、关窗、右侧显示新 SN（默认选中）；取消则不生成 |
| 主数据 | 模态对话框维护四类主数据 → 确认生效并关窗；取消不生效 |
| 改状态 | 须先选中行 → 选择目标状态并应用 |
| 导出 | 须先选中行 → 对话框选 Excel / 烧写 txt（烧写可勾选标为已使用） |

## 7. 打包与交付

- 开发：`uv` 管理依赖与虚拟环境
- 交付：PyInstaller 分别生成 Windows `.exe` 与 Linux 可执行文件；说明备份 `sn_manager.db` 即可在同平台迁移历史数据
- 构建：在 Windows 环境构建 Windows 包，在 Linux 环境构建 Linux 包（或等价 CI 矩阵）；不把跨 OS 交叉编译作为首期要求

## 8. 测试策略

**自动化（`sn_core` / `sn_app`+临时库）**

- 编解码往返；月日字母边界；`000`/`FFF`
- 非法长度/字符/日期码拒绝
- 同维度连续 seq；作废不回收；触顶整批无写入
- N=1 与 N>1；仅选中行可导出；导出后标 used 仅全成功后生效
- GUI 手工：启动主界面、对话框确认/取消、无选中导出禁用、生成后右侧选中新 SN

**手工**

- Windows / Linux 可执行文件各自启动、库路径、典型路径：生成 → 选中 → 导出 txt → used → 筛选查询 → 导出 Excel
## 9. 明确不在首期范围

- 多机共享序号池 / 服务端
- 用户权限与登录
- Version A 以外的 SN 版本实现
- 标签打印驱动对接
- CLI（架构预留，首期不交付）

## 10. 开放实现细节（不阻塞需求）

以下实现阶段选定即可，不改变产品行为：

- 精确的可执行文件旁数据路径在两平台的边界情况（只读安装目录等；需在安装说明中写清）
- ORM（如 SQLAlchemy）vs 手写 SQL
- Excel 库（如 openpyxl）