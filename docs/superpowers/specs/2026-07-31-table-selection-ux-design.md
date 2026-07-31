# 表格选中样式与主数据添加聚焦设计

日期：2026-07-31  
状态：已确认  
关联：`src/sn_manager/gui/main_window.py`（结果表）；`src/sn_manager/gui/master_data_dialog.py`（主数据表）

## 1. 背景与目标

`QTableWidget` 行选中时，默认选中背景为浅灰，且当前单元格会显示蓝色焦点框。结果表希望更醒目的选中色；主数据希望保留灰底但去掉焦点框，并在点击「添加」后立即进入编辑。

**成功标准**

1. 结果表：选中行背景为浅天蓝 `#87CEFA`，单元格无蓝色焦点框
2. 主数据：点击「添加」后立刻进入新行首单元格编辑态，可直接输入
3. 主数据：选中行背景为浅天蓝 `#87CEFA`，单元格无蓝色焦点框

## 2. 方案

采用 **QSS（选中色）+ `NoFocusDelegate`（去焦点框）**：

- 结果表与主数据表均用 QSS 设选中色 `#87CEFA`（`SKY_BLUE_SELECTION_STYLESHEET`）
- 两表均安装 `NoFocusDelegate`：绘制前清除 `State_HasFocus`。仅靠 `item:focus { border/outline: none }` 在 Windows 上压不住焦点框，黑边会内缩盖住文字
- 「添加」后用 `setCurrentCell` + `editItem` 进入编辑

## 3. 改动点

### 3.1 结果表（`main_window.py`）

在结果表创建/配置后设置样式并安装委托，例如：

```css
QTableWidget {
    outline: none;
}
QTableWidget::item:selected {
    background-color: #87CEFA;
    color: black;
}
```

另：`install_no_focus_delegate(self._table)`（见 `gui/no_focus_delegate.py`）。

行为不变：只读、`SelectRows` + `ExtendedSelection`；单击/多选/全选均使用上述选中色。

### 3.2 主数据表（`master_data_dialog.py`）

在 `_configure_table` 中设置与结果表相同的 `SKY_BLUE_SELECTION_STYLESHEET`，并安装 `NoFocusDelegate`。

### 3.3 添加后自动编辑（`_add_row`）

插入空行并创建各列 `QTableWidgetItem("")` 后：

1. `table.setCurrentCell(row, 0)`
2. `table.editItem(table.item(row, 0))`

其余编辑触发（单击/双击等）沿用 Qt 默认，不做额外改动。

## 4. 非目标

- 不改结果表列、筛选、多选语义
- 不改主数据确认/取消落库逻辑
- 不引入全局主题或共享样式工具模块

## 5. 验证

- 结果表单击、Ctrl/Shift 多选、全选：选中行为 `#87CEFA`，无蓝焦点框
- 主数据选中行：`#87CEFA` 底，无蓝焦点框
- 主数据点「添加」：光标在新行首单元格，可立即键入；确认后仍按原逻辑落库
