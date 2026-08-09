"""e2m2e 可视化适配层 -- view 与 OrbitVisualizer 之间的薄封装。

职责：
- 构造 CR3BP_System（从 mu 提取，地月质量比）
- 调用 e2m2e OrbitVisualizer 绘制地月标注 / L1-L5 / 2D 投影
- 惯性系（GCRS/J2000）视图：地球原点 marker、月球真实轨迹
- 向 view 暴露纯数组接口（不泄漏 e2m2e 类型）

架构：src/view/ 不直接 import e2m2e（硬规则），此模块是唯一桥接点。
e2m2e 延迟 import，保证本模块被 import 时不触发 e2m2e 加载。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np


def build_cr3bp_system(mu: float) -> Any:
    """构造 e2m2e CR3BP_System（地月系统，主天体 Earth，次天体 Moon）。"""
    from e2m2e.algorithm.dynamics import CR3BP_System

    return CR3BP_System(mu=mu, primary="Earth", secondary="Moon")


def draw_primary_bodies(
    ax, mu: float, *, is_3d: bool = True, plane: tuple[int, int] | None = None
) -> None:
    """在 ax 上绘制地球/月球位置标注。

    Args:
        ax: 目标 matplotlib Axes。
        mu: CR3BP 质量比。地球在 (-mu,0,0)，月球在 (1-mu,0,0)。
        is_3d: 是否在 3D 坐标系绘制（False = 2D 投影平面）。
        plane: 2D 投影平面的轴下标。None 或 (0,1) 时委托 e2m2e（XY 投影，
            其 2D 实现恒用 (x,y) 正好匹配并保留 PNG 图标）；XZ/YZ 投影
            由本函数按平面自绘——e2m2e 2D 无视投影平面，会把天体画进
            错误的轴（如 YZ 下本应重叠于原点的地月被画到 y=±μ）。
    """
    from e2m2e.tools.viz import OrbitVisualizer

    system = build_cr3bp_system(mu)
    if is_3d or plane is None or plane == (0, 1):
        OrbitVisualizer(system).plot_primary_bodies(ax=ax, is_3d=is_3d)
        return
    for name, xpos, color in (("Earth", -mu, "tab:blue"), ("Moon", 1 - mu, "tab:gray")):
        coord3d = (xpos, 0.0, 0.0)
        px, py = coord3d[plane[0]], coord3d[plane[1]]
        ax.scatter(px, py, color=color, s=60, zorder=5)
        ax.annotate(name, (px, py), xytext=(5, 5), textcoords="offset points", fontsize=9)


def draw_libration_points(
    ax, mu: float, *, is_3d: bool = True, plane: tuple[int, int] | None = None
) -> None:
    """在 ax 上绘制 L1-L5 拉格朗日点标注。

    Args:
        ax: 目标 matplotlib Axes。
        mu: CR3BP 质量比。
        is_3d: 是否在 3D 坐标系绘制（False = 2D 投影平面）。
        plane: 2D 投影平面的轴下标。None 或 (0,1) 委托 e2m2e；XZ/YZ 自绘
            （理由同 draw_primary_bodies：e2m2e 2D 无视投影平面）。
    """
    from e2m2e.algorithm.dynamics import LibrationPoint
    from e2m2e.tools.viz import OrbitVisualizer

    system = build_cr3bp_system(mu)
    if is_3d or plane is None or plane == (0, 1):
        OrbitVisualizer(system).plot_libration_points(ax=ax, show_labels=True, is_3d=is_3d)
        return
    if not system.has_L_points:
        system.compute_libration_points()
    labels = ("L1", "L2", "L3", "L4", "L5")
    for i, lp in enumerate(LibrationPoint):
        coord = system.L_points[lp]
        px, py = coord[plane[0]], coord[plane[1]]
        ax.scatter(px, py, color="black", marker="+", s=50, zorder=5)
        ax.annotate(labels[i], (px, py), xytext=(5, 5), textcoords="offset points", fontsize=8)


def draw_earth_origin_marker(
    ax, *, is_3d: bool = True, plane: tuple[int, int] | None = None
) -> None:
    """惯性系视图：在地球原点（GCRS/J2000 原点）画 marker。

    惯性系以地球为原点，地球位置固定在 (0,0,0)。

    Args:
        ax: 目标 matplotlib Axes。
        is_3d: 是否在 3D 坐标系绘制。
        plane: 2D 投影平面的轴下标（is_3d=False 时使用）。
    """
    if is_3d:
        ax.plot([0], [0], [0], "o", color="tab:blue", markersize=8, label="Earth")
    else:
        ax.plot([0], [0], "o", color="tab:blue", markersize=8, label="Earth")


def draw_moon_gcrs_trajectory(
    ax,
    times_et: np.ndarray,
    *,
    kernel_dir: str | None = None,
    is_3d: bool = True,
    plane: tuple[int, int] | None = None,
) -> bool:
    """惯性系视图：按 times_et 用 SPICE 查月球 GCRS（J2000）位置相对地球，画轨迹线。

    月球轨迹与轨道 ``position_km`` 同坐标系（均 GCRS/J2000，km，Earth-relative），
    故两曲线在同一画布上可直接比较。

    Args:
        ax: 目标 matplotlib Axes。
        times_et: ET 秒数组（J2000 TDB），形状 (n,)。
        kernel_dir: SPICE 内核目录（含 de440s.bsp）。None 时调 detect_kernel_dir()。
        is_3d: 是否在 3D 坐标系绘制。
        plane: 2D 投影平面的轴下标。

    Returns:
        True 画出月球轨迹；False 因内核缺失/查询失败而跳过（调用方降级）。
    """
    import numpy as np
    from e2m2e.data.kernels.manager import SPICEManager

    from src.commons.paths import detect_kernel_dir

    kd = kernel_dir or detect_kernel_dir()
    if not kd:
        return False
    mgr = SPICEManager()
    try:
        kernel_path = mgr.find_ephemeris_kernel(kd)
        mgr.load_kernel(kernel_path)
    except FileNotFoundError:
        return False

    try:
        moon_pos = np.array(
            [mgr.get_body_position("MOON", float(et), "J2000", "EARTH") for et in times_et]
        )
    except Exception:  # noqa: BLE001 -- SPICE 查询失败时降级，不阻塞轨道线渲染
        return False

    if is_3d:
        ax.plot(
            moon_pos[:, 0],
            moon_pos[:, 1],
            moon_pos[:, 2],
            linewidth=0.8,
            color="gray",
            linestyle="--",
            label="Moon",
        )
    else:
        if plane is None:
            plane = (0, 1)
        ax.plot(
            moon_pos[:, plane[0]],
            moon_pos[:, plane[1]],
            linewidth=0.8,
            color="gray",
            linestyle="--",
            label="Moon",
        )
    return True


def et_to_utc_label(et: float) -> str:
    """把 ET 秒（J2000 TDB）转成 UTC 时间字符串，用于 GIF 帧时间戳标注。

    优先用 SPICE 闰秒换算（et2utc）；内核未加载/缺失时回退到 J2000 历元
    固定偏移近似（ET≈UTC+64.184s，忽略闰秒跳变，误差 <1s，仅作降级标注）。
    两条路径统一追加 ``" UTC"`` 后缀，便于帧标注可读。
    """
    from datetime import UTC, datetime, timedelta

    try:
        from e2m2e.data.kernels.manager import SPICEManager

        iso = SPICEManager().et_to_utc(float(et))
        return f"{iso} UTC"
    except Exception:  # noqa: BLE001 -- SPICE 不可用时降级为近似
        pass
    # J2000 历元（ET=0）的 UTC 近似时刻
    epoch = datetime(2000, 1, 1, 11, 58, 56, tzinfo=UTC)
    approx = epoch + timedelta(seconds=float(et))
    return f"{approx.strftime('%Y-%m-%dT%H:%M:%S')} UTC"
