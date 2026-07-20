"""Matplotlib 绘图样式配置与辅助函数。

本模块 orbit-agnostic，集中定义各绘图脚本共用的标准字号、布局、天体图标缩放、
colorbar 样式与轨道采样等配置，供 ``tod.plot`` 下的可视化脚本 import 使用，
本身不可作为脚本运行。
"""

from __future__ import annotations

import os
from collections.abc import Mapping

# 向后兼容重导出：所有符号仍可从 tod.plot.config 导入
from tod.plot._font_config import (
    BODY_ICON_SCALE_ENV,
    PLOT_FONT_ENV_VARS,
    PLOT_FONT_KEYS,
    PLOT_FONT_SETTING_KEYS,
    PROJECT_DEFAULT_BODY_ICON_SCALE,
    STANDARD_PLOT_FONT_SIZES,
    STANDARD_PLOT_LAYOUT,
    _coerce_font_size,
    apply_cjk_font_fallback,
    body_icon_env_from_settings,
    get_plot_font_sizes_from_env,
    plot_font_env_from_settings,
)
from tod.plot._subsample import subsample_indices


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
    apply_cjk_font_fallback()
    return config


def style_colorbar(colorbar, config, label: str | None = None):
    """统一色标标签和刻度字号。"""
    if label is not None:
        colorbar.set_label(label, fontsize=config.colorbar)
    elif colorbar.ax.get_ylabel() or colorbar.ax.get_xlabel():
        colorbar.set_label(colorbar.ax.get_ylabel() or colorbar.ax.get_xlabel(), fontsize=config.colorbar)
    colorbar.ax.tick_params(labelsize=config.colorbar)
    return colorbar


__all__ = [
    "BODY_ICON_SCALE_ENV",
    "PLOT_FONT_ENV_VARS",
    "PLOT_FONT_KEYS",
    "PLOT_FONT_SETTING_KEYS",
    "PROJECT_DEFAULT_BODY_ICON_SCALE",
    "STANDARD_PLOT_FONT_SIZES",
    "STANDARD_PLOT_LAYOUT",
    "apply_cjk_font_fallback",
    "apply_standard_plot_config",
    "body_icon_env_from_settings",
    "get_plot_font_sizes_from_env",
    "get_standard_plot_config",
    "plot_font_env_from_settings",
    "style_colorbar",
    "subsample_indices",
]
