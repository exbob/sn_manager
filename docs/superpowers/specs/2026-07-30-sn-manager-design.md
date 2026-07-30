# SN Manager 设计规格

**日期**：2026-07-30  
**状态**：待用户审阅  
**关联**：产品需求见仓库根目录 `PRD.md`

## 1. 背景与目标

产线单机 Windows 桌面工具：本地生成、查询、管理设备序列号（SN），数据存本机，无需联网。Linux 下用 Python + uv 开发，PyInstaller 打包为 Windows exe。

首期只实现 SN **Version A**（17 字符），版本首字符预留扩展。

## 2. 已确认需求摘要

| 项 | 决策 |
| ---- | ------ |
| 部署 | 单机本地，无多机共享、无登录 |
| UI | PySide6 中文 GUI |
| 打包 | PyInstaller |
| 存储 | SQLite 单文件 `sn_manager.db` |
| 生成 | 统一「数量 N」；N=1 为单个 |
| 主数据 | 下拉选择 + 可临时新增并保存 |
| 生产日期 | 默认当天，可改（支持补录） |
| 状态 | `unused` / `used` / `void`，可任意互改；作废不回收序号 |
| 导出 | 一个 Excel；多个 `sn_<SN>.txt`（每文件一行 SN）；导出 txt 可选标为 used |
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

优先：与 exe 同目录的 `sn_manager.db`（开发态可为项目数据目录）。启动时若无法创建/打开，中文报错并给出路径。

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

- 精确：按完整 `sn`；可先做格式校验
- 筛选：型号、批次、单位、市场、日期范围、状态；分页
- 状态：三态任意更新，写 `updated_at`

### 5.3 导出

- Excel：当前筛选结果 → 单文件 `.xlsx`（SN、各解析字段、状态、时间戳）
- 烧写：目录下 `sn_<设备序列号>.txt`，内容仅一行 SN  
  - 选项「导出后标为已使用」：全部文件写成功后，再批量 `status=used`；任一文失败则不改状态并报告失败项

## 6. GUI 信息架构（首期）

建议页面/区域（实现时可合并为少标签）：

1. **生成**：参数表单 + 数量 + 结果列表
2. **查询**：精确框 + 筛选条件 + 结果表（多选改状态、导出入口）
3. **主数据**：四类编码维护

不做登录、不做网络同步。

## 7. 打包与交付

- 开发：`uv` 管理依赖与虚拟环境
- 交付：PyInstaller 生成 Windows exe；说明备份 `sn_manager.db` 即可迁移历史数据

## 8. 测试策略

**自动化（`sn_core` / `sn_app`+临时库）**

- 编解码往返；月日字母边界；`000`/`FFF`
- 非法长度/字符/日期码拒绝
- 同维度连续 seq；作废不回收；触顶整批无写入
- N=1 与 N>1；导出后标 used 仅全成功后生效

**手工**

- Windows exe 启动、库路径、典型路径：生成 → 导出 txt → used → 筛选导出 Excel

## 9. 明确不在首期范围

- 多机共享序号池 / 服务端
- 用户权限与登录
- Version A 以外的 SN 版本实现
- 标签打印驱动对接
- CLI（架构预留，首期不交付）

## 10. 开放实现细节（不阻塞需求）

以下实现阶段选定即可，不改变产品行为：

- ORM（如 SQLAlchemy）vs 手写 SQL
- Excel 库（如 openpyxl）
- 精确的「exe 旁 vs AppData」路径策略（需在安装说明中写死一种）
