"""config 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.config --help
"""


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

# 项目级天体图标缩放默认值。
# 仅在环境变量 BODY_ICON_SCALE_ENV 未设置时生效；GUI 写入该环境变量后，
# 用户设置优先。这里不直接通过 kwargs 注入到 PlotConfig，否则会覆盖环境变量。
PROJECT_DEFAULT_BODY_ICON_SCALE: float = 0.25

# e2m2e.visualization 未导出此常量，在本地定义以保持功能独立。
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
    """将 GUI 的 plot_body_icon_scale 设置转换为子进程环境变量。

    解析失败或值非正时返回空 dict（让 e2m2e 走自己的默认回退）。
    """
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

    # 仅在用户未通过环境变量指定图标缩放时，才注入项目级默认值（0.25）。
    # 否则项目默认会覆盖用户设置（kwargs 在 from_env 中作为 overrides 优先级最高）。
    if use_env and BODY_ICON_SCALE_ENV not in os.environ:
        kwargs["primary_body_icon_scale"] = PROJECT_DEFAULT_BODY_ICON_SCALE
        kwargs["secondary_body_icon_scale"] = PROJECT_DEFAULT_BODY_ICON_SCALE

    return PlotConfig.from_env(**kwargs)  # pyright: ignore[reportArgumentType]


def apply_standard_plot_config(
    font_sizes: Mapping[str, float] | None = None,
    *,
    use_env: bool = True,
):
    """应用统一 PlotConfig，并补充中文字体回退。"""
    config = get_standard_plot_config(font_sizes, use_env=use_env)
    config.apply_rcparams()

    import matplotlib

    # 关键：matplotlib 的 font.<family> 是"家族选择链"，不是"逐字符回退链"。
    # 一旦命中第一个存在的家族（如 Times New Roman），就用它渲染整串文本；
    # 若该字体不含 CJK 字形，就会出现"豆腐块"乱码。
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
    """统一色标标签和刻度字号。"""
    if label is not None:
        colorbar.set_label(label, fontsize=config.colorbar)
    elif colorbar.ax.get_ylabel() or colorbar.ax.get_xlabel():
        colorbar.set_label(colorbar.ax.get_ylabel() or colorbar.ax.get_xlabel(), fontsize=config.colorbar)
    colorbar.ax.tick_params(labelsize=config.colorbar)
    return colorbar


def subsample_indices(n: int, max_points: int | None, seed: int) -> np.ndarray:
    """对轨道索引进行亚采样（当轨道数超过最大点数时）。
    
    Args:
        n: 轨道总数。
        max_points: 最大采样点数，None 表示不采样。
        seed: 随机种子。
    
    Returns:
        排序后的采样索引数组。
    """
    if max_points is None or n <= max_points:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n, size=max_points, replace=False))
