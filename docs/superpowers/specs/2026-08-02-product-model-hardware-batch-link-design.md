# 产品型号与硬件批次关联设计

日期：2026-08-02  
状态：已确认  
关联：修订 `docs/PRD.md`、`docs/user-manual.md`；触及 `schema`、`master_data`、`SnService` / `MasterSnapshot`、`MasterDataDialog`、`GenerateDialog`、`MainWindow` 及对应测试

## 1. 背景与目标

当前 `product_models` 与 `hardware_batches` 为两张互不关联的主数据表，`hardware_batches.code` 全局唯一且仅有一份 `name`。

实际业务中，同一批次编码在不同产品型号下含义不同，例如：

| 产品型号 | 批次 `01` | 批次 `02` |
| -------- | --------- | --------- |
| SVG14 | 使用国产化 FPGA | 使用 Intel FPGA |
| SCP4A | 使用国产 Wi-Fi 模块 | 使用海华 Wi-Fi 模块 |

**目标**

1. 硬件批次从属于产品型号；主键为 `(product_model, code)`，名称按型号区分
2. 生成与筛选：先选型号，批次下拉仅显示该型号下的批次
3. 主数据：去掉独立「批次」Tab；在型号 Tab 内嵌套维护该型号的批次
4. 删除：有下属批次不可删型号；批次被 SN 引用（同型号+批次）不可删

**成功标准**

- 同码异义可并存（如 `SVG14/01` 与 `SCP4A/01` 名称不同）
- 生成/筛选换型号后批次列表与已选项正确清空
- 删除规则与确认/取消事务行为符合下文
- PRD 与使用手册与实现一致
- 开发期不做旧库迁移：改 schema 后删库重建

## 2. 数据模型

### 2.1 `product_models`（不变）

| 字段 | 说明 |
| ---- | ---- |
| `code` TEXT PRIMARY KEY | 5 位字母数字，大写 |
| `name` TEXT NOT NULL | 必填，≤64 |

### 2.2 `hardware_batches`（改）

| 字段 | 说明 |
| ---- | ---- |
| `product_model` TEXT NOT NULL | 所属型号（逻辑外键 → `product_models.code`） |
| `code` TEXT NOT NULL | 2 位字母数字，大写 |
| `name` TEXT NOT NULL | 该型号下该批次的含义，必填，≤64 |
| **PRIMARY KEY** | `(product_model, code)` |

所属关系由应用层保证（upsert 批次前型号须已存在；删型号前无下属批次）。是否在 DDL 中再声明 `FOREIGN KEY`，由实现计划按现有 SQLite / `PRAGMA foreign_keys` 习惯决定，行为以上文删除规则为准。

名称规则与现有四类主数据一致：去首尾空白后非空、长度 ≤64（Unicode 字符）、不参与 SN 编解码。

### 2.3 `serial_numbers`（结构不变）

仍存 `product_model`、`hw_batch` 文本列；唯一约束  
`(product_model, hw_batch, prod_year, prod_month, prod_day, seq)` 不变。

生成前必须校验：所选 `(product_model, hw_batch)` 存在于 `hardware_batches`。

### 2.4 其它

`factories` / `markets` 不变。首次启动仍只写入单位与市场种子；型号与批次由用户维护。

**迁移**：不做。直接改 DDL；已有 `sn_manager.db` 需删除重建。

## 3. 界面与交互

### 3.1 主数据对话框

- 页签改为三个：**型号**、**单位**、**市场**（去掉独立「批次」页签）
- **型号**页签：
  - 上方：型号表（编码 + 名称），支持添加/删除行
  - 下方：当前选中型号的批次表（批次编码 + 名称），支持添加/删除行
  - 未选中型号时：下方批次表为空且不可增删
  - 切换选中型号时：下方加载该型号的批次行
- **确认**：编码/名称校验；同型号内批次编码不重复；一次性落库
- **取消**：全部不落库并关闭

### 3.2 生成对话框

- 先选型号 → 批次下拉只列出该型号下的批次（展示文案：`编码 名称`）
- 未选型号、或该型号下无批次：批次为空/不可选；确认时提示先维护主数据
- 切换型号：清空已选批次并刷新批次列表

### 3.3 主界面筛选

- 与生成相同联动：型号为首项「不限」（空）时，批次为空/不可选
- 选了型号后，批次列出该型号下批次；批次首项仍可为空表示「该型号下批次不限」
- 型号变更时清空批次选择
- 主数据确认关闭后刷新型号与批次下拉

### 3.4 删除规则（确认落库时执行）

| 操作 | 条件 | 结果 |
| ---- | ---- | ---- |
| 删除型号 | 该型号下仍有批次行 | 拒绝，提示先删下属批次 |
| 删除型号 | 无下属批次，但 SN 引用了该型号编码 | 拒绝（与现有「被引用不可删」一致） |
| 删除型号 | 无下属批次且无 SN 引用 | 允许 |
| 删除批次 | 存在 SN 满足同 `product_model` + `hw_batch` | 拒绝 |
| 删除批次 | 无上述引用 | 允许 |

## 4. 服务层与 API

### 4.1 `MasterSnapshot`

`hardware_batches` 由 `list[tuple[str, str]]`（全局 code, name）改为：

`list[tuple[str, str, str]]` → `(product_model, batch_code, name)`

单位/市场形状不变；`product_models` 仍为 `list[tuple[str, str]]`。

### 4.2 db 层

- `list_hardware_batches(conn, product_model: str | None = None)`：按型号过滤；`None` 时列出全部（供同步）
- `upsert_hardware_batch(conn, product_model, code, name, *, commit=...)`
- `delete_hardware_batch(conn, product_model, code, *, commit=...)`：按 `(型号, 批次)` 检查 SN 引用
- 删型号：若该型号下仍有批次行 → 拒绝（即使尚无 SN）

### 4.3 同步顺序（同一事务）

1. Upsert 全部型号  
2. Upsert / 删除批次（按快照中的 `(型号, 批次)` 集合）  
3. 删除快照中已不存在的空型号（无下属批次）  
4. 同步单位、市场  
5. `commit`；任一步 `ValidationError` 则 `rollback`

生成路径：写入 SN 前校验 `(product_model, hw_batch)` 在主数据中存在。

### 4.4 错误文案要点

| 情况 | 提示方向 |
| ---- | -------- |
| 同型号下批次编码重复 | 该型号下批次编码重复 |
| 删型号但仍有下属批次 | 请先删除该型号下的硬件批次 |
| 删批次但仍被 SN 引用 | 该批次已被序列号引用，无法删除 |
| 生成时批次不属于型号 / 不存在 | 所选硬件批次不属于该产品型号（或不存在） |
| 未选齐主数据 / 型号无批次 | 请先维护主数据（或先选择产品型号） |

## 5. 文档同步

实现时同步修订：

1. **`docs/PRD.md`**：主数据表结构；主数据维护（型号内嵌批次、三 Tab）；生成/筛选型号→批次联动；删除规则  
2. **`docs/user-manual.md`**：§4 主数据（页签与嵌套维护、同码异义示例、删除限制）；§5 生成（先选型号再选批次）；§6 查询筛选联动说明  
3. 若 `docs/superpowers/specs/2026-07-30-sn-manager-design.md` / `2026-07-31-master-data-names-and-dropdowns-design.md` 中仍写「全局独立批次」，以本文为准并在实现计划中注明覆盖关系（可不改历史 spec 正文，避免扰乱已完成记录）

## 6. 测试要点

- 同码异义：`SVG14/01` 与 `SCP4A/01` 可并存且名称不同  
- 生成：换型号后批次列表与已选项清空；不能选他型号批次  
- 筛选：型号「不限」时批次不可用；选型号后批次正确过滤  
- 删除：有批次不可删型号；有 SN 不可删对应批次；无引用可删  
- 主数据确认落库 / 取消不落库  
- 生成前校验批次属于型号  
- schema 重建后仅单位/市场有种子数据  

## 7. 非目标（首期不做）

- 旧库自动迁移或全局批次挂靠推断  
- 跨型号按批次码单独筛选（型号「不限」时筛 `01`）  
- 批次编码在全局的强制唯一  

## 8. 方案取舍（摘要）

采用「批次表带所属型号、联合主键」，而非全局批次 + 关联表或 JSON 嵌套：直接表达同码异义，查询简单，与现有 `serial_numbers` 字段对齐，改动面可控。
