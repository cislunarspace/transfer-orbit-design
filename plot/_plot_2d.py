"""2D 渲染辅助函数。"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from src.commons.viz.family import FamilyPlotter


def _project_2d(xyz: Sequence[float] | np.ndarray, plane: str) -> tuple[float, float]:
    """将 3D 坐标投影到指定平面。"""
    if plane == "yz":
        return (xyz[1], xyz[2])
    elif plane == "xy":
        return (xyz[0], xyz[1])
    else:  # xz
        return (xyz[0], xyz[2])


def _plot_bodies_and_libration(
    ax,
    plotter: FamilyPlotter,
    plane: str,
) -> None:
    """在 2D 坐标轴上绘制天体和 libration 点（支持任意投影平面）。"""
    plane_lower = plane.lower()

    # xy 平面：e2m2e helper 原生支持
    if plane_lower == "xy":
        plotter.plot_primary_bodies(ax=ax)
        plotter.plot_libration_points(ax=ax)
        return

    # xz / yz 平面：手动投影坐标
    mu = plotter.mu
    if mu is None:
        return

    # 天体位置（旋转坐标系）
    bodies = [
        ((-mu, 0.0, 0.0), "#2E86AB", "Earth", plotter.primary_body_size),
        ((1.0 - mu, 0.0, 0.0), "#95A5A6", "Moon", plotter.secondary_body_size),
    ]
    for pos_3d, color, name, size in bodies:
        h, v = _project_2d(pos_3d, plane_lower)
        ax.scatter(
            h, v, color=color, s=size, edgecolors="black", linewidth=1, zorder=10, label=name
        )

    # Libration 点
    system = plotter.system
    if system is not None and hasattr(system, "has_L_points"):
        if not system.has_L_points:
            system.compute_libration_points()
        if system.L_points is not None:
            from e2m2e.algorithm.dynamics import LibrationPoint

            for i, lp in enumerate(LibrationPoint):
                coord = system.L_points[lp]
                h, v = _project_2d(coord, plane_lower)
                color = plotter.libration_point_colors[i]
                marker = plotter.libration_point_markers[i]
                size = plotter.libration_point_sizes[i]
                label_text = plotter.libration_point_labels[i]
                ax.scatter(h, v, color=color, marker=marker, s=size, zorder=5)
                ax.annotate(
                    label_text,
                    (h, v),
                    textcoords="offset points",
                    xytext=(5, 5),
                    fontsize=8,
                )
