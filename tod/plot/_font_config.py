"""绘图字体常量、CJK 回退与环境变量 plumbing。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

PLOT_FONT_KEYS = (
    "title",
    "label",
    "tick",
    "legend",
    "colorbar",
    "suptitle",
    "lp_label",
)

STANDARD_PLOT_FONT_SIZES: dict[str, float] = {
    "title": 16,
    "label": 14,
    "tick": 13,
    "legend": 8,
    "colorbar": 13,
    "suptitle": 18,
    "lp_label": 16,
}

STANDARD_PLOT_LAYOUT: dict[str, float] = {
    "title_y_offset": -0.12,
    "title_y_offset_3d": -0.08,
    "title_y_offset_dual": -0.18,
    "title_y_offset_subplot": -0.15,
}

PROJECT_DEFAULT_BODY_ICON_SCALE: float = 0.25

BODY_ICON_SCALE_ENV: str = "E2M2E_BODY_ICON_SCALE"

PLOT_FONT_ENV_VARS: dict[str, str] = {
    key: f"PLOT_FONT_{key.upper()}" for key in PLOT_FONT_KEYS
}

PLOT_FONT_SETTING_KEYS: dict[str, str] = {
    key: f"plot_font_{key}" for key in PLOT_FONT_KEYS
}


def _coerce_font_size(value: Any) -> float | None:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return None
    if size <= 0:
        return None
    return size


def get_plot_font_sizes_from_env(
    env: Mapping[str, str] | None = None,
) -> dict[str, float]:
    """读取 GUI/终端通过环境变量传入的绘图字号覆盖值。"""
    source = os.environ if env is None else env
    overrides: dict[str, float] = {}
    for key, env_var in PLOT_FONT_ENV_VARS.items():
        if env_var not in source:
            continue
        size = _coerce_font_size(source[env_var])
        if size is not None:
            overrides[key] = size
    return overrides


def plot_font_env_from_settings(settings: Mapping[str, str]) -> dict[str, str]:
    """将 GUI 持久化设置转换为子进程环境变量。"""
    env: dict[str, str] = {}
    for key, setting_key in PLOT_FONT_SETTING_KEYS.items():
        if setting_key not in settings:
            continue
        size = _coerce_font_size(settings[setting_key])
        if size is not None:
            env[PLOT_FONT_ENV_VARS[key]] = f"{size:g}"
    return env


def body_icon_env_from_settings(settings: Mapping[str, str]) -> dict[str, str]:
    """将 GUI 的 plot_body_icon_scale 设置转换为子进程环境变量。"""
    raw = settings.get("plot_body_icon_scale")
    if not raw:
        return {}
    try:
        value = float(raw)
    except ValueError:
        return {}
    if value <= 0:
        return {}
    return {BODY_ICON_SCALE_ENV: f"{value:g}"}


def apply_cjk_font_fallback() -> None:
    """补充中文字体回退到 matplotlib rcParams。"""
    import matplotlib

    cjk_serif_fonts = [
        "Noto Serif CJK SC",
        "Noto Serif CJK JP",
        "Source Han Serif SC",
        "STSong",
        "SimSun",
        "AR PL UMing CN",
    ]
    cjk_sans_fonts = [
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
        "Noto Sans SC",
        "Source Han Sans SC",
        "Microsoft YaHei",
        "PingFang SC",
        "Hiragino Sans GB",
        "SimHei",
        "WenQuanYi Zen Hei",
    ]
    matplotlib.rcParams["font.serif"] = [
        *cjk_serif_fonts,
        "Times New Roman",
        "DejaVu Serif",
    ]
    matplotlib.rcParams["font.sans-serif"] = [
        *cjk_sans_fonts,
        "DejaVu Sans",
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False
