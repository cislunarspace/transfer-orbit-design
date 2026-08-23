"""可视化适配层 -- view 与 OrbitVisualizer 之间的薄封装。

职责：
- 构造 CR3BP_System（从 mu 提取，地月质量比）
- 调用 src.commons.viz 的 OrbitVisualizer 绘制地月标注 / L1-L5 / 2D 投影
  （OrbitVisualizer 收编自 e2m2e 5.6.5 tools/viz，e2m2e 5.6.6 已删除该模块）
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


def body_center_offset(mu: float, center: str) -> tuple[float, float, float]:
    """中心点坐标（无量纲会合系，质心归一）。

    ``"barycenter"`` 为 (0,0,0)；``"moon"`` 为 (1-μ,0,0)；``"L1"``/``"L2"`` 由
    e2m2e 解算平动点坐标。未知 center 回退质心。
    """
    if center == "moon":
        return (1.0 - mu, 0.0, 0.0)
    if center in ("L1", "L2"):
        from e2m2e.algorithm.dynamics import LibrationPoint

        system = build_cr3bp_system(mu)
        if not system.has_L_points:
            system.compute_libration_points()
        coord = system.L_points[LibrationPoint[center]]
        return (float(coord[0]), float(coord[1]), float(coord[2]))
    return (0.0, 0.0, 0.0)


def synodic_to_gcrs_km(pos, theta, mu: float) -> Any:
    """会合系（质心归一，无量纲）→ GCRS 惯性系 km。

    会合系角速度归一为 1，旋转角 θ(t) = t（无量纲时间；物理秒下
    θ = t_sec / TU_sec）。转换式：``r_gcrs = R(θ)·(r_syn + (μ,0,0))·DU``
    （地球在原点）。用于无星历的纯 CR3BP 产物（轨道族/旧初猜）在惯性系
    下的近似视图，历元对齐取 θ(t=0)=0。
    """
    import numpy as np

    from src.commons.constants import DU

    arr = np.asarray(pos)[:, :3]
    th = np.asarray(theta)
    c, s = np.cos(th), np.sin(th)
    x = arr[:, 0] * c - arr[:, 1] * s
    y = arr[:, 0] * s + arr[:, 1] * c
    z = arr[:, 2]
    return np.column_stack([(x + mu) * DU, y * DU, z * DU])


def approx_moon_gcrs_km(theta) -> Any:
    """近似惯性系视图的月球 GCRS 位置：R(θ)·(1,0,0)·DU（正圆轨道）。

    与 :func:`synodic_to_gcrs_km` 的月球特例一致，供无星历的纯 CR3BP 产物
    （轨道族/旧初猜）在惯性系视图下绘制月球轨迹与月球中心平移。
    """
    import numpy as np

    from src.commons.constants import DU

    th = np.asarray(theta)
    return np.column_stack([np.cos(th), np.sin(th), np.zeros_like(th)]) * DU


def draw_primary_bodies(
    ax,
    mu: float,
    *,
    is_3d: bool = True,
    plane: tuple[int, int] | None = None,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    earth_size: float = 160.0,
    moon_size: float = 90.0,
    fontsize: float = 10.0,
) -> None:
    """在 ax 上绘制地球/月球位置标注（自绘，支持中心平移与大小配置）。

    地球在 (-μ,0,0)，月球在 (1-μ,0,0)（质心归一会合系）；绘制时整体减去
    ``center``，使所选中心点成为坐标原点（如月球中心/L1/L2 中心视图）。
    ``earth_size``/``moon_size`` 为 2D scatter 面积（3D markersize 取其平方根）。
    """
    if plane is None:
        plane = (0, 1)
    cx, cy, cz = center
    for name, xpos, color, edge, size in (
        ("Earth", -mu, "#2E86AB", "#1A5276", earth_size),
        ("Moon", 1.0 - mu, "#95A5A6", "#566573", moon_size),
    ):
        x, y, z = xpos - cx, -cy, -cz
        if is_3d:
            ax.plot(
                [x],
                [y],
                [z],
                "o",
                color=color,
                markersize=size**0.5,
                markeredgecolor="black",
                markeredgewidth=0.8,
                label=name,
            )
        else:
            px, py = (x, y, z)[plane[0]], (x, y, z)[plane[1]]
            ax.scatter(px, py, color=color, s=size, edgecolors=edge, linewidth=1.2, zorder=10)
            ax.annotate(
                name, (px, py), xytext=(6, 6), textcoords="offset points", fontsize=fontsize
            )


def draw_libration_points(
    ax,
    mu: float,
    *,
    is_3d: bool = True,
    plane: tuple[int, int] | None = None,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    color: str = "#d62728",
    size: float = 80.0,
    fontsize: float = 10.0,
) -> None:
    """在 ax 上绘制 L1-L5 拉格朗日点标注（自绘，支持中心平移与样式配置）。"""
    from e2m2e.algorithm.dynamics import LibrationPoint

    if plane is None:
        plane = (0, 1)
    system = build_cr3bp_system(mu)
    if not system.has_L_points:
        system.compute_libration_points()
    cx, cy, cz = center
    labels = ("L1", "L2", "L3", "L4", "L5")
    for i, lp in enumerate(LibrationPoint):
        coord = system.L_points[lp]
        x, y, z = coord[0] - cx, coord[1] - cy, coord[2] - cz
        if is_3d:
            ax.plot([x], [y], [z], marker="^", color=color, markersize=size**0.5, linestyle="None")
            ax.text(x, y, z + 0.02, labels[i], fontsize=fontsize, ha="center")
        else:
            px, py = (x, y, z)[plane[0]], (x, y, z)[plane[1]]
            ax.scatter(px, py, color=color, marker="^", s=size, zorder=5)
            ax.annotate(
                labels[i], (px, py), xytext=(5, 5), textcoords="offset points", fontsize=fontsize
            )


def draw_earth_origin_marker(
    ax,
    *,
    is_3d: bool = True,
    plane: tuple[int, int] | None = None,
    earth_size: float = 160.0,
    fontsize: float = 10.0,
) -> None:
    """惯性系视图：在地球原点（GCRS/J2000 原点）画 marker。

    惯性系以地球为原点，地球位置固定在 (0,0,0)。样式与会合系地月标注
    一致（深蓝圆 + 黑描边；2D 带标签），大小/字号可由图表设置控制。
    """
    if is_3d:
        ax.plot(
            [0],
            [0],
            [0],
            "o",
            color="#2E86AB",
            markersize=earth_size**0.5,
            markeredgecolor="black",
            markeredgewidth=0.8,
            label="Earth",
        )
    else:
        if plane is None:
            plane = (0, 1)
        ax.scatter(
            0, 0, color="#2E86AB", s=earth_size, edgecolors="#1A5276", linewidth=1.2, zorder=10
        )
        ax.annotate("Earth", (0, 0), xytext=(6, 6), textcoords="offset points", fontsize=fontsize)


def moon_position_gcrs(
    times_et: np.ndarray,
    *,
    kernel_dir: str | None = None,
) -> Any:
    """SPICE 查询月球 GCRS（J2000，Earth-relative）位置，shape (n,3) km。

    内核缺失/查询失败返回 None（调用方降级）。
    """
    import numpy as np
    from e2m2e.data.kernels.manager import SPICEManager

    from src.commons.paths import detect_kernel_dir

    kd = kernel_dir or detect_kernel_dir()
    if not kd:
        return None
    mgr = SPICEManager()
    try:
        kernel_path = mgr.find_ephemeris_kernel(kd)
        mgr.load_kernel(kernel_path)
    except FileNotFoundError:
        return None

    try:
        moon_pos = np.array(
            [mgr.get_body_position("MOON", float(et), "J2000", "EARTH") for et in times_et]
        )
    except Exception:  # noqa: BLE001 -- SPICE 查询失败时降级，不阻塞轨道线渲染
        return None
    return moon_pos


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
    moon_pos = moon_position_gcrs(times_et, kernel_dir=kernel_dir)
    if moon_pos is None:
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
