"""3D 渲染辅助函数。"""

from __future__ import annotations

import argparse

import numpy as np

from src.commons.constants import MU


def _get_center_coordinates(center_type: str, mu: float) -> tuple[float, float, float]:
    if center_type == "moon":
        return (1.0 - mu, 0.0, 0.0)
    elif center_type == "earth":
        return (0.0, 0.0, 0.0)
    elif center_type == "emb":
        return (mu, 0.0, 0.0)
    raise ValueError(f"Unknown center type: {center_type}")


def _resolve_3d_center_radius(
    cfg,
    args: argparse.Namespace,
    bounds: tuple | None,
) -> tuple[tuple[float, float, float], float]:
    """根据用户 --plot-center 选择和配置计算 3D 视图的中心与半径。

    始终使用 args.plot_center 确定视图中心（moon/earth/emb）。
    半径优先使用 dynamic_bounds 计算，回退到配置默认值。

    Args:
        cfg: 轨道族绘图配置
        args: 命令行参数（需包含 plot_center）
        bounds: compute_view_bounds 的返回值，可为 None

    Returns:
        (center, radius) 元组
    """
    center = _get_center_coordinates(args.plot_center, MU)

    if cfg.dynamic_bounds and bounds is not None:
        data_center = bounds[2]
        data_radius = bounds[3]
        offset = float(
            np.sqrt(sum((c - d) ** 2 for c, d in zip(center, data_center, strict=False)))
        )
        radius = offset + data_radius
    elif cfg.radius_3d is not None:
        radius = cfg.radius_3d
    else:
        radius = 1.0

    return center, radius


def compute_view_bounds(
    all_states: np.ndarray,
    plane: str = "xz",
) -> tuple:
    """根据轨道状态数组计算 2D 与 3D 视图的边界参数。

    Args:
        all_states: Nx6 状态数组
        plane: 2D 投影平面 ("xy", "xz", "yz")

    Returns:
        (xlim_2d, ylim_2d, center_3d, radius_3d)
    """
    if all_states.size == 0:
        return (0.8, 1.2), (-0.3, 0.3), (1.0, 0.0, 0.0), 0.4

    x_min, x_max = all_states[:, 0].min(), all_states[:, 0].max()
    y_min, y_max = all_states[:, 1].min(), all_states[:, 1].max()
    z_min, z_max = all_states[:, 2].min(), all_states[:, 2].max()

    # 根据 plane 选择 2D 轴
    plane_lower = plane.lower()
    if plane_lower == "yz":
        h_min, h_max = y_min, y_max
        v_min, v_max = z_min, z_max
    elif plane_lower == "xy":
        h_min, h_max = x_min, x_max
        v_min, v_max = y_min, y_max
    else:  # default: xz
        h_min, h_max = x_min, x_max
        v_min, v_max = z_min, z_max

    h_pad = max(0.05, (h_max - h_min) * 0.1)
    v_pad = max(0.05, (v_max - v_min) * 0.1)

    xlim_2d = (float(h_min - h_pad), float(h_max + h_pad))
    ylim_2d = (float(v_min - v_pad), float(v_max + v_pad))

    center_3d = (
        float((x_min + x_max) / 2),
        float((y_min + y_max) / 2),
        float((z_min + z_max) / 2),
    )
    radius_3d = float(max(x_max - x_min, y_max - y_min, z_max - z_min) / 2 + max(h_pad, v_pad))
    return xlim_2d, ylim_2d, center_3d, radius_3d
