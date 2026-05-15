"""绘图脚本共享工具：字号配置、采样、数据处理等。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import numpy as np


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
    "legend": 14,
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


def get_standard_plot_config(
    font_sizes: Mapping[str, float] | None = None,
    *,
    use_env: bool = True,
):
    """创建与 plot_dro_family.py 一致的 PlotConfig。"""
    from e2m2e.visualization import PlotConfig

    kwargs: dict[str, float] = {}
    kwargs.update(STANDARD_PLOT_FONT_SIZES)
    if use_env:
        kwargs.update(get_plot_font_sizes_from_env())
    if font_sizes:
        for key, value in font_sizes.items():
            if key not in PLOT_FONT_KEYS:
                continue
            size = _coerce_font_size(value)
            if size is not None:
                kwargs[key] = size
    kwargs.update(STANDARD_PLOT_LAYOUT)
    return PlotConfig(**kwargs)


def apply_standard_plot_config(
    font_sizes: Mapping[str, float] | None = None,
    *,
    use_env: bool = True,
):
    """应用统一 PlotConfig，并补充中文字体 fallback。"""
    config = get_standard_plot_config(font_sizes, use_env=use_env)
    config.apply_rcparams()

    import matplotlib

    # 关键：matplotlib 的 font.<family> 是“家族选择链”，不是“逐字符回退链”。
    # 一旦命中第一个存在的家族（如 Times New Roman），就用它渲染整串文本；
    # 若该字体不含 CJK 字形，就会出现“豆腐块”乱码。
    # 因此必须把一个 *包含 CJK 字形的字体* 放在链首。
    # 这里同时覆盖 Linux（Noto/WenQuanYi/文鼎）、Windows（YaHei/SimHei/SimSun）、
    # macOS（PingFang/Hiragino/STSong）常见的真实家族名。
    cjk_serif_fonts = [
        "Noto Serif CJK SC",
        "Noto Serif CJK JP",  # Linux 上 NotoSerifCJK*.ttc 实际暴露的家族名
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
    return config


def style_colorbar(colorbar, config, label: str | None = None):
    """统一 colorbar 标签和刻度字号。"""
    if label is not None:
        colorbar.set_label(label, fontsize=config.colorbar)
    elif colorbar.ax.get_ylabel() or colorbar.ax.get_xlabel():
        colorbar.set_label(colorbar.ax.get_ylabel() or colorbar.ax.get_xlabel(), fontsize=config.colorbar)
    colorbar.ax.tick_params(labelsize=config.colorbar)
    return colorbar


def subsample_indices(n: int, max_points: int | None, seed: int) -> np.ndarray:
    if max_points is None or n <= max_points:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n, size=max_points, replace=False))
