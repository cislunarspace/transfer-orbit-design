"""
可视化 grid_search_dro_to_geo 输出的搜索结果 JSON：可行解的 α–Δv 散点图、转移时间–Δv 散点图与转移轨道示意图。

在下方 ``RESULTS_JSON`` 中指定要绘制的 grid_search_dro_to_geo 输出 JSON（相对仓库根目录或绝对路径均可）。

Δv 优先使用 JSON 中的 dv_departure，否则由 departure_state 与 α 按搜索阶段速度扰动模型计算。

转移轨道示意图通过重新积分转移轨迹（从 departure_state 出发，以 α 扰动的速度），
叠加绘制 DRO 出发轨道与 GEO 球面，直观展示转移路径。

用法:
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo              # 仅 α–Δv 散点图
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --time-dv   # 转移时间–Δv 散点图
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit      # 转移轨道 3D 示意图
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --save output/transfer/figures/search_geo_orbit.png
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx 0        # 绘制第 idx 个可行解
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx best      # 绘制 Δv 最小的可行解
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx random --seed 42  # 随机一个可行解
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx all        # 绘制全部可行解（子采样受 --max-points 控制）
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx all --max-points 100  # 最多绘制 100 条
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx best:10      # 绘制 Δv 最小的 10 条轨道
    python -m tod.pipelines.transfer.dro_to_geo.plot_search_results_dro_to_geo --interactive           # 交互式逐条浏览（按转移时间排序）
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import matplotlib

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tod.commons.plot_helpers import apply_standard_plot_config, style_colorbar, subsample_indices

PLOT_CONFIG = apply_standard_plot_config()

import e2m2e
from e2m2e.core import CR3BP_System, Orbit
from e2m2e.transfer import TransferSearch, load_orbit_from_json

from tod.commons.common import MU, DU, TU, VU, safe_resolve_within
from tod.commons.geo import R_GEO, V_CIRCULAR_GEO, EARTH_CENTER

# =============================================================================
# 数据文件：grid_search_dro_to_geo 输出的 JSON
# =============================================================================
RESULTS_JSON = (
    project_root
    / "output/transfer/search_dro_geo_200-100-0.5-2.5-22.9985_3858323266.json"
)

# 轨道数据文件（用于转移轨道积分和绘图）
DRO_FILE = project_root / "output/dro/dro_31_3857693511.json"


def departure_delta_v_norm(state6: np.ndarray, alpha: float) -> float:
    """与 e2m2e TransferSearch._compute_departure_velocity 一致，返回 ‖v'−v‖（无量纲速度）。"""
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


def feasible_alpha_and_departure_dv(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """仅可行解；优先使用 JSON 中的 dv_departure（标量），否则由 departure_state 与 alpha 计算。"""
    alphas: list[float] = []
    dvs: list[float] = []
    for r in rows:
        if not r.get("is_feasible"):
            continue
        alpha = r.get("alpha")
        if alpha is None:
            continue
        dv_raw = r.get("dv_departure")
        if dv_raw is not None:
            dv_arr = np.asarray(dv_raw, dtype=np.float64).ravel()
            dv = float(dv_arr[0]) if dv_arr.size == 1 else float(np.linalg.norm(dv_arr))
        else:
            ds = r.get("departure_state")
            if ds is None:
                continue
            dv = departure_delta_v_norm(np.asarray(ds, dtype=np.float64), float(alpha))
        if np.isfinite(dv):
            alphas.append(float(alpha))
            dvs.append(dv)
    return np.asarray(alphas, dtype=np.float64), np.asarray(dvs, dtype=np.float64)


def load_search_results(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)




def compute_actual_transfer_time(r: dict, dt: float = 1.0 / (24.0 * TU)) -> float:
    """
    计算实际转移时间。

    grid_search_dro_to_geo 输出的 transfer_time 已经是到达 GEO 球面的实际转移时间，
    不需要额外计算。这里直接使用 transfer_time。
    """
    transfer_time = r.get("transfer_time")
    if transfer_time is None:
        return float("nan")
    return float(transfer_time)


def feasible_transfer_time_and_dv(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """仅可行解；返回 (transfer_times, dv_departure)。"""
    times: list[float] = []
    dvs: list[float] = []
    for r in rows:
        if not r.get("is_feasible"):
            continue
        dv_raw = r.get("dv_departure")
        if dv_raw is not None:
            dv_arr = np.asarray(dv_raw, dtype=np.float64).ravel()
            dv = float(dv_arr[0]) if dv_arr.size == 1 else float(np.linalg.norm(dv_arr))
        else:
            ds = r.get("departure_state")
            alpha = r.get("alpha")
            if ds is None or alpha is None:
                continue
            dv = departure_delta_v_norm(np.asarray(ds, dtype=np.float64), float(alpha))
        if np.isfinite(dv):
            actual_time = compute_actual_transfer_time(r)
            if np.isfinite(actual_time):
                times.append(actual_time)
                dvs.append(dv)
    return np.asarray(times, dtype=np.float64), np.asarray(dvs, dtype=np.float64)


def plot_alpha_delta_v(
    ax: Axes,
    alpha: np.ndarray,
    delta_v: np.ndarray,
) -> None:
    if len(alpha) == 0:
        ax.text(0.5, 0.5, "无可行解", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("DRO→GEO: α vs Δv_departure")
        return
    ax.scatter(alpha, delta_v * VU / 1000, s=6, alpha=0.6, c="steelblue")
    ax.set_xlabel("α")
    ax.set_ylabel("Δv_departure (km/s)")
    ax.set_title("DRO→GEO: α vs Δv_departure")
    ax.grid(True, alpha=0.3)


def plot_transfer_time_delta_v(
    ax: Axes,
    transfer_time: np.ndarray,
    delta_v: np.ndarray,
) -> None:
    """绘制转移时间 vs Δv 散点图。"""
    if len(transfer_time) == 0:
        ax.text(0.5, 0.5, "无可行解", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("DRO→GEO: 转移时间 vs Δv_departure")
        return
    sc = ax.scatter(transfer_time * TU, delta_v * VU / 1000, s=6, alpha=0.6,
                    c=transfer_time * TU, cmap="viridis")
    style_colorbar(plt.colorbar(sc, ax=ax, label="转移时间 (天)"), PLOT_CONFIG)
    ax.set_xlabel("转移时间 (天)")
    ax.set_ylabel("Δv_departure (km/s)")
    ax.set_title("DRO→GEO: 转移时间 vs Δv_departure")
    ax.grid(True, alpha=0.3)


def _compute_departure_velocity(state6: np.ndarray, alpha: float) -> np.ndarray:
    """与 e2m2e TransferSearch._compute_departure_velocity 一致，计算速度扰动后的速度向量。"""
    pos = np.asarray(state6[:3], dtype=np.float64)
    vel = np.asarray(state6[3:6], dtype=np.float64)
    r_xy = float(np.sqrt(pos[0] ** 2 + pos[1] ** 2))
    if r_xy < 1e-10:
        return vel.copy()
    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)
    v_radial_comp = float(np.dot(vel, radial))
    v_tangential_comp = float(np.dot(vel, tangential))
    new_vel = v_radial_comp * radial + alpha * v_tangential_comp * tangential
    return new_vel


def _build_transfer_search() -> TransferSearch:
    """构建并配置 TransferSearch 实例（积分器参数与 grid_search_dro_to_geo.py 一致）。"""
    DT = 1.0 / (24.0 * TU)
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = DT
    transfer_search = TransferSearch(dynamics=dynamics)
    transfer_search.integration_dt = DT
    return transfer_search


def _integrate_single_orbit(args: tuple) -> tuple:
    """
    子进程 worker：构建积分器并积分单条转移轨道。
    参数 (args)：
        departure_state, alpha, max_transfer_time, mu, tu
    返回：
        (transfer_states, alpha, dv_departure) 或失败时 (None, ...)
    """
    import warnings

    departure_state, alpha, max_transfer_time, mu, tu = args
    DT = 1.0 / (24.0 * tu)
    try:
        system = e2m2e.core.system.CR3BP_System(
            mu=mu, primary="earth", secondary="moon"
        )
        dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
        dynamics.integrator = "DOP853"
        dynamics.rtol = 1e-12
        dynamics.atol = 1e-12
        dynamics.max_step = DT
        ts = TransferSearch(dynamics=dynamics)
        ts.integration_dt = DT

        pos = departure_state[:3]
        vel = departure_state[3:6]
        r_xy = float(np.sqrt(pos[0] ** 2 + pos[1] ** 2))
        if r_xy < 1e-10:
            tangential = np.array([-pos[1], pos[0], 0.0]) / max(r_xy, 1e-10)
        else:
            tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
        radial = pos / float(np.linalg.norm(pos))
        v_radial_comp = float(np.dot(vel, radial))
        v_tangential_comp = float(np.dot(vel, tangential))
        new_vel = v_radial_comp * radial + alpha * v_tangential_comp * tangential
        initial_state = np.concatenate([pos, new_vel])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            transfer_states, _ = ts._forward_integrate(
                initial_state, max_transfer_time, DT
            )

        dv_departure = float(np.linalg.norm(new_vel - vel))
        return transfer_states, alpha, dv_departure
    except Exception:
        return None, alpha, float("nan")


def _reintegrate_transfer(
    ts: TransferSearch,
    departure_state: np.ndarray,
    alpha: float,
    max_transfer_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    """重新积分转移轨迹，返回 (states, times)。"""
    new_vel = _compute_departure_velocity(departure_state, alpha)
    initial_state = np.concatenate([departure_state[:3], new_vel])
    dt = ts.integration_dt if ts.integration_dt is not None else 0.01
    states, times = ts._forward_integrate(initial_state, max_transfer_time, dt)
    return states, times


def _orbit_states_in_plane(
    orbit: Orbit, plane: str = "xz"
) -> tuple[np.ndarray, np.ndarray]:
    """返回轨道在指定平面上的坐标。plane: 'xz' | 'xy' | 'yz'。"""
    idx_map = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
    i, j = idx_map[plane]
    return orbit.states[:, i], orbit.states[:, j]


def _geo_circle_points(n_pts: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """GEO 圆在 x-y 平面上的投影（返回 x, y 两个 1D 数组）。"""
    th = np.linspace(0, 2 * np.pi, n_pts)
    earth_x = -MU
    return earth_x + R_GEO * np.cos(th), R_GEO * np.sin(th)


def _geo_sphere_points(n_pts: int = 200) -> np.ndarray:
    """
    生成 GEO 球面上的点（在旋转坐标系中）。

    地心在 (-μ, 0)，GEO 半径为 R_GEO。
    在旋转系中，GEO 球面近似为以 (-μ, 0, 0) 为圆心、R_GEO 为半径的圆（z=0 平面）。
    （严格来说在旋转系中由于科氏力会形成更复杂的形状，但 R_GEO 很小，近似为圆足够。）
    """
    theta = np.linspace(0.0, 2.0 * np.pi, n_pts)
    earth_x = -MU
    pts = np.zeros((n_pts, 3))
    pts[:, 0] = earth_x + R_GEO * np.cos(theta)
    pts[:, 1] = R_GEO * np.sin(theta)
    pts[:, 2] = 0.0
    return pts


def _plot_single_transfer_orbit(
    departure_orbit: Orbit,
    transfer_states: np.ndarray,
    departure_state: np.ndarray,
    dv_departure: float,
    dv_insertion: float,
    transfer_time: float,
    alpha: float,
    system: CR3BP_System,
    fig=None,
    ax=None,
) -> Axes:
    """绘制单条 DRO→GEO 转移轨道 3D 示意图。"""
    if ax is None:
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

    # DRO 出发轨道
    ax.plot(departure_orbit.states[:, 0], departure_orbit.states[:, 1],
            departure_orbit.states[:, 2], color="royalblue", lw=0.8, label="DRO")

    # 转移轨迹
    ax.plot(transfer_states[:, 0], transfer_states[:, 1], transfer_states[:, 2],
            color="crimson", lw=1.2, label="转移轨道")

    # 出发点
    dep_pos = np.asarray(departure_state, dtype=float)[:3]
    ax.scatter(*dep_pos, color="green", s=40, zorder=5, label="出发点")

    # GEO 穿越点（终点）
    ax.scatter(*transfer_states[-1, :3], color="orange", s=40, marker="s", zorder=5, label="终点")

    # GEO 球面（圆）
    gx, gy = _geo_circle_points()
    ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")

    # 地球和月球
    ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
    ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
    ax.text(EARTH_CENTER[0], EARTH_CENTER[1] + 0.03, 0, "地球", fontsize=PLOT_CONFIG.lp_label, ha="center")
    ax.text(1.0 - MU, 0.03, 0, "月球", fontsize=PLOT_CONFIG.lp_label, ha="center")

    # 平动点
    system.compute_libration_points()
    if system.L1 is None or system.L2 is None:
        raise RuntimeError("L1/L2 平动点未计算")
    for lp_name, lp_x in [("L1", system.L1[0]), ("L2", system.L2[0])]:
        ax.scatter(lp_x, 0, 0, color="red", marker="+", s=30, zorder=5)
        ax.text(lp_x, 0.02, 0, lp_name, fontsize=PLOT_CONFIG.lp_label, ha="center", color="red")

    ax.set_xlabel("x (DU)")
    ax.set_ylabel("y (DU)")
    ax.set_zlabel("z (DU)")

    dv_dep_phys = dv_departure * VU / 1000
    dv_ins_phys = dv_insertion * VU / 1000
    ax.set_title(
        f"DRO→GEO  α={alpha:.4f}  T={transfer_time:.2f} TU ({transfer_time * TU:.1f}天)\n"
        f"Δv_dep={dv_dep_phys:.4f} km/s  Δv_ins={dv_ins_phys:.4f} km/s"
    )
    ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

    # 等比例轴
    all_pts = np.concatenate([transfer_states[:, :3], departure_orbit.states[:, :3]])
    mid = all_pts.mean(axis=0)
    half = np.ptp(all_pts, axis=0).max() / 2.0 + 0.1
    ax.set_xlim(mid[0] - half, mid[0] + half)
    ax.set_ylim(mid[1] - half, mid[1] + half)
    ax.set_zlim(mid[2] - half, mid[2] + half)
    ax.set_box_aspect([1, 1, 1])

    return ax


def _select_feasible_indices(
    feasible_rows: list[dict], idx_arg: str, seed: int, max_indices: int | None = None
) -> list[int]:
    """根据 --idx 参数选择可行解索引列表。返回索引列表；支持：
    - 'all': 全部（可子采样）
    - 'best': Δv 最小的 1 个
    - 'best:N': Δv 最小的 N 个
    - 'random': 随机 1 个
    """
    n = len(feasible_rows)

    # 预计算所有 dv_total（dv_departure + dv_insertion）
    dv_vals = []
    for r in feasible_rows:
        dv_dep = r.get("dv_departure")
        dv_ins = r.get("dv_insertion")
        if dv_dep is not None and dv_ins is not None:
            dv = float(dv_dep) + float(dv_ins)
        else:
            dv = float("inf")
        dv_vals.append(dv)

    if idx_arg == "all":
        if max_indices is not None and n > max_indices:
            rng = np.random.default_rng(seed)
            chosen = rng.choice(n, size=max_indices, replace=False)
            print(f"  [all] 随机采样 {max_indices} / {n} 个可行解（seed={seed}）")
            return sorted(chosen.tolist())
        print(f"  [all] 绘制全部 {n} 个可行解")
        return list(range(n))
    elif idx_arg.startswith("best"):
        parts = idx_arg.split(":")
        if len(parts) == 2:
            try:
                top_n = int(parts[1])
            except ValueError:
                top_n = 1
        else:
            top_n = 1
        top_n = min(top_n, n)
        sorted_indices = sorted(range(n), key=lambda i: dv_vals[i])
        selected = sorted_indices[:top_n]
        if top_n == 1:
            print(
                f"  [best] 选择 Δv_total={dv_vals[selected[0]]:.6f} 的解（索引 {selected[0]}）"
            )
        else:
            print(
                f"  [best:{top_n}] 选择 Δv 最小的 {top_n} 个可行解（Δv 范围: {dv_vals[selected[0]]:.6f} ~ {dv_vals[selected[-1]]:.6f}）"
            )
        return selected
    elif idx_arg == "random":
        rng = np.random.default_rng(seed)
        chosen = rng.integers(0, n)
        print(f"  [random] 随机选择索引 {chosen}（seed={seed}）")
        return [int(chosen)]
    else:
        i = int(idx_arg)
        if i < 0 or i >= n:
            raise ValueError(f"索引 {i} 超出范围（可行解总数={n}）")
        return [i]


def interactive_browse_by_time(
    feasible_rows: list[dict],
    dro_orbit: Orbit,
    system: CR3BP_System,
    ts: TransferSearch,
) -> None:
    """按转移时间排序，交互式逐条浏览转移轨道（参考 plot_interactive_orbit_inspector.py）。"""
    plt.ion()

    sorted_rows = sorted(
        feasible_rows, key=lambda r: float(r.get("transfer_time", float("inf")))
    )
    n = len(sorted_rows)

    print(f"\n共 {n} 条可行解，已按转移时间排序")
    print("=" * 60)
    print("交互式转移轨道浏览器（按转移时间排序）")
    print("=" * 60)
    print("按 Enter: 绘制下一条轨道")
    print("输入 'q': 退出")
    print("输入 's N': 跳过 N 条")
    print("输入 'j N': 跳转到第 N 条")
    print("输入 'r': 重绘当前轨道")
    print("=" * 60 + "\n")

    current_idx = 0
    fig = None

    while True:
        row = sorted_rows[current_idx]
        alpha = float(row["alpha"])
        transfer_time = float(row["transfer_time"])
        departure_state = np.asarray(row["departure_state"], dtype=np.float64)

        dv_dep_raw = row.get("dv_departure")
        dv_arr = (
            np.asarray(dv_dep_raw, dtype=np.float64).ravel()
            if dv_dep_raw is not None
            else None
        )
        dv_departure = (
            float(dv_arr[0])
            if dv_arr is not None and dv_arr.size == 1
            else (float(np.linalg.norm(dv_arr)) if dv_arr is not None else float("nan"))
        )
        dv_insertion_raw = row.get("dv_insertion")
        dv_insertion = (
            float(dv_insertion_raw) if dv_insertion_raw is not None else float("nan")
        )

        print(f"\n[{current_idx + 1}/{n}] 转移轨道信息:")
        print(f"  α = {alpha:.4f}")
        print(f"  转移时间 = {transfer_time:.4f} TU")
        print(
            f"  Δv_dep = {dv_departure:.6f} ({dv_departure * VU * 1000:.1f} m/s)"
        )
        print(
            f"  Δv_ins = {dv_insertion:.6f} ({dv_insertion * VU * 1000:.1f} m/s)"
        )
        if np.isfinite(dv_departure) and np.isfinite(dv_insertion):
            dv_total = dv_departure + dv_insertion
            print(
                f"  Δv_total = {dv_total:.6f} ({dv_total * VU * 1000:.1f} m/s)"
            )

        transfer_states, _ = _reintegrate_transfer(
            ts, departure_state, alpha, transfer_time
        )

        if fig is not None:
            plt.close(fig)
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")
        _plot_single_transfer_orbit(
            departure_orbit=dro_orbit,
            transfer_states=transfer_states,
            departure_state=departure_state,
            dv_departure=dv_departure,
            dv_insertion=dv_insertion,
            transfer_time=transfer_time,
            alpha=alpha,
            system=system,
            fig=fig,
            ax=ax,
        )
        fig.tight_layout()
        fig.canvas.draw()
        fig.canvas.flush_events()

        try:
            user_input = input(
                "\n命令 (Enter继续, q退出, s跳过, j跳转, r重绘): "
            ).strip()
        except EOFError:
            break

        if user_input == "q":
            print("退出")
            break
        elif user_input.startswith("s "):
            try:
                skip_n = int(user_input.split()[1])
                current_idx = min(current_idx + skip_n, n - 1)
                print(f"跳转到第 {current_idx + 1} 条")
            except (ValueError, IndexError):
                print("无效的跳过数量")
        elif user_input.startswith("j "):
            try:
                target = int(user_input.split()[1])
                current_idx = max(0, min(target - 1, n - 1))
                print(f"跳转到第 {current_idx + 1} 条")
            except (ValueError, IndexError):
                print("无效的编号")
        elif user_input == "r":
            print(f"重绘第 {current_idx + 1} 条")
            continue
        else:
            if current_idx < n - 1:
                current_idx += 1
            else:
                print("已到达最后一条")
                break

    if fig is not None:
        plt.close(fig)
    plt.ioff()
    print(f"\n浏览完成，共查看了 {current_idx + 1} 条轨道")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="绘制 grid_search_dro_to_geo 结果（α–Δv 散点图 / 转移轨道示意图）"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="搜索结果 JSON 路径（默认使用硬编码路径）",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="保存 PNG 路径；不传则弹窗显示",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=50000,
        help="散点最多绘制的可行点数（过多时随机子采样）",
    )
    parser.add_argument("--seed", type=int, default=0, help="子采样随机种子")
    parser.add_argument("--dpi", type=int, default=150)
    # 转移轨道示意图专用参数
    parser.add_argument(
        "--orbit",
        action="store_true",
        help="绘制转移轨道示意图（替代散点图）",
    )
    parser.add_argument(
        "--idx",
        type=str,
        default="0",
        help="选择可行解：整数索引，'best'（Δv 最小 1 个），'best:N'（Δv 最小的 N 个），'random'，或 'all'（全部，受 --max-points 控制）",
    )
    parser.add_argument(
        "--n-workers",
        type=int,
        default=None,
        help="并行积分的 worker 进程数（默认 CPU 核数）；仅 --orbit 且多轨道时生效",
    )
    # 转移时间 vs Δv 图专用参数
    parser.add_argument(
        "--time-dv",
        action="store_true",
        help="绘制转移时间 vs Δv 散点图（替代 α–Δv 图）",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="交互式逐条浏览转移轨道（按转移时间排序）",
    )
    args = parser.parse_args()

    path = Path(args.file).expanduser().resolve() if args.file else Path(RESULTS_JSON).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    # 路径遍历防护：仅在用户通过 --file 指定路径时检查
    if args.file and safe_resolve_within(args.file, project_root) is None:
        print(f"安全拒绝: {args.file} 不在项目根目录 {project_root} 内")
        sys.exit(1)
    print(f"读取: {path}")

    rows = load_search_results(path)
    feasible_rows = [r for r in rows if r.get("is_feasible")]
    print(f"总行数={len(rows)}，可行解={len(feasible_rows)}")

    if args.interactive:
        # ── 交互式逐条浏览（按转移时间排序）──────────────────────────────────
        dro_path = Path(DRO_FILE).expanduser().resolve()
        if not dro_path.is_file():
            raise FileNotFoundError(f"DRO 轨道文件不存在: {dro_path}")

        print(f"加载 DRO: {dro_path}")
        dro_orbit = load_orbit_from_json(str(dro_path))

        ts = _build_transfer_search()
        system = ts.system

        interactive_browse_by_time(feasible_rows, dro_orbit, system, ts)
    elif args.orbit:
        # ── 转移轨道示意图 ──────────────────────────────────────────────────
        dro_path = Path(DRO_FILE).expanduser().resolve()
        if not dro_path.is_file():
            raise FileNotFoundError(f"DRO 轨道文件不存在: {dro_path}")

        print(f"加载 DRO: {dro_path}")
        dro_orbit = load_orbit_from_json(str(dro_path))

        # 构建 system（用于 OrbitVisualizer 和子进程）
        ts_dummy = _build_transfer_search()
        system = ts_dummy.system

        sel_indices = _select_feasible_indices(
            feasible_rows, args.idx, args.seed, max_indices=args.max_points
        )
        n_sel = len(sel_indices)

        # 并行积分（子进程各自构建积分器，不依赖外部对象）
        n_workers = args.n_workers
        use_parallel = n_sel > 1
        if use_parallel:
            print(f"并行积分：{n_sel} 条轨道，n_workers={n_workers or 'CPU 核数'}...")
            work_args = [
                (
                    np.asarray(feasible_rows[i]["departure_state"], dtype=np.float64),
                    float(feasible_rows[i]["alpha"]),
                    float(feasible_rows[i]["transfer_time"]),
                    float(MU),
                    float(TU),
                )
                for i in sel_indices
            ]
            with ProcessPoolExecutor(max_workers=n_workers) as executor:
                futures = {
                    executor.submit(_integrate_single_orbit, wa): (cm_idx, wa[1])
                    for cm_idx, wa in enumerate(work_args)
                }
                results: dict[int, tuple] = {}
                for future in as_completed(futures):
                    cm_idx, alpha = futures[future]
                    res = future.result()
                    results[cm_idx] = res
                    print(f"  [{len(results)}/{n_sel}] α={alpha:.3f} 完成")
        else:
            # 单条轨道：串行（用于 --idx 0 / best / random）
            result = feasible_rows[sel_indices[0]]
            departure_state = np.asarray(result["departure_state"], dtype=np.float64)
            alpha = float(result["alpha"])
            transfer_time = float(result["transfer_time"])
            dv_departure_raw = result.get("dv_departure")
            dv_arr = (
                np.asarray(dv_departure_raw, dtype=np.float64).ravel()
                if dv_departure_raw is not None
                else None
            )
            dv_departure = (
                float(dv_arr[0])
                if dv_arr is not None and dv_arr.size == 1
                else (
                    float(np.linalg.norm(dv_arr))
                    if dv_arr is not None
                    else float("nan")
                )
            )
            print(f"积分转移轨道（α={alpha}, T={transfer_time:.3f} TU）...")
            transfer_states, _ = _reintegrate_transfer(
                ts_dummy, departure_state, alpha, float(transfer_time)
            )
            results = {0: (transfer_states, alpha, dv_departure)}

        if n_sel == 1:
            transfer_states, alpha, dv_departure = results[0]
            departure_state = np.asarray(
                feasible_rows[sel_indices[0]]["departure_state"], dtype=np.float64
            )
            dv_insertion_raw = feasible_rows[sel_indices[0]].get("dv_insertion")
            dv_insertion = (
                float(dv_insertion_raw)
                if dv_insertion_raw is not None
                else float("nan")
            )

            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")
            ax = _plot_single_transfer_orbit(
                departure_orbit=dro_orbit,
                transfer_states=transfer_states,
                departure_state=departure_state,
                dv_departure=dv_departure,
                dv_insertion=dv_insertion,
                transfer_time=float(feasible_rows[sel_indices[0]]["transfer_time"]),
                alpha=alpha,
                system=system,
                fig=fig,
                ax=ax,
            )
        else:
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")

            # DRO
            ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1],
                    dro_orbit.states[:, 2], color="royalblue", lw=0.8, label="DRO")

            # GEO 球面
            gx, gy = _geo_circle_points()
            ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")

            # 转移轨迹（过滤积分失败的结果）
            cmap = matplotlib.colormaps["plasma"]
            n_skipped = 0
            for cm_idx in range(n_sel):
                transfer_states, alpha, dv_departure = results[cm_idx]
                if transfer_states is None:
                    n_skipped += 1
                    continue
                sel_idx = sel_indices[cm_idx]
                departure_state = np.asarray(
                    feasible_rows[sel_idx]["departure_state"], dtype=np.float64
                )

                color = cmap(cm_idx / max(n_sel - 1, 1))
                ax.plot(transfer_states[:, 0], transfer_states[:, 1],
                        transfer_states[:, 2], color=color, lw=1.2, alpha=0.7)
                ax.scatter(*departure_state[:3], color=color, s=30, alpha=0.8)

            if n_skipped:
                print(f"  警告: {n_skipped}/{n_sel} 条转移轨迹积分失败，已跳过")

            # 地球和月球
            ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
            ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
            ax.text(EARTH_CENTER[0], EARTH_CENTER[1] + 0.03, 0, "地球", fontsize=PLOT_CONFIG.lp_label, ha="center")
            ax.text(1.0 - MU, 0.03, 0, "月球", fontsize=PLOT_CONFIG.lp_label, ha="center")

            # 平动点
            system.compute_libration_points()
            if system.L1 is None or system.L2 is None:
                raise RuntimeError("L1/L2 平动点未计算")
            for lp_name, lp_x in [("L1", system.L1[0]), ("L2", system.L2[0])]:
                ax.scatter(lp_x, 0, 0, color="red", marker="+", s=30, zorder=5)
                ax.text(lp_x, 0.02, 0, lp_name, fontsize=PLOT_CONFIG.lp_label, ha="center", color="red")

            ax.set_xlabel("x (DU)")
            ax.set_ylabel("y (DU)")
            ax.set_zlabel("z (DU)")
            ax.set_title(f"DRO→GEO: {n_sel} 条转移轨道")
            ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

            # 等比例轴
            all_pts = dro_orbit.states[:, :3]
            mid = all_pts.mean(axis=0)
            half = np.ptp(all_pts, axis=0).max() / 2.0 + 0.1
            ax.set_xlim(mid[0] - half, mid[0] + half)
            ax.set_ylim(mid[1] - half, mid[1] + half)
            ax.set_zlim(mid[2] - half, mid[2] + half)
            ax.set_box_aspect([1, 1, 1])

        if args.save:
            png = Path(args.save).expanduser().resolve()
            if png.suffix.lower() != ".png":
                png = png.with_suffix(".png")
            png.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
            print(f"Saved: {png}")
        else:
            plt.show()
        plt.close(fig)
    else:
        if args.time_dv:
            # ── 转移时间–Δv 散点图 ─────────────────────────────────────────
            times_all, dvs_all = feasible_transfer_time_and_dv(rows)
            n_feas = len(times_all)
            idx = subsample_indices(n_feas, args.max_points, args.seed)
            times = times_all[idx]
            dvs = dvs_all[idx]

            fig, ax = plt.subplots(figsize=(10, 6))
            plot_transfer_time_delta_v(ax, times, dvs)
            fig.tight_layout()

            if args.save:
                png = Path(args.save).expanduser().resolve()
                if png.suffix.lower() != ".png":
                    png = png.with_suffix(".png")
                png.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
                print(f"Saved: {png}")
            else:
                plt.show()
            plt.close(fig)
        else:
            # ── α–Δv 散点图 ─────────────────────────────────────────────
            alpha_all, dv_all = feasible_alpha_and_departure_dv(rows)
            n_feas = len(alpha_all)
            idx = subsample_indices(n_feas, args.max_points, args.seed)
            alpha = alpha_all[idx]
            dv = dv_all[idx]

            fig, ax = plt.subplots(figsize=(10, 6))
            plot_alpha_delta_v(ax, alpha, dv)
            fig.tight_layout()

            if args.save:
                png = Path(args.save).expanduser().resolve()
                if png.suffix.lower() != ".png":
                    png = png.with_suffix(".png")
                png.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
                print(f"Saved: {png}")
            else:
                plt.show()
            plt.close(fig)


if __name__ == "__main__":
    main()
