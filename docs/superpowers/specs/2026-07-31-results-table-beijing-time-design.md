# 结果表列顺序与北京时间显示设计

日期：2026-07-31  
状态：已确认  
关联：`src/sn_manager/gui/main_window.py`

## 1. 背景与目标

结果表目前列顺序为「… → 序号 → 状态 → 创建时间」，且无 `updated_at`；标题为「结果表（可多选）」。库内时间均为 UTC ISO-8601，主界面需要可选地按北京时间墙钟展示。

**成功标准**

1. 列顺序：序号之后依次为「创建时间」「状态」「更新时间」
2. 标题文案为「结果表」；其右侧有「北京时间」复选框，默认勾选
3. 勾选时，创建/更新时间显示为 `YYYY-MM-DD HH:MM:SS`（Asia/Shanghai）；取消勾选时显示库内 UTC 原文
4. 切换勾选即时重绘当前结果，不重新查库；导出仍为 UTC

## 2. 方案

采用 **GUI 纯显示转换**：

- 数据库与 `filter` / 改状态 / 导出逻辑不变，仍读写 UTC
- 仅在 `_populate_table` / `_refresh_rows_for_sns` 的单元格展示层按勾选状态格式化 `created_at`、`updated_at`
- 勾选状态不持久化；每次启动默认勾选

## 3. 改动点

### 3.1 列定义

`_TABLE_COLUMNS` 调整为（序号之后）：

| key | 表头 |
| ----- | ------ |
| `seq` | 序号 |
| `created_at` | 创建时间 |
| `status` | 状态 |
| `updated_at` | 更新时间 |

此前各列（SN、型号、批次、单位、市场、年、月、日）不变。

### 3.2 标题行

`_build_results_panel` 顶部行：

1. `QLabel("结果表")`
2. `QCheckBox("北京时间")`（`setChecked(True)`）
3. `addStretch()`
4. 「全选」按钮

勾选 `toggled` → 若已有 `_rows`，调用 `_populate_table(self._rows)` 重绘；重绘前记下当前选中 SN，重绘后按 SN 恢复选中。

### 3.3 时间格式化

抽一小函数（可放在 `main_window.py` 模块级）：

- 输入：原始字符串、`use_beijing: bool`
- `use_beijing=False`：原样返回
- `use_beijing=True`：解析 UTC（支持末尾 `Z` 与带偏移的 ISO），转到 `Asia/Shanghai`（或固定 `UTC+8`），输出 `strftime("%Y-%m-%d %H:%M:%S")`
- 解析失败：原样返回

`status` 列仍用 `_STATUS_LABELS`；其它列 `str(value)`。

### 3.4 刷新路径

`_populate_table` 与 `_refresh_rows_for_sns` 共用同一套「按 key 决定 display」逻辑，避免改状态后更新时间仍按旧规则显示。

## 4. 非目标

- 不改库 schema、写入格式或导出列内容（导出继续 UTC）
- 不持久化「北京时间」勾选
- 不改筛选、多选、全选语义
- 不引入新依赖（用标准库 `datetime` / `zoneinfo`）

## 5. 验证

- 列头顺序：…序号、创建时间、状态、更新时间
- 标题为「结果表」；「北京时间」默认勾选
- 勾选：两时间列为墙钟 `YYYY-MM-DD HH:MM:SS`；取消：为库内 UTC 原文
- 切换勾选：无需再点查询即可切换显示
- 改状态后「更新时间」按当前勾选规则刷新
- 导出文件中时间仍为 UTC
