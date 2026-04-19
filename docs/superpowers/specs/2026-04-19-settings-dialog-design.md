# 设置对话框设计

## 概述

为 GUI 添加设置对话框，允许用户手动选择主题样式（暗色/浅色/跟随系统），并预留后续添加更多设置项的代码扩展接口。

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 设置形式 | 独立对话框 | 非侵入式，不影响主界面布局 |
| 持久化 | gui_defaults.json | 复用现有机制，无需新增文件 |
| 扩展方式 | 代码驱动 | 用户明确不需要声明式配置 |

## 数据结构

`SETTINGS_SCHEMA` 列表定义所有设置项，每个设置项包含：

```python
@dataclass
class SettingItem:
    key: str           # 唯一标识，如 "theme"
    label: str         # 界面显示标签，如 "主题"
    type: str          # "choice" | "bool"
    choices: list[str] | None  # 仅 choice 类型，如 ["light", "dark", "system"]
    default: str      # 默认值
    on_changed: Callable[[str], None] | None  # 值变化回调
```

**初始设置项：**
- `theme`: 主题模式，choice，[light, dark, system]，default=system

## 文件结构

```
scripts/gui/
  main_window.py       # 添加 _build_settings_dialog()、_current_theme_mode
  settings_dialog.py   # 新文件：SettingsDialog 类
```

## 组件设计

### SettingsDialog

- **初始化**：从 `gui_defaults.json` 读取当前值，未设置则用默认值
- **UI**：垂直布局，每项设置一行（QLabel + QComboBox 或 QCheckBox）
- **保存**：点击确定时，写入 `gui_defaults.json` 并调用 `on_changed` 回调
- **信号**：无 Qt 信号，回调直接触发 `MainWindow` 的主题更新

### 主题检测逻辑

原 `_is_dark_mode()` 函数逻辑不变，但调用点改为从 `MainWindow._current_theme_mode` 读取用户设置，而非自动检测：

```python
def _resolve_theme() -> str:
    """返回当前应使用的主题：light / dark"""
    mode = getattr(MainWindow, '_current_theme_mode', 'system')
    if mode == 'system':
        return 'dark' if _is_system_dark() else 'light'
    return mode
```

`MainWindow._current_theme_mode` 在初始化时从 `gui_defaults.json` 加载。

## 交互流程

1. 用户点击 Toolbar 的 `Settings` 按钮
2. 弹出 `SettingsDialog`，显示当前设置值
3. 用户修改后点击确定 → 保存到 `gui_defaults.json` → 触发 `on_changed` 回调 → 刷新界面颜色
4. 主题变化后需重建左侧面板和参数面板的颜色（调用 `_rebuild_left_panel` 和 `_rebuild_params_panel`）

## 实现步骤

1. 在 `main_window.py` 添加 `SETTINGS_SCHEMA` 和 `SettingItem`
2. 创建 `settings_dialog.py`，实现 `SettingsDialog` 类
3. 在 `MainWindow.__init__` 中加载 `theme` 设置
4. 在 Toolbar 添加 `Settings` 按钮
5. 实现 `on_theme_changed` 回调，重建相关面板
6. 将 `_is_dark_mode()` 替换为 `_resolve_theme()`

## 扩展方式

后续添加新设置项：
1. 在 `SETTINGS_SCHEMA` 中添加新的 `SettingItem`
2. 在 `on_changed` 中处理新设置的生效逻辑

无需修改 `SettingsDialog` 的渲染逻辑（已支持任意数量的 choice/bool 项）。
