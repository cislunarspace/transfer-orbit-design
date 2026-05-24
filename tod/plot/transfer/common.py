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


def feasible_transfer_time_and_dv(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """提取可行解的 (transfer_times, dv_departure)。"""
    times: list[float] = []
    dvs: list[float] = []
    for r in rows:
        if not r.get("is_feasible"):
            continue
        dv = _extract_dv_from_row(r)
        if dv is None or not np.isfinite(dv):
            continue
        tt = r.get("transfer_time")
        if tt is None:
            continue
        times.append(float(tt))
        dvs.append(dv)
    return np.asarray(times, dtype=np.float64), np.asarray(dvs, dtype=np.float64)


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
    ax: Axes, transfer_time: np.ndarray, delta_v: np.ndarray, title_prefix: str, *, config=None
) -> None:
    """绘制转移时间 vs Δv 散点图。"""
    from tod.commons.constants import TU, VU
    from tod.plot.config import style_colorbar

    if config is None:
        from tod.plot.config import apply_standard_plot_config
        config = apply_standard_plot_config()

    if len(transfer_time) == 0:
        ax.text(0.5, 0.5, "无可行解", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"{title_prefix} 转移时间 vs Δv_departure")
        return
    sc = ax.scatter(transfer_time * TU, delta_v * VU / 1000, s=6, alpha=0.6,
                    c=transfer_time * TU, cmap="viridis")
    style_colorbar(plt.colorbar(sc, ax=ax, label="转移时间 (天)"), config)
    ax.set_xlabel("转移时间 (天)")
    ax.set_ylabel("Δv_departure (km/s)")
    ax.set_title(f"{title_prefix} 转移时间 vs Δv_departure")
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
    """设置 3D axes 等比例显示。"""
    mid = points.mean(axis=0)
    half = np.ptp(points, axis=0).max() / 2.0 + 0.1
    ax.set_xlim(mid[0] - half, mid[0] + half)
    ax.set_ylim(mid[1] - half, mid[1] + half)
    ax.set_zlim(mid[2] - half, mid[2] + half)
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
