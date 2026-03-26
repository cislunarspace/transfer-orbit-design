"""
可视化 grid_search 输出的搜索结果 JSON：可行解的 α–Δv 散点图与转移轨道示意图。

在下方 ``RESULTS_JSON`` 中指定要绘制的 grid_search 输出 JSON（相对仓库根目录或绝对路径均可）。

Δv 优先使用 JSON 中的 dv_departure，否则由 departure_state 与 α 按搜索阶段速度扰动模型计算。

转移轨道示意图通过重新积分转移轨迹（从 departure_state 出发，以 α 扰动的速度），
叠加绘制 DRO 出发轨道与 RO 到达轨道，直观展示转移路径。

用法:
    python plot_search_results.py                                      # 仅 α–Δv 散点图
    python plot_search_results.py --orbit                            # 转移轨道 3D 示意图
    python plot_search_results.py --orbit --save output/transfer/figures/search_orbit.png
    python plot_search_results.py --orbit --idx 0                      # 绘制第 idx 个可行解
    python plot_search_results.py --orbit --idx best                  # 绘制 Δv 最小的可行解
    python plot_search_results.py --orbit --idx random --seed 42      # 随机一个可行解
    python plot_search_results.py --orbit --idx all                    # 绘制全部可行解（子采样受 --max-points 控制）
    python plot_search_results.py --orbit --idx all --max-points 100  # 最多绘制 100 条
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np

# 配置中文字体（解决 Windows 下中文显示为方块的问题）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimSun", "Noto Sans SC"]
plt.rcParams["axes.unicode_minus"] = False

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import e2m2e
from e2m2e.core import CR3BP_System, Orbit
from e2m2e.transfer import DROTransferSearch, load_orbit_from_json
from e2m2e.visualization.plotting import OrbitVisualizer

from scripts.utils.common import MU, DU, TU

# =============================================================================
# 数据文件：grid_search 输出的 JSON
# =============================================================================
RESULTS_JSON = project_root / "output/transfer/search_results_200-1001-0.5-2.5-2.299848_3857331829.json"
# 示例: RESULTS_JSON = project_root / "output/transfer/search_results_10-101-0.5-2.5-2.298634_3857123456.json"

# 轨道数据文件（用于转移轨道积分和绘图）
DRO_FILE = project_root / "output/dro/dro_31_3857337599.json"
RO_FILE = project_root / "output/ro/ro_31_3857337606.json"


def departure_delta_v_norm(state6: np.ndarray, alpha: float) -> float:
    """与 e2m2e DROTransferSearch._compute_departure_velocity 一致，返回 ‖v'−v‖（无量纲速度）。"""
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


def subsample_indices(n: int, max_points: int | None, seed: int) -> np.ndarray:
    if max_points is None or n <= max_points:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n, size=max_points, replace=False))


def plot_alpha_delta_v(
    ax: Axes,
    alpha: np.ndarray,
    delta_v: np.ndarray,
) -> None:
    if len(alpha) == 0:
        ax.text(
            0.5,
            0.5,
            "no feasible points",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_title("Feasible: departure Δv vs α")
        return
    ax.scatter(
        alpha,
        delta_v,
        c="crimson",
        s=16,
        alpha=0.75,
        edgecolors="darkred",
        linewidths=0.3,
        rasterized=True,
    )
    ax.set_xlabel("α")
    ax.set_ylabel("Δv (departure, ‖Δv‖)")
    ax.set_title("Feasible solutions: departure Δv vs α")
    ax.grid(True, alpha=0.3)


def _compute_departure_velocity(state6: np.ndarray, alpha: float) -> np.ndarray:
    """与 e2m2e DROTransferSearch._compute_departure_velocity 一致，计算速度扰动后的速度向量。"""
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


def _build_transfer_search() -> DROTransferSearch:
    """构建并配置 DROTransferSearch 实例（积分器参数与 grid_search.py 一致）。"""
    DT = 1.0 / (24.0 * TU)
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = DT
    transfer_search = DROTransferSearch(system=system, dynamics=dynamics)
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
        system = e2m2e.core.system.CR3BP_System(mu=mu, primary="earth", secondary="moon")
        dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
        dynamics.integrator = "DOP853"
        dynamics.rtol = 1e-12
        dynamics.atol = 1e-12
        dynamics.max_step = DT
        ts = DROTransferSearch(system=system, dynamics=dynamics)
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
            transfer_states, _ = ts._forward_integrate(initial_state, max_transfer_time, DT)

        dv_departure = float(np.linalg.norm(new_vel - vel))
        return transfer_states, alpha, dv_departure
    except Exception:
        return None, alpha, float("nan")


def _reintegrate_transfer(
    ts: DROTransferSearch,
    departure_state: np.ndarray,
    alpha: float,
    max_transfer_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    """重新积分转移轨迹，返回 (states, times)。"""
    new_vel = _compute_departure_velocity(departure_state, alpha)
    initial_state = np.concatenate([departure_state[:3], new_vel])
    states, times = ts._forward_integrate(initial_state, max_transfer_time, ts.integration_dt)
    return states, times


def _orbit_states_in_plane(
    orbit: Orbit, plane: str = "xz"
) -> tuple[np.ndarray, np.ndarray]:
    """返回轨道在指定平面上的坐标。plane: 'xz' | 'xy' | 'yz'。"""
    idx_map = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
    i, j = idx_map[plane]
    return orbit.states[:, i], orbit.states[:, j]


def _find_closest_orbit_phase_idx(
    transfer_states: np.ndarray, orbit: Orbit
) -> int:
    """找到转移轨迹终点与目标轨道最接近的点（轨道相位索引）。"""
    pos_tr = transfer_states[-1, :2]
    min_dist = float("inf")
    best_idx = 0
    for i in range(len(orbit.states)):
        d = np.linalg.norm(orbit.states[i, :2] - pos_tr)
        if d < min_dist:
            min_dist = d
            best_idx = i
    return best_idx


def plot_transfer_orbit_diagram_3d(
    departure_orbit: Orbit,
    arrival_orbit: Orbit,
    transfer_states: np.ndarray,
    transfer_times: np.ndarray,
    departure_state: np.ndarray,
    arrival_orbit_phase_idx: int,
    dv_departure: float,
    dv_insertion: float,
    transfer_time: float,
    alpha: float,
    system: CR3BP_System,
    fig=None,
    ax=None,
) -> Axes:
    """绘制转移轨道 3D 示意图：DRO出发轨道 + 转移轨迹 + RO到达轨道。"""
    if ax is None:
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection="3d")

    # 绘制 DRO 出发轨道（蓝色）
    ax.plot(
        departure_orbit.states[:, 0],
        departure_orbit.states[:, 1],
        departure_orbit.states[:, 2],
        "-", color="steelblue", lw=1.0, alpha=0.7, label="DRO (departure)"
    )

    # 绘制 RO 到达轨道（绿色）
    ax.plot(
        arrival_orbit.states[:, 0],
        arrival_orbit.states[:, 1],
        arrival_orbit.states[:, 2],
        "-", color="seagreen", lw=1.0, alpha=0.7, label="RO (arrival)"
    )

    # 绘制转移轨迹（红色）
    ax.plot(
        transfer_states[:, 0],
        transfer_states[:, 1],
        transfer_states[:, 2],
        "-", color="crimson", lw=2.0, alpha=0.9, label="Transfer trajectory"
    )

    # 标注出发点
    ax.scatter(
        [departure_state[0]], [departure_state[1]], [departure_state[2]],
        color="blue", s=100, zorder=5, label="Departure point"
    )

    # 标注到达点
    arrival_point = arrival_orbit.states[arrival_orbit_phase_idx]
    ax.scatter(
        [arrival_point[0]], [arrival_point[1]], [arrival_point[2]],
        color="green", s=100, zorder=5, label="Arrival point"
    )

    # 使用 OrbitVisualizer 绘制地球、月球和拉格朗日点
    orbit_plotter = OrbitVisualizer(system=system)
    orbit_plotter.primary_body_color = "blue"
    orbit_plotter.secondary_body_color = "silver"
    orbit_plotter.libration_point_colors = ["gray"] * 5
    orbit_plotter.libration_point_markers = ["^"] * 5
    orbit_plotter.libration_point_sizes = [60] * 5
    orbit_plotter.plot_primary_bodies(ax=ax, is_3d=True)
    orbit_plotter.plot_libration_points(ax=ax, is_3d=True, show_labels=True)

    # 坐标轴范围（自适应转移轨迹）
    all_x = np.concatenate([
        departure_orbit.states[:, 0], arrival_orbit.states[:, 0], transfer_states[:, 0]
    ])
    all_y = np.concatenate([
        departure_orbit.states[:, 1], arrival_orbit.states[:, 1], transfer_states[:, 1]
    ])
    all_z = np.concatenate([
        departure_orbit.states[:, 2], arrival_orbit.states[:, 2], transfer_states[:, 2]
    ])
    cx = (all_x.max() + all_x.min()) / 2
    cy = (all_y.max() + all_y.min()) / 2
    cz = (all_z.max() + all_z.min()) / 2
    span = max(all_x.max() - all_x.min(), all_y.max() - all_y.min(), all_z.max() - all_z.min()) / 2
    span = max(span, 0.3) * 1.2
    ax.set_xlim(cx - span, cx + span)
    ax.set_ylim(cy - span, cy + span)
    ax.set_zlim(cz - span, cz + span)

    # 标题
    dv_dep_phys = dv_departure * 1023.23281
    dv_ins_phys = dv_insertion * 1023.23281
    ax.set_title(
        f"Transfer orbit: α={alpha:.3f}, T={transfer_time:.2f} TU\n"
        f"Δv_dep={dv_dep_phys:.2f} m/s, Δv_ins={dv_ins_phys:.2f} m/s",
        fontsize=11,
    )
    ax.set_xlabel("X (nondimensional)", fontsize=10)
    ax.set_ylabel("Y (nondimensional)", fontsize=10)
    ax.set_zlabel("Z (nondimensional)", fontsize=10)
    ax.legend(loc="upper right", fontsize=9)

    # 视角：侧视（地球在左，月球在右）
    ax.view_init(elev=0, azim=-90)

    return ax


def _select_feasible_indices(
    feasible_rows: list[dict], idx_arg: str, seed: int, max_indices: int | None = None
) -> list[int]:
    """根据 --idx 参数选择可行解索引列表。返回索引列表；'all' 返回全部（可子采样）。"""
    n = len(feasible_rows)
    if idx_arg == "all":
        if max_indices is not None and n > max_indices:
            rng = np.random.default_rng(seed)
            chosen = rng.choice(n, size=max_indices, replace=False)
            print(f"  [all] 随机采样 {max_indices} / {n} 个可行解（seed={seed}）")
            return sorted(chosen.tolist())
        print(f"  [all] 绘制全部 {n} 个可行解")
        return list(range(n))
    elif idx_arg == "best":
        dv_vals = []
        for r in feasible_rows:
            dv_raw = r.get("dv_departure")
            if dv_raw is not None:
                dv_arr = np.asarray(dv_raw, dtype=np.float64).ravel()
                dv = float(dv_arr[0]) if dv_arr.size == 1 else float(np.linalg.norm(dv_arr))
            else:
                dv = float("inf")
            dv_vals.append(dv)
        best_i = int(np.argmin(dv_vals))
        print(f"  [best] 选择 Δv={dv_vals[best_i]:.6f} 的解（索引 {best_i}）")
        return [best_i]
    elif idx_arg == "random":
        rng = np.random.default_rng(seed)
        chosen = rng.integers(0, n)
        print(f"  [random] 随机选择索引 {chosen}（seed={seed}）")
        return [chosen]
    else:
        i = int(idx_arg)
        if i < 0 or i >= n:
            raise ValueError(f"索引 {i} 超出范围（可行解总数={n}）")
        return [i]


def main() -> None:
    parser = argparse.ArgumentParser(description="绘制 grid_search 结果（α–Δv 散点图 / 转移轨道示意图）")
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
        help="选择可行解：整数索引，'best'（Δv 最小），'random'，或 'all'（全部，受 --max-points 控制）",
    )
    parser.add_argument(
        "--n-workers",
        type=int,
        default=None,
        help="并行积分的 worker 进程数（默认 CPU 核数）；仅 --orbit --idx all 时生效",
    )
    args = parser.parse_args()

    path = Path(RESULTS_JSON).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    print(f"读取: {path}")

    rows = load_search_results(path)
    feasible_rows = [r for r in rows if r.get("is_feasible")]
    print(f"总行数={len(rows)}，可行解={len(feasible_rows)}")

    if args.orbit:
        # ── 转移轨道示意图 ──────────────────────────────────────────────────
        dro_path = Path(DRO_FILE).expanduser().resolve()
        ro_path = Path(RO_FILE).expanduser().resolve()
        if not dro_path.is_file():
            raise FileNotFoundError(f"DRO 轨道文件不存在: {dro_path}")
        if not ro_path.is_file():
            raise FileNotFoundError(f"RO 轨道文件不存在: {ro_path}")

        print(f"加载 DRO: {dro_path}")
        print(f"加载 RO: {ro_path}")
        dro_orbit = load_orbit_from_json(str(dro_path))
        ro_orbit = load_orbit_from_json(str(ro_path))

        # 构建 system（用于 OrbitVisualizer 和子进程）
        ts_dummy = _build_transfer_search()
        system = ts_dummy.system

        sel_indices = _select_feasible_indices(
            feasible_rows, args.idx, args.seed, max_indices=args.max_points
        )
        n_sel = len(sel_indices)

        # 并行积分（子进程各自构建积分器，不依赖外部对象）
        n_workers = args.n_workers
        use_parallel = (n_sel > 1)
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
            dv_arr = np.asarray(dv_departure_raw, dtype=np.float64).ravel() if dv_departure_raw is not None else None
            dv_departure = float(dv_arr[0]) if dv_arr is not None and dv_arr.size == 1 else (float(np.linalg.norm(dv_arr)) if dv_arr is not None else float("nan"))
            print(f"积分转移轨道（α={alpha}, T={transfer_time:.3f} TU）...")
            transfer_states, _ = _reintegrate_transfer(
                ts_dummy, departure_state, alpha, float(transfer_time)
            )
            arrival_phase_idx = _find_closest_orbit_phase_idx(transfer_states, ro_orbit)
            results = {0: (transfer_states, alpha, dv_departure)}

        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection="3d")

        # 只绘制一次 DRO 和 RO 轨道（所有解共用）
        ax.plot(
            dro_orbit.states[:, 0], dro_orbit.states[:, 1], dro_orbit.states[:, 2],
            "-", color="steelblue", lw=1.0, alpha=0.5, label="DRO (departure)"
        )
        ax.plot(
            ro_orbit.states[:, 0], ro_orbit.states[:, 1], ro_orbit.states[:, 2],
            "-", color="seagreen", lw=1.0, alpha=0.5, label="RO (arrival)"
        )

        # 用颜色映射区分不同解
        cmap = plt.cm.plasma
        for cm_idx in range(n_sel):
            transfer_states, alpha, dv_departure = results[cm_idx]
            sel_idx = sel_indices[cm_idx]
            departure_state = np.asarray(feasible_rows[sel_idx]["departure_state"], dtype=np.float64)
            arrival_phase_idx = _find_closest_orbit_phase_idx(transfer_states, ro_orbit)

            color = cmap(cm_idx / max(n_sel - 1, 1))
            ax.plot(
                transfer_states[:, 0], transfer_states[:, 1], transfer_states[:, 2],
                "-", color=color, lw=1.2, alpha=0.7
            )
            # 标注出发点
            ax.scatter(
                [departure_state[0]], [departure_state[1]], [departure_state[2]],
                color=color, s=30, alpha=0.8
            )
            # 标注到达点
            arrival_point = ro_orbit.states[arrival_phase_idx]
            ax.scatter(
                [arrival_point[0]], [arrival_point[1]], [arrival_point[2]],
                color=color, s=30, alpha=0.8, marker="s"
            )

        # 使用 OrbitVisualizer 绘制地球、月球和拉格朗日点
        orbit_plotter = OrbitVisualizer(system=system)
        orbit_plotter.primary_body_color = "blue"
        orbit_plotter.secondary_body_color = "silver"
        orbit_plotter.libration_point_colors = ["gray"] * 5
        orbit_plotter.libration_point_markers = ["^"] * 5
        orbit_plotter.libration_point_sizes = [60] * 5
        orbit_plotter.plot_primary_bodies(ax=ax, is_3d=True)
        orbit_plotter.plot_libration_points(ax=ax, is_3d=True, show_labels=True)

        # 坐标轴范围（自适应）
        all_x = np.concatenate([dro_orbit.states[:, 0], ro_orbit.states[:, 0]])
        all_y = np.concatenate([dro_orbit.states[:, 1], ro_orbit.states[:, 1]])
        all_z = np.concatenate([dro_orbit.states[:, 2], ro_orbit.states[:, 2]])
        cx = (all_x.max() + all_x.min()) / 2
        cy = (all_y.max() + all_y.min()) / 2
        cz = (all_z.max() + all_z.min()) / 2
        span = max(
            all_x.max() - all_x.min(), all_y.max() - all_y.min(), all_z.max() - all_z.min()
        ) / 2
        span = max(span, 0.3) * 1.2
        ax.set_xlim(cx - span, cx + span)
        ax.set_ylim(cy - span, cy + span)
        ax.set_zlim(cz - span, cz + span)

        ax.set_xlabel("X (nondimensional)", fontsize=10)
        ax.set_ylabel("Y (nondimensional)", fontsize=10)
        ax.set_zlabel("Z (nondimensional)", fontsize=10)
        ax.set_title(f"Transfer orbits: {n_sel} feasible solutions", fontsize=11)
        ax.legend(loc="upper right", fontsize=9)
        ax.view_init(elev=0, azim=-90)

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
        # ── α–Δv 散点图（原有功能）─────────────────────────────────────────
        alpha_all, dv_all = feasible_alpha_and_departure_dv(rows)
        n_feas = len(alpha_all)
        idx = subsample_indices(n_feas, args.max_points, args.seed)
        alpha = alpha_all[idx]
        dv = dv_all[idx]

        fig, ax = plt.subplots(figsize=(7, 5))
        plot_alpha_delta_v(ax, alpha, dv)
        fig.suptitle(
            f"N={len(rows)} rows, {n_feas} feasible, {len(idx)} points drawn",
            fontsize=11,
            y=1.02,
        )
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
