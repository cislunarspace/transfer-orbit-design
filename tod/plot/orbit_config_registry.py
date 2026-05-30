"""轨道类型自动检测与默认配置注册表。

根据文件名前缀自动推断轨道族类型（Halo / DRO / RO 子类型），
返回对应的 FamilyPlotConfig 默认配置。
"""

from __future__ import annotations

from pathlib import Path

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


def _ro_31_config() -> FamilyPlotConfig:
    return FamilyPlotConfig(
        family_type="3:1 RO",
        default_filename="ro_31_family_placeholder",
        output_subdir="ro",
        plane="xy",
        center_3d=(-0.85, 0, 0),
        radius_3d=0.5,
        elev_3d=0,
        azim_3d=-90,
        show_seed_overlay=True,
        target_period=2 * np.pi,
    )


def _ro_32_config() -> FamilyPlotConfig:
    return FamilyPlotConfig(
        family_type="3:2 RO",
        default_filename="ro_32_family_placeholder",
        output_subdir="ro",
        plane="xy",
        center_3d=(-0.9, 0, 0),
        radius_3d=0.5,
        elev_3d=0,
        azim_3d=-90,
        show_seed_overlay=True,
        target_period=4 * np.pi,
    )


def _aro_config() -> FamilyPlotConfig:
    return FamilyPlotConfig(
        family_type="3:2 ARO",
        default_filename="aro_32_family_placeholder",
        output_subdir="ro",
        plane="xy",
        center_3d=(-0.85, 0, 0.2),
        radius_3d=0.5,
        elev_3d=20,
        azim_3d=-90,
        show_seed_overlay=True,
        target_period=4 * np.pi,
    )


def _rro_config() -> FamilyPlotConfig:
    return FamilyPlotConfig(
        family_type="3:2 RRO",
        default_filename="rro_32_family_placeholder",
        output_subdir="ro",
        plane="xy",
        center_3d=(-0.9, 0, 0.1),
        radius_3d=0.5,
        elev_3d=20,
        azim_3d=-90,
        show_seed_overlay=True,
        target_period=4 * np.pi,
    )


_CONFIG_REGISTRY: list[tuple[str, object]] = [
    ("halo_", _halo_config),
    ("dro_", _dro_config),
    ("ro_31_", _ro_31_config),
    ("ro_32_", _ro_32_config),
    ("aro_", _aro_config),
    ("rro_", _rro_config),
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
