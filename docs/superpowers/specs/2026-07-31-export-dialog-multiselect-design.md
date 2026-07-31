# 导出对话框多选与共用路径设计

日期：2026-07-31  
状态：待确认  
关联：修订 `docs/PRD.md` §4/§5/流程与测试；触及 `paths`、`export`、`export_dialog`、`main_window` 与相关测试

## 1. 背景与目标

当前导出对话框用单选在「Excel」与「烧写」间切换，路径控件分成「Excel 文件」与「烧写目录」，且「导出后标为已使用」仅烧写可用。产线场景常要一次导出烧写文本（默认），有时同时要 Excel 备份，并希望路径默认落在可执行文件目录。

**目标**

1. 烧写文本与导出 Excel 可多选；默认仅烧写
2. 共用一个「导出路径」（目录）；默认 = 应用目录
3. 「导出后标为已使用」两种导出都适用，默认勾选；勾选的类型全部写成功后才标 `used`
4. Excel 文件名固定为本地时间 `YYYYMMDDHHmmss.xlsx`

**成功标准**

- 对话框：烧写在上、Excel 在下；默认仅烧写；至少选一种；共用目录路径；mark used 默认勾选
- 同目录可同时产出 `sn_*.txt` 与时间戳 `.xlsx`
- 双选时任一写失败不改状态；全部成功且勾选 mark used 才批量 `used`
- PRD 与实现一致

## 2. 对话框行为

| 控件 | 行为 |
| ---- | ---- |
| 烧写文本 | `QCheckBox`；默认勾选 |
| 导出 Excel | `QCheckBox`；默认不勾选 |
| 导出路径 | 单行目录路径 +「浏览…」（`getExistingDirectory`）；默认 `app_dir()` |
| 导出后标为已使用 | `QCheckBox`；默认勾选，可取消 |

**确认校验**

- 未勾选烧写且未勾选 Excel → 警告「请至少选择一种导出方式」，不关闭
- 导出路径为空 → 警告「请选择导出路径」，不关闭

**应用目录 `app_dir()`**

- 与库路径策略一致：`sys.frozen` 时为 `Path(sys.executable).resolve().parent`；否则 `Path.cwd()`
- 从 `paths.py` 抽出，供 `default_db_path()` 与导出对话框共用

## 3. 写出规则

| 类型 | 路径 | 内容 |
| ---- | ---- | ---- |
| 烧写 | `{export_directory}/sn_<SN>.txt` | 一行 SN；已存在则覆盖 |
| Excel | `{export_directory}/{YYYYMMDDHHmmss}.xlsx` | 现有列：SN、解析字段、状态、时间；时间戳在**确认导出时**用本地时间生成 |

写出顺序（若均勾选）：先烧写、后 Excel（任一失败即中止后续写出，已写出文件保留）。

## 4. 参数与编排

```text
ExportParams:
  burn: bool
  excel: bool
  export_directory: Path
  mark_used: bool
```

去掉互斥 `ExportMode` 及分叉的 `excel_path` / `burn_directory`。

主窗口 `_on_export`：

1. 对话框 Accepted 且拿到 `ExportParams`
2. 按勾选调用现有 `export_burn_txt` / `export_excel`（Excel 路径 = `export_directory / f"{now:%Y%m%d%H%M%S}.xlsx"`）
3. 全部成功且 `mark_used` → `set_status(..., USED)` 并刷新结果表状态列
4. `OSError` → 中文「导出失败」警告；不改状态

可选：在 `app/export.py` 增加薄编排函数（如 `export_selected_and_mark_used`），把「按勾选写出 + 可选 mark used」收拢一处，便于单测；非必须，主窗口内联亦可，以测试覆盖为准。

## 5. 非目标

- 不改 Excel 列结构、烧写文件名规则
- 不提供自定义 Excel 文件名
- 不在导出路径中选择「文件」——始终是目录
- 不修改旧的其它 feature 的 spec/plan（本功能用本文件 + 对应 plan）

## 6. 测试要点

- 对话框默认：仅 burn、mark used 勾选、路径为 `app_dir()`
- 未选导出类型 / 空路径 → 不 accept
- 仅 burn / 仅 excel / 两者 → 文件落在同一目录；Excel 名匹配 `^\d{14}\.xlsx$`
- mark used：全成功才 `used`；故意让第二步写出失败 → 状态仍 unused
- 主窗口：无选中时导出仍禁用（既有行为）
