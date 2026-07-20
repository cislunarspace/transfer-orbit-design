"""轨道类型自动检测与默认配置注册表。

根据文件名前缀自动推断轨道族类型（Halo / DRO / Resonant），
返回对应的 FamilyPlotConfig 默认配置。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from tod.plot.family_plot_orchestrator import FamilyPlotConfig

def _halo_config() -> FamilyPlotConfig:
    return FamilyPlotConfig(
        family_type="Halo",
        default_filename="halo_L1_N_family_placeholder",
        output_subdir="halo",
        plane="xz",
        dynamic_bounds=True,
        libration_point_sizes=[20, 20, 20, 20, 20],
    )

def _dro_config() -> FamilyPlotConfig:
    return FamilyPlotConfig(
        family_type="DRO",
        default_filename="dro_31_family_placeholder",
        output_subdir="dro",
        plane="xy",
        radius_3d=1.5,
        supports_center_choice=True,
        step=5,
    )

_RATIO_PLOT_OVERRIDES: dict[str, dict[str, object]] = {
    "3:1": {"center_3d": (-0.85, 0, 0), "target_period": 2 * np.pi},
    "3:2": {"center_3d": (-0.9, 0, 0), "target_period": 4 * np.pi},
}

def _resonant_config(ratio: str) -> FamilyPlotConfig:
    """构建 Resonant 族绘图配置，按共振比应用差异参数。"""
    overrides = _RATIO_PLOT_OVERRIDES[ratio]
    ratio_tag = ratio.replace(":", "")
    return FamilyPlotConfig(
        family_type="Resonant",
        ratio=ratio,
        default_filename=f"resonant_{ratio_tag}_family_placeholder",
        output_subdir="ro",
        plane="xy",
        radius_3d=0.5,
        elev_3d=0,
        azim_3d=-90,
        show_seed_overlay=True,
        **overrides,
    )

_CONFIG_REGISTRY: list[tuple[str, Callable[[], FamilyPlotConfig]]] = [
    ("halo_", _halo_config),
    ("dro_", _dro_config),
    ("ro_31_", lambda: _resonant_config("3:1")),
    ("ro_32_", lambda: _resonant_config("3:2")),
    ("resonant_31_", lambda: _resonant_config("3:1")),
    ("resonant_32_", lambda: _resonant_config("3:2")),
]

FALLBACK_CONFIG = FamilyPlotConfig(
    family_type="Orbit",
    default_filename="orbit_placeholder",
    output_subdir="plot",
    plane="xy",
    dynamic_bounds=True,
    step=5,
)

def detect_orbit_config(file_path: Path) -> FamilyPlotConfig:
    """根据文件名自动检测轨道族类型并返回对应的默认配置。

    Args:
        file_path: 轨道文件路径

    Returns:
        匹配的 FamilyPlotConfig，未匹配时返回通用回退配置
    """
    stem = file_path.stem.lower()
    for prefix, factory in _CONFIG_REGISTRY:
        if stem.startswith(prefix):
            return factory()
    return FALLBACK_CONFIG
