# Settings Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a settings dialog allowing users to manually choose theme (light/dark/system), with code-driven extensibility for future settings.

**Architecture:** Add `SettingsDialog` class and `SettingItem` dataclass. Replace direct `_is_dark_mode()` calls with a `_resolve_theme()` function that respects user preference from settings.

**Tech Stack:** PyQt6, dataclasses, existing `gui_defaults.json` persistence

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
|  | Create | `SettingItem` dataclass, `SettingsDialog` class |
|  | Modify | `SETTINGS_SCHEMA`, `_current_theme_mode`, `_resolve_theme()`, toolbar button, callbacks |

---

## Task 1: Create settings_dialog.py

**Files:**
- Create: 

- [ ] **Step 1: Write the file**

```python
"""设置对话框 — 动态渲染 SETTINGS_SCHEMA 中的所有设置项。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout


@dataclass
class SettingItem:
    """单个设置项的定义。"""
    key: str
    label: str
    type: str  # "choice" | "bool"
    choices: list[str] | None = None  # 仅 choice 类型
    default: str = ""
    on_changed: Callable[[str], None] = None


class SettingsDialog(QDialog):
    def __init__(self, settings: dict[str, str], schema: list[SettingItem], parent=None):
        super().__init__(parent)
        self._settings = settings
        self._schema = schema
        self._controls: dict[str, QComboBox] = {}

        self.setWindowTitle("Settings")
        self.setMinimumWidth(300)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        for item in self._schema:
            label = QLabel(item.label)
            if item.type == "choice":
                combo = QComboBox()
                combo.addItems(item.choices or [])
                current = self._settings.get(item.key, item.default)
                if current in (item.choices or []):
                    combo.setCurrentText(current)
                form.addRow(label, combo)
                self._controls[item.key] = combo
            elif item.type == "bool":
                # 暂不使用 checkbox，统一用 choice
                pass

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        for key, combo in self._controls.items():
            self._settings[key] = combo.currentText()
        self.accept()

    def get_settings(self) -> dict[str, str]:
        return self._settings
```

- [ ] **Step 2: Commit**

```bash
git add scripts/gui/settings_dialog.py
git commit -m "feat(gui): add SettingsDialog class"
```

---

## Task 2: Add SETTINGS_SCHEMA and _current_theme_mode to main_window.py

**Files:**
- Modify: `scripts/gui/main_window.py:42-57`

- [ ] **Step 1: Add SettingItem import and SETTINGS_SCHEMA after FILE_PATH_ROLE**

```python
from scripts.gui.script_registry import SCRIPTS, UNIT_GROUPS, CliParam, ScriptEntry
from scripts.gui.settings_dialog import SettingItem

FILE_PATH_ROLE = Qt.ItemDataRole.UserRole + 1


def _is_system_dark() -> bool:
    """检测系统是否使用暗色模式（仅作辅助函数，不直接使用）。"""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        return False
    palette = app.palette()
    window_color = palette.color(palette.ColorRole.Window)
    luminance = 0.299 * window_color.red() + 0.587 * window_color.green() + 0.114 * window_color.blue()
    return luminance < 128


def _resolve_theme() -> str:
    """返回当前应使用的主题：light / dark。"""
    mode = getattr(MainWindow, '_current_theme_mode', 'system')
    if mode == 'system':
        return 'dark' if _is_system_dark() else 'light'
    return mode


# Settings schema — each entry defines one setting item.
# Add new SettingItem entries here to extend settings.
SETTINGS_SCHEMA: list[SettingItem] = [
    SettingItem(
        key="theme",
        label="主题 (Theme)",
        type="choice",
        choices=["light", "dark", "system"],
        default="system",
        on_changed=None,  # filled in after MainWindow is defined
    ),
]
```

- [ ] **Step 2: Add _current_theme_mode attribute in MainWindow.__init__**

After `self._job_outputs: dict[str, StructuredOutputWidget] = {}` add:

```python
        self._has_jobs = False

        # 从设置加载 theme
        self._current_theme_mode = self._gui_defaults.get("settings", {}).get("theme", "system")
        MainWindow._current_theme_mode = self._current_theme_mode
```

- [ ] **Step 3: Replace all `_is_dark_mode()` calls with `_resolve_theme()` calls**

Replace the 4 occurrences (lines 148, 161, 1243, 1249, 1261):
- `hdr_color = "#aaa" if _is_dark_mode() else "#555"` → `hdr_color = "#aaa" if _resolve_theme() == "dark" else "#555"`
- `grp_color = "#aaa" if _is_dark_mode() else "#555"` → `grp_color = "#aaa" if _resolve_theme() == "dark" else "#555"`
- `text_color = "#ccc" if _is_dark_mode() else "#333"` → `text_color = "#ccc" if _resolve_theme() == "dark" else "#333"`
- `code_color = "#bbb" if _is_dark_mode() else "#444"` (2 places) → `code_color = "#bbb" if _resolve_theme() == "dark" else "#444"`

- [ ] **Step 4: Store left_splitter reference and add Settings button to toolbar**

In `_build_central()`, after creating `left_splitter`, store it:

```python
        self._left_splitter = left_splitter
```

In `_build_toolbar()`, after the Refresh button:

```python
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._on_settings)
        toolbar.addWidget(settings_btn)
```

- [ ] **Step 5: Add _on_settings and _on_theme_changed methods**

Add these methods before `_build_toolbar`:

```python
    def _on_settings(self) -> None:
        from scripts.gui.settings_dialog import SettingsDialog
        current = dict(self._gui_defaults.get("settings", {}))
        dialog = SettingsDialog(current, SETTINGS_SCHEMA, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            if "settings" not in self._gui_defaults:
                self._gui_defaults["settings"] = {}
            self._gui_defaults["settings"].update(settings)
            self._save_gui_defaults()

            if "theme" in settings:
                self._current_theme_mode = settings["theme"]
                MainWindow._current_theme_mode = settings["theme"]
                self._on_theme_changed()

    def _on_theme_changed(self) -> None:
        """主题变化后，重建左侧面板和参数面板的颜色。"""
        # 重建左侧面板
        old_panel = self._left_splitter.widget(0)
        new_left = self._build_left_panel()
        self._left_splitter.replaceWidget(0, new_left)
        old_panel.hide()
        old_panel.deleteLater()

        # 重建参数面板（如果当前有选中脚本）
        if self._current_script is not None:
            self._rebuild_params_panel(self._current_script)
```

- [ ] **Step 6: Commit**

```bash
git add scripts/gui/main_window.py
git commit -m "feat(gui): add Settings dialog and theme selection"
```

---

## Verification

1. Launch GUI: `uv run python -m tod.pipelines.gui.main`
2. Click "Settings" button in toolbar
3. Verify dialog shows theme dropdown with light/dark/system options
4. Change theme and click OK — verify left panel and params panel colors update
5. Restart GUI — verify theme preference persists
