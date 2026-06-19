"""common 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.transfer.common --help
"""


from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.axes import Axes


def load_search_results(path: Path) -> list[dict]:
    """加载 grid_search 输出的搜索结果 JSON。

    支持两种格式：
    - list[dict]（直接列表）
    - dict 含 "results" key（自动提取 results 字段）
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "results" in data:
        return list(data["results"])
    if not isinstance(data, list):
        raise TypeError(f"期望 list 或含 'results' key 的 dict, 实际 {type(data)}")
    return data


def departure_delta_v_norm(state6: np.ndarray, alpha: float) -> float:
    """计算速度扰动后的 Δv 模：‖v'−v‖（无量纲速度）。

    在位置径向方向保持速度分量不变，切向方向乘以 α。
    """
    pos = np.asarray(state6[:3], dtype=np.float64)
    vel = np.asarray(state6[3:6], dtype=np.float64)
    r_xy = float(np.sqrt(pos[0] ** 2 + pos[1] ** 2))
    if r_xy < 1e-10:
        return float("nan")
    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)
    v_radial_comp = float(np.dot(vel, radial))
    v_tangential_comp = float(np.dot(vel, tangential))
    new_vel = v_radial_comp * radial + alpha * v_tangential_comp * tangential
    return float(np.linalg.norm(new_vel - vel))


def _extract_dv_from_row(r: dict) -> float | None:
    """从搜索结果行中提取 dv_departure 标量。"""
    dv_raw = r.get("dv_departure")
    if dv_raw is not None:
        dv_arr = np.asarray(dv_raw, dtype=np.float64).ravel()
        return float(dv_arr[0]) if dv_arr.size == 1 else float(np.linalg.norm(dv_arr))
    ds = r.get("departure_state")
    alpha = r.get("alpha")
    if ds is not None and alpha is not None:
        return departure_delta_v_norm(np.asarray(ds, dtype=np.float64), float(alpha))
    return None


def feasible_alpha_and_departure_dv(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """提取可行解的 (alphas, dv_departure)。"""
    alphas: list[float] = []
    dvs: list[float] = []
    for r in rows:
        if not r.get("is_feasible"):
            continue
        alpha = r.get("alpha")
        if alpha is None:
            continue
        dv = _extract_dv_from_row(r)
        if dv is not None and np.isfinite(dv):
            alphas.append(float(alpha))
            dvs.append(dv)
    return np.asarray(alphas, dtype=np.float64), np.asarray(dvs, dtype=np.float64)


def _first_feasible_time(r: dict) -> float | None:
    """可行解首次满足约束的时间（TU）。

    优先首次进入相交阈值（issue #238），否则首次最小距离，最后回退到积分全程时间。
    旧 JSON 缺 ``first_*`` 字段时回退到 ``transfer_time``。
    """
    if r.get("intersection_found"):
        tt = r.get("first_intersection_time")
    else:
        tt = r.get("first_min_distance_time")
    if tt is None:
        tt = r.get("transfer_time")
    return None if tt is None else float(tt)


def _arrival_dv_scalar(r: dict) -> float:
    """从行中提取入轨/到达 Δv 标量（无量纲），缺失则为 0。"""
    for key in ("dv_arrival", "dv_insertion"):
        val = r.get(key)
        if val is None:
            continue
        arr = np.asarray(val, dtype=np.float64).ravel()
        if arr.size:
            return float(arr[0])
    return 0.0


def feasible_time_dv_total(
    rows: list[dict],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """提取可行解的 (transfer_times, dv_departure, dv_total)，三者按同一筛选顺序对齐。

    对可行解使用首次进入阈值的时间（见 ``_first_feasible_time``），而非积分全程的
    transfer_time。``dv_total = dv_departure + dv_arrival``，入轨脉冲缺失时退化为
    出发脉冲。
    """
    times: list[float] = []
    dvs: list[float] = []
    totals: list[float] = []
    for r in rows:
        if not r.get("is_feasible"):
            continue
        dv = _extract_dv_from_row(r)
        if dv is None or not np.isfinite(dv):
            continue
        tt = _first_feasible_time(r)
        if tt is None:
            continue
        times.append(tt)
        dvs.append(dv)
        totals.append(dv + _arrival_dv_scalar(r))
    return (
        np.asarray(times, dtype=np.float64),
        np.asarray(dvs, dtype=np.float64),
        np.asarray(totals, dtype=np.float64),
    )


def feasible_transfer_time_and_dv(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """提取可行解的 (transfer_times, dv_departure)。

    对可行解使用首次进入阈值的时间（first_intersection_time 或
    first_min_distance_time），而非积分全程的 transfer_time。
    """
    times, dvs, _ = feasible_time_dv_total(rows)
    return times, dvs


def _dv_total_from_row(r: dict) -> float:
    """计算行的总 Δv（dv_departure + dv_insertion），用于排序。"""
    dv_dep = r.get("dv_departure")
    dv_ins = r.get("dv_insertion")
    if dv_dep is not None and dv_ins is not None:
        return float(dv_dep) + float(dv_ins)
    if dv_dep is not None:
        return float(dv_dep)
    return float("inf")


def select_feasible_indices(
    rows: list[dict],
    idx_arg: str,
    seed: int = 0,
    max_indices: int | None = None,
) -> list[int]:
    """根据 idx_arg 参数选择可行解索引列表。

    支持：
    - 'all': 全部（可子采样）
    - 'best': Δv 最小的 1 个
    - 'best:N': Δv 最小的 N 个
    - 'random': 随机 1 个
    - 整数: 指定索引
    """
    n = len(rows)
    dv_vals = [_dv_total_from_row(r) for r in rows]

    if idx_arg == "all":
        if max_indices is not None and n > max_indices:
            rng = np.random.default_rng(seed)
            chosen = rng.choice(n, size=max_indices, replace=False)
            return sorted(chosen.tolist())
        return list(range(n))
    elif idx_arg.startswith("best"):
        parts = idx_arg.split(":")
        top_n = int(parts[1]) if len(parts) == 2 else 1
        top_n = min(top_n, n)
        sorted_indices = sorted(range(n), key=lambda i: dv_vals[i])
        return sorted_indices[:top_n]
    elif idx_arg == "random":
        rng = np.random.default_rng(seed)
        return [int(rng.integers(0, n))]
    else:
        i = int(idx_arg)
        if i < 0 or i >= n:
            raise ValueError(f"索引 {i} 超出范围（可行解总数={n}）")
        return [i]


def _apply_title(ax: Axes, title: str | None, auto: str) -> None:
    """设置标题：``None`` 用自动标题，``""`` 不设标题，其它字符串原样使用。"""
    if title is None:
        ax.set_title(auto)
    elif title != "":
        ax.set_title(title)


def plot_alpha_delta_v(ax: Axes, alpha: np.ndarray, delta_v: np.ndarray, title_prefix: str, *, config=None) -> None:
    """绘制 α vs Δv_departure 散点图。"""
    from tod.commons.constants import VU

    if len(alpha) == 0:
        ax.text(0.5, 0.5, "无可行解", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"{title_prefix} α vs Δv_departure")
        return
    ax.scatter(alpha, delta_v * VU / 1000, s=6, alpha=0.6, c="steelblue")
    ax.set_xlabel("α")
    ax.set_ylabel("Δv_departure (km/s)")
    ax.set_title(f"{title_prefix} α vs Δv_departure")
    ax.grid(True, alpha=0.3)


def plot_transfer_time_delta_v(
    ax: Axes,
    transfer_time: np.ndarray,
    delta_v: np.ndarray,
    title_prefix: str,
    *,
    config=None,
    scatter_size: float = 6.0,
    scatter_alpha: float = 0.6,
    color: np.ndarray | None = None,
    colorbar_label: str = "转移时间 (天)",
    cmap: str = "viridis",
    title: str | None = None,
) -> None:
    """绘制转移时间 vs Δv 散点图。

    ``color`` 为 None 时按转移时间（天）着色；否则按传入数组（已为显示单位）着色，
    并用 ``colorbar_label`` 标注色标。``title`` 为 None 用自动标题，``""`` 不显示标题。
    """
    from tod.commons.constants import TU, VU
    from tod.plot.config import style_colorbar

    if config is None:
        from tod.plot.config import apply_standard_plot_config
        config = apply_standard_plot_config()

    if len(transfer_time) == 0:
        ax.text(0.5, 0.5, "无可行解", ha="center", va="center", transform=ax.transAxes)
        _apply_title(ax, title, f"{title_prefix} 转移时间 vs Δv_departure")
        return
    c = transfer_time * TU if color is None else np.asarray(color, dtype=np.float64)
    sc = ax.scatter(
        transfer_time * TU,
        delta_v * VU / 1000,
        s=scatter_size,
        alpha=scatter_alpha,
        c=c,
        cmap=cmap,
    )
    style_colorbar(plt.colorbar(sc, ax=ax, label=colorbar_label), config)
    ax.set_xlabel("转移时间 (天)")
    ax.set_ylabel("Δv_departure (km/s)")
    _apply_title(ax, title, f"{title_prefix} 转移时间 vs Δv_departure")
    ax.grid(True, alpha=0.3)


def geo_circle_points(n_pts: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """GEO 球面在 x-y 平面上的投影圆。"""
    from e2m2e.orbits.geo import R_GEO, EARTH_CENTER

    th = np.linspace(0, 2 * np.pi, n_pts)
    return EARTH_CENTER[0] + R_GEO * np.cos(th), R_GEO * np.sin(th)


def plot_celestial_bodies(ax, system, config) -> None:
    """在 3D axes 上绘制地球、月球和平动点。"""
    from tod.commons.constants import MU
    from e2m2e.orbits.geo import EARTH_CENTER

    ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
    ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
    ax.text(EARTH_CENTER[0], EARTH_CENTER[1] + 0.03, 0, "地球", fontsize=config.lp_label, ha="center")
    ax.text(1.0 - MU, 0.03, 0, "月球", fontsize=config.lp_label, ha="center")

    system.compute_libration_points()
    if system.L1 is None or system.L2 is None:
        raise RuntimeError("L1/L2 平动点未计算")
    for lp_name, lp_x in [("L1", system.L1[0]), ("L2", system.L2[0])]:
        ax.scatter(lp_x, 0, 0, color="red", marker="+", s=30, zorder=5)
        ax.text(lp_x, 0.02, 0, lp_name, fontsize=config.lp_label, ha="center", color="red")


def set_equal_aspect_3d(ax, points: np.ndarray) -> None:
    """设置 3D axes 等比例显示。

    对平面轨迹（如 z≈0）特殊处理：z 轴使用小范围固定比例，
    避免纯平面数据因 3D 透视产生虚假的 z 方向振幅感。
    """
    mid = points.mean(axis=0)
    ptp = np.ptp(points, axis=0)
    half = ptp.max() / 2.0 + 0.1
    ax.set_xlim(mid[0] - half, mid[0] + half)
    ax.set_ylim(mid[1] - half, mid[1] + half)

    # 若 z 方向极差远小于 x/y，视为平面轨迹，z 轴使用小范围
    if ptp[2] < 1e-8 and ptp[:2].max() > 1e-8:
        z_half = ptp[:2].max() * 0.05 + 0.05
    else:
        z_half = half
    ax.set_zlim(mid[2] - z_half, mid[2] + z_half)

    ax.set_box_aspect([1, 1, 1])


def build_transfer_dynamics(mu: float | None = None, dt: float | None = None):
    """构建 CR3BP 动力学实例（积分器参数与 grid_search 一致）。"""
    from tod.commons.constants import MU, TU
    from e2m2e.core import CR3BP_System, CR3BP_Dynamics

    _mu = mu if mu is not None else MU
    _dt = dt if dt is not None else (1.0 / (24.0 * TU))

    system = CR3BP_System(mu=_mu, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = _dt
    return system, dynamics


def compute_departure_velocity(state6: np.ndarray, alpha: float) -> np.ndarray:
    """根据切向速度比 α 计算出发速度。

    径向分量不变，切向分量乘以 α。
    """
    pos = np.asarray(state6[:3], dtype=np.float64)
    vel = np.asarray(state6[3:6], dtype=np.float64)
    r_xy = float(np.sqrt(pos[0] ** 2 + pos[1] ** 2))
    if r_xy < 1e-10:
        return vel.copy()
    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)
    v_radial_comp = float(np.dot(vel, radial))
    v_tangential_comp = float(np.dot(vel, tangential))
    return v_radial_comp * radial + alpha * v_tangential_comp * tangential


def reintegrate_transfer(
    dynamics,
    departure_state: np.ndarray,
    alpha: float,
    max_transfer_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    """用指定动力学对象重新积分转移轨道。"""
    new_vel = compute_departure_velocity(departure_state, alpha)
    initial_state = np.concatenate([departure_state[:3], new_vel])
    step = max(0.01, dynamics.max_step)
    n_steps = int(max_transfer_time / step) + 1
    t_eval = np.linspace(0.0, max_transfer_time, n_steps)
    result = dynamics.propagate(
        initial_state=initial_state,
        t_span=(0.0, max_transfer_time),
        t_eval=t_eval,
        with_stm=False,
        with_jacobi=False,
    )
    return result["states"], result["time"]


def plot_single_transfer_orbit_2d(
    departure_orbit,
    transfer_states: np.ndarray,
    departure_state: np.ndarray,
    dv_departure: float,
    dv_insertion: float,
    transfer_time: float,
    alpha: float,
    system,
    config,
    *,
    fig=None,
    ax=None,
    title: str | None = None,
) -> "plt.Axes":
    """在 XY 平面（旋转系）绘制单条转移轨道的论文版图。

    绘制 DRO 轨道、转移轨道、GEO 圆、地球、月球、出发点、到达点。
    """
    import matplotlib.pyplot as plt
    from tod.commons.constants import MU, TU, VU
    from e2m2e.orbits.geo import EARTH_CENTER

    if ax is None:
        fig, ax = plt.subplots(figsize=(8.5 / 2.54, 8.5 / 2.54))

    ax.plot(departure_orbit.states[:, 0], departure_orbit.states[:, 1],
            color="royalblue", lw=0.8, label="DRO")
    ax.plot(transfer_states[:, 0], transfer_states[:, 1],
            color="crimson", lw=1.2, label="转移轨道")

    dep_pos = np.asarray(departure_state, dtype=float)[:3]
    ax.scatter(dep_pos[0], dep_pos[1], color="green", s=40, zorder=5, label="出发点")
    ax.scatter(transfer_states[-1, 0], transfer_states[-1, 1],
               color="orange", s=40, marker="s", zorder=5, label="到达点")

    gx, gy = geo_circle_points()
    ax.plot(gx, gy, color="gray", ls="--", lw=0.8, label="GEO")

    ax.scatter(*EARTH_CENTER[:2], color="blue", s=60, zorder=5)
    ax.scatter(1.0 - MU, 0, color="gray", s=30, zorder=5)
    ax.text(EARTH_CENTER[0], EARTH_CENTER[1] + 0.03, "地球",
            fontsize=config.lp_label, ha="center")
    ax.text(1.0 - MU, 0.03, "月球",
            fontsize=config.lp_label, ha="center")

    system.compute_libration_points()
    for lp_name, lp_x in [("L1", system.L1[0]), ("L2", system.L2[0])]:
        ax.scatter(lp_x, 0, color="red", marker="+", s=30, zorder=5)
        ax.text(lp_x, 0.02, lp_name, fontsize=config.lp_label,
                ha="center", color="red")

    ax.set_xlabel("x (DU)", fontsize=config.label)
    ax.set_ylabel("y (DU)", fontsize=config.label)
    ax.set_aspect("equal", adjustable="datalim")

    if title is None:
        dv1_km = dv_departure * VU / 1000
        dv2_km = dv_insertion * VU / 1000
        title = (
            f"DRO→GEO  α={alpha:.4f}  T={transfer_time:.2f} TU "
            f"({transfer_time * TU:.1f}天)\n"
            f"Δv₁={dv1_km:.4f} km/s  Δv₂={dv2_km:.4f} km/s  "
            f"Δv总={dv1_km + dv2_km:.4f} km/s"
        )
    if title:
        ax.set_title(title, fontsize=config.title)

    ax.legend(fontsize=config.legend, loc="upper left")
    ax.grid(True, alpha=0.3)

    # Equal aspect ratio
    all_pts = np.concatenate([transfer_states[:, :2], departure_orbit.states[:, :2]])
    mid = all_pts.mean(axis=0)
    ptp = np.ptp(all_pts, axis=0)
    half = ptp.max() / 2.0 + 0.1
    ax.set_xlim(mid[0] - half, mid[0] + half)
    ax.set_ylim(mid[1] - half, mid[1] + half)

    return ax
