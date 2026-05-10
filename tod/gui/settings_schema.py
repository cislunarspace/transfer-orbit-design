"""设置 schema 定义 — 主窗口设置对话框的数据结构。"""

from __future__ import annotations

from tod.commons.plot_helpers import (
    PLOT_FONT_SETTING_KEYS,
    STANDARD_PLOT_FONT_SIZES,
)
from tod.gui.settings_dialog import SettingItem

# Settings schema — each entry defines one setting item.
# Add new SettingItem entries here to extend settings.
SETTINGS_SCHEMA: list[SettingItem] = [
    SettingItem(
        key="theme",
        label="主题 (Theme)",
        type="choice",
        choices=["light", "dark", "system"],
        default="system",
        on_changed=lambda _: None,
    ),
    SettingItem(
        key=PLOT_FONT_SETTING_KEYS["title"],
        label="子图标题字号",
        type="int",
        default=str(int(STANDARD_PLOT_FONT_SIZES["title"])),
        min_value=6,
        max_value=80,
    ),
    SettingItem(
        key=PLOT_FONT_SETTING_KEYS["label"],
        label="坐标轴标签字号",
        type="int",
        default=str(int(STANDARD_PLOT_FONT_SIZES["label"])),
        min_value=6,
        max_value=80,
    ),
    SettingItem(
        key=PLOT_FONT_SETTING_KEYS["tick"],
        label="刻度标签字号",
        type="int",
        default=str(int(STANDARD_PLOT_FONT_SIZES["tick"])),
        min_value=6,
        max_value=80,
    ),
    SettingItem(
        key=PLOT_FONT_SETTING_KEYS["legend"],
        label="图例字号",
        type="int",
        default=str(int(STANDARD_PLOT_FONT_SIZES["legend"])),
        min_value=6,
        max_value=80,
    ),
    SettingItem(
        key=PLOT_FONT_SETTING_KEYS["colorbar"],
        label="色标字号",
        type="int",
        default=str(int(STANDARD_PLOT_FONT_SIZES["colorbar"])),
        min_value=6,
        max_value=80,
    ),
    SettingItem(
        key=PLOT_FONT_SETTING_KEYS["suptitle"],
        label="总标题字号",
        type="int",
        default=str(int(STANDARD_PLOT_FONT_SIZES["suptitle"])),
        min_value=6,
        max_value=80,
    ),
    SettingItem(
        key=PLOT_FONT_SETTING_KEYS["lp_label"],
        label="Lagrange 点标注字号",
        type="int",
        default=str(int(STANDARD_PLOT_FONT_SIZES["lp_label"])),
        min_value=6,
        max_value=80,
    ),
]
