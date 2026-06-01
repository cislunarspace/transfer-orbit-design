"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

from tod.plot.config import (
    PLOT_FONT_SETTING_KEYS,
    PROJECT_DEFAULT_BODY_ICON_SCALE,
    STANDARD_PLOT_FONT_SIZES,
)
from tod.gui.settings_dialog import SettingItem

# GUI 设置 key：天体图标缩放系数。值会被 _run_from_tab 写入到环境变量
# E2M2E_BODY_ICON_SCALE 中传给绘图子进程。
BODY_ICON_SCALE_SETTING_KEY = "plot_body_icon_scale"

# 设置模式 — 每个条目定义一个设置项。
# 在此处添加新的 SettingItem 条目以扩展设置。
SETTINGS_SCHEMA: list[SettingItem] = [
    SettingItem(
        key="theme",
        label="主题 (Theme)",
        type="choice",
        choices=["light", "dark", "system"],
        choice_labels=["浅色", "深色", "跟随系统"],
        default="system",
        on_changed=lambda _: None,
    ),
    SettingItem(
        key="language",
        label="语言 (Language)",
        type="choice",
        choices=["zh", "en"],
        choice_labels=["中文", "English"],
        default="zh",
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
    SettingItem(
        key=BODY_ICON_SCALE_SETTING_KEY,
        label="天体图标缩放",
        type="float",
        default=f"{PROJECT_DEFAULT_BODY_ICON_SCALE:g}",
        min_value=0.05,
        max_value=2.0,
        decimals=2,
        step=0.05,
    ),
]
