"""
可视化 grid_search_dro_to_geo 输出的搜索结果 JSON：可行解的 α–Δv 散点图、转移时间–Δv 散点图与转移轨道示意图。

在下方 ``RESULTS_JSON`` 中指定要绘制的 grid_search_dro_to_geo 输出 JSON（相对仓库根目录或绝对路径均可）。

Δv 优先使用 JSON 中的 dv_departure，否则由 departure_state 与 α 按搜索阶段速度扰动模型计算。

转移轨道示意图通过重新积分转移轨迹（从 departure_state 出发，以 α 扰动的速度），
叠加绘制 DRO 出发轨道与 GEO 球面，直观展示转移路径。

用法:
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo              # 仅 α–Δv 散点图
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --time-dv   # 转移时间–Δv 散点图
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit      # 转移轨道 3D 示意图
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --save output/transfer/figures/search_geo_orbit.png
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx 0        # 绘制第 idx 个可行解
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx best      # 绘制 Δv 最小的可行解
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx random --seed 42  # 随机一个可行解
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx all        # 绘制全部可行解（子采样受 --max-points 控制）
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx all --max-points 100  # 最多绘制 100 条
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --orbit --idx best:10      # 绘制 Δv 最小的 10 条轨道
    python -m tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --interactive           # 交互式逐条浏览（按转移时间排序）
"""

from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import matplotlib
from tod.commons.common import find_project_root
project_root = find_project_root(Path(__file__))

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(project_root))

from tod.commons.plot_helpers import apply_standard_plot_config, subsample_indices
from tod.commons.common import MU, TU, VU, safe_resolve_within
from tod.plot.transfer.common import (
    load_search_results,
    feasible_alpha_and_departure_dv,
    feasible_transfer_time_and_dv,
    plot_alpha_delta_v,
    plot_transfer_time_delta_v,
    select_feasible_indices,
    geo_circle_points,
    plot_celestial_bodies,
    set_equal_aspect_3d,
)

PLOT_CONFIG = apply_standard_plot_config()

import e2m2e
from e2m2e.core import CR3BP_System, Orbit
from e2m2e.transfer import TransferSearch, load_orbit_from_json
from e2m2e.orbits.geo import R_GEO, EARTH_CENTER

logger = logging.getLogger(__name__)

# =============================================================================
# 数据文件
# =============================================================================
RESULTS_JSON = (
    project_root
    / "output/transfer/search_dro_geo_200-100-0.5-2.5-22.9985_3858323266.json"
)

DRO_FILE = project_root / "output/dro/dro_31_3857693511.json"


def _compute_departure_velocity(state6: np.ndarray, alpha: float) -> np.ndarray:
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
        tangential = np.array([-pos[1], pos[0], 0.0]) / max(r_xy, 1e-10)
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
    new_vel = _compute_departure_velocity(departure_state, alpha)
    initial_state = np.concatenate([departure_state[:3], new_vel])
    dt = ts.integration_dt if ts.integration_dt is not None else 0.01
    states, times = ts._forward_integrate(initial_state, max_transfer_time, dt)
    return states, times


def _geo_sphere_points(n_pts: int = 200) -> np.ndarray:
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
) -> plt.Axes:
    if ax is None:
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

    ax.plot(departure_orbit.states[:, 0], departure_orbit.states[:, 1],
            departure_orbit.states[:, 2], color="royalblue", lw=0.8, label="DRO")
    ax.plot(transfer_states[:, 0], transfer_states[:, 1], transfer_states[:, 2],
            color="crimson", lw=1.2, label="转移轨道")

    dep_pos = np.asarray(departure_state, dtype=float)[:3]
    ax.scatter(*dep_pos, color="green", s=40, zorder=5, label="出发点")
    ax.scatter(*transfer_states[-1, :3], color="orange", s=40, marker="s", zorder=5, label="终点")

    gx, gy = geo_circle_points()
    ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")

    plot_celestial_bodies(ax, system, PLOT_CONFIG)

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

    all_pts = np.concatenate([transfer_states[:, :3], departure_orbit.states[:, :3]])
    set_equal_aspect_3d(ax, all_pts)

    return ax


def interactive_browse_by_time(
    feasible_rows: list[dict],
    dro_orbit: Orbit,
    system: CR3BP_System,
    ts: TransferSearch,
) -> None:
    plt.ion()

    sorted_rows = sorted(
        feasible_rows, key=lambda r: float(r.get("transfer_time", float("inf")))
    )
    n = len(sorted_rows)

    logger.info("共 %d 条可行解，已按转移时间排序", n)
    logger.info("=" * 60)
    logger.info("交互式转移轨道浏览器（按转移时间排序）")
    logger.info("=" * 60)
    logger.info("按 Enter: 绘制下一条轨道")
    logger.info("输入 'q': 退出")
    logger.info("输入 's N': 跳过 N 条")
    logger.info("输入 'j N': 跳转到第 N 条")
    logger.info("输入 'r': 重绘当前轨道")
    logger.info("=" * 60)

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

        logger.info("[%d/%d] 转移轨道信息:", current_idx + 1, n)
        logger.info("  α = %.4f", alpha)
        logger.info("  转移时间 = %.4f TU", transfer_time)
        logger.info("  Δv_dep = %.6f (%.1f m/s)", dv_departure, dv_departure * VU * 1000)
        logger.info("  Δv_ins = %.6f (%.1f m/s)", dv_insertion, dv_insertion * VU * 1000)
        if np.isfinite(dv_departure) and np.isfinite(dv_insertion):
            dv_total = dv_departure + dv_insertion
            logger.info("  Δv_total = %.6f (%.1f m/s)", dv_total, dv_total * VU * 1000)

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
            user_input = input("\n命令 (Enter继续, q退出, s跳过, j跳转, r重绘): ").strip()
        except EOFError:
            break

        if user_input == "q":
            logger.info("退出")
            break
        elif user_input.startswith("s "):
            try:
                skip_n = int(user_input.split()[1])
                current_idx = min(current_idx + skip_n, n - 1)
                logger.info("跳转到第 %d 条", current_idx + 1)
            except (ValueError, IndexError):
                logger.warning("无效的跳过数量")
        elif user_input.startswith("j "):
            try:
                target = int(user_input.split()[1])
                current_idx = max(0, min(target - 1, n - 1))
                logger.info("跳转到第 %d 条", current_idx + 1)
            except (ValueError, IndexError):
                logger.warning("无效的编号")
        elif user_input == "r":
            logger.info("重绘第 %d 条", current_idx + 1)
            continue
        else:
            if current_idx < n - 1:
                current_idx += 1
            else:
                logger.info("已到达最后一条")
                break

    if fig is not None:
        plt.close(fig)
    plt.ioff()
    logger.info("浏览完成，共查看了 %d 条轨道", current_idx + 1)


def _save_or_show(fig, args):
    if args.save:
        png = Path(args.save).expanduser().resolve()
        if png.suffix.lower() != ".png":
            png = png.with_suffix(".png")
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
        logger.info("Saved: %s", png)
    else:
        plt.show()
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="绘制 grid_search_dro_to_geo 结果（α–Δv 散点图 / 转移轨道示意图）"
    )
    parser.add_argument("--file", type=str, default=None, help="搜索结果 JSON 路径")
    parser.add_argument("--save", type=str, default=None, help="保存 PNG 路径")
    parser.add_argument("--max-points", type=int, default=50000, help="散点最多可行点数")
    parser.add_argument("--seed", type=int, default=0, help="子采样随机种子")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--orbit", action="store_true", help="绘制转移轨道示意图")
    parser.add_argument("--idx", type=str, default="0", help="选择可行解：整数索引/best/best:N/random/all")
    parser.add_argument("--n-workers", type=int, default=None, help="并行积分 worker 数")
    parser.add_argument("--time-dv", action="store_true", help="绘制转移时间 vs Δv 散点图")
    parser.add_argument("--interactive", action="store_true", help="交互式逐条浏览")
    args = parser.parse_args()

    path = Path(args.file).expanduser().resolve() if args.file else Path(RESULTS_JSON).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if args.file and safe_resolve_within(args.file, project_root) is None:
        logger.warning("安全拒绝: %s 不在项目根目录 %s 内", args.file, project_root)
        sys.exit(1)
    logger.info("读取: %s", path)

    rows = load_search_results(path)
    feasible_rows = [r for r in rows if r.get("is_feasible")]
    logger.info("总行数=%d，可行解=%d", len(rows), len(feasible_rows))

    if args.interactive:
        dro_path = Path(DRO_FILE).expanduser().resolve()
        if not dro_path.is_file():
            raise FileNotFoundError(f"DRO 轨道文件不存在: {dro_path}")
        logger.info("加载 DRO: %s", dro_path)
        dro_orbit = load_orbit_from_json(str(dro_path))
        ts = _build_transfer_search()
        interactive_browse_by_time(feasible_rows, dro_orbit, ts.system, ts)
    elif args.orbit:
        dro_path = Path(DRO_FILE).expanduser().resolve()
        if not dro_path.is_file():
            raise FileNotFoundError(f"DRO 轨道文件不存在: {dro_path}")
        logger.info("加载 DRO: %s", dro_path)
        dro_orbit = load_orbit_from_json(str(dro_path))
        ts_dummy = _build_transfer_search()
        system = ts_dummy.system

        sel_indices = select_feasible_indices(
            feasible_rows, args.idx, args.seed, max_indices=args.max_points
        )
        n_sel = len(sel_indices)

        use_parallel = n_sel > 1
        if use_parallel:
            logger.info("并行积分：%d 条轨道，n_workers=%s...", n_sel, args.n_workers or 'CPU 核数')
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
            results: dict[int, tuple] = {}
            with ProcessPoolExecutor(max_workers=args.n_workers) as executor:
                futures = {
                    executor.submit(_integrate_single_orbit, wa): (cm_idx, wa[1])
                    for cm_idx, wa in enumerate(work_args)
                }
                for future in as_completed(futures):
                    cm_idx, alpha = futures[future]
                    results[cm_idx] = future.result()
                    logger.info("  [%d/%d] α=%.3f 完成", len(results), n_sel, alpha)
        else:
            result = feasible_rows[sel_indices[0]]
            departure_state = np.asarray(result["departure_state"], dtype=np.float64)
            alpha = float(result["alpha"])
            transfer_time = float(result["transfer_time"])
            dv_dep_raw = result.get("dv_departure")
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
            logger.info("积分转移轨道（α=%.4f, T=%.3f TU）...", alpha, transfer_time)
            transfer_states, _ = _reintegrate_transfer(
                ts_dummy, departure_state, alpha, float(transfer_time)
            )
            results = {0: (transfer_states, alpha, dv_departure)}

        if n_sel == 1:
            transfer_states, alpha, dv_departure = results[0]
            departure_state = np.asarray(
                feasible_rows[sel_indices[0]]["departure_state"], dtype=np.float64
            )
            dv_ins_raw = feasible_rows[sel_indices[0]].get("dv_insertion")
            dv_insertion = float(dv_ins_raw) if dv_ins_raw is not None else float("nan")

            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")
            _plot_single_transfer_orbit(
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

            ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1],
                    dro_orbit.states[:, 2], color="royalblue", lw=0.8, label="DRO")
            gx, gy = geo_circle_points()
            ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")

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
                logger.warning("%d/%d 条转移轨迹积分失败，已跳过", n_skipped, n_sel)

            plot_celestial_bodies(ax, system, PLOT_CONFIG)
            ax.set_xlabel("x (DU)")
            ax.set_ylabel("y (DU)")
            ax.set_zlabel("z (DU)")
            ax.set_title(f"DRO→GEO: {n_sel} 条转移轨道")
            ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")
            set_equal_aspect_3d(ax, dro_orbit.states[:, :3])

        _save_or_show(fig, args)
    else:
        if args.time_dv:
            times_all, dvs_all = feasible_transfer_time_and_dv(rows)
            n_feas = len(times_all)
            idx = subsample_indices(n_feas, args.max_points, args.seed)
            fig, ax = plt.subplots(figsize=(10, 6))
            plot_transfer_time_delta_v(ax, times_all[idx], dvs_all[idx], "DRO→GEO:")
            fig.tight_layout()
            _save_or_show(fig, args)
        else:
            alpha_all, dv_all = feasible_alpha_and_departure_dv(rows)
            n_feas = len(alpha_all)
            idx = subsample_indices(n_feas, args.max_points, args.seed)
            fig, ax = plt.subplots(figsize=(10, 6))
            plot_alpha_delta_v(ax, alpha_all[idx], dv_all[idx], "DRO→GEO:")
            fig.tight_layout()
            _save_or_show(fig, args)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += [
            "--max-points", "50000",
            "--seed", "0",
            "--dpi", "150",
            "--idx", "0",
        ]
        logger.debug("使用代码内置调试参数")
    main()
