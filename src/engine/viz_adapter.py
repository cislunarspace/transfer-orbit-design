"""e2m2e 可视化适配层 -- view 与 OrbitVisualizer 之间的薄封装。

职责：
- 构造 CR3BP_System（从 mu 提取，地月质量比）
- 调用 e2m2e OrbitVisualizer 绘制地月标注 / L1-L5 / 2D 投影
- 向 view 暴露纯数组接口（不泄漏 e2m2e 类型）

架构：src/view/ 不直接 import e2m2e（硬规则），此模块是唯一桥接点。
e2m2e 延迟 import，保证本模块被 import 时不触发 e2m2e 加载。
"""

from __future__ import annotations

from typing import Any


def build_cr3bp_system(mu: float) -> Any:
    """构造 e2m2e CR3BP_System（地月系统，主天体 Earth，次天体 Moon）。"""
    from e2m2e.algorithm.dynamics import CR3BP_System

    return CR3BP_System(mu=mu, primary="Earth", secondary="Moon")


def draw_primary_bodies(ax, mu: float, *, is_3d: bool = True) -> None:
    """在 ax 上绘制地球/月球位置标注。

    Args:
        ax: 目标 matplotlib Axes。
        mu: CR3BP 质量比。地球在 (-mu,0,0)，月球在 (1-mu,0,0)。
        is_3d: 是否在 3D 坐标系绘制（False = 2D 投影平面）。
    """
    from e2m2e.tools.viz import OrbitVisualizer

    system = build_cr3bp_system(mu)
    viz = OrbitVisualizer(system)
    viz.plot_primary_bodies(ax=ax, is_3d=is_3d)


def draw_libration_points(ax, mu: float, *, is_3d: bool = True) -> None:
    """在 ax 上绘制 L1-L5 拉格朗日点标注。

    Args:
        ax: 目标 matplotlib Axes。
        mu: CR3BP 质量比。
        is_3d: 是否在 3D 坐标系绘制（False = 2D 投影平面）。
    """
    from e2m2e.tools.viz import OrbitVisualizer

    system = build_cr3bp_system(mu)
    viz = OrbitVisualizer(system)
    viz.plot_libration_points(ax=ax, show_labels=True, is_3d=is_3d)
