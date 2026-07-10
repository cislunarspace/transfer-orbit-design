"""plot_search_results_dro_to_ro 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.transfer.dro_to_ro.plot_search_results_dro_to_ro --help
"""


from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

import e2m2e
import matplotlib
import numpy as np
from e2m2e.core import CR3BP_System, Orbit
from e2m2e.transfer import TransferSearch, load_orbit_from_json
from matplotlib.axes import Axes
from tod.commons.constants import MU, TU, VU
from tod.commons.common import find_project_root, safe_resolve_within
from tod.plot.config import apply_standard_plot_config, subsample_indices
from tod.plot.transfer.common import (
    departure_delta_v_norm,
    feasible_alpha_and_departure_dv,
    load_search_results,
    plot_alpha_delta_v,
    plot_transfer_time_delta_v,
    select_feasible_indices,
    plot_celestial_bodies,
    set_equal_aspect_3d,
    compute_departure_velocity as _compute_departure_velocity,
)

project_root = find_project_root(Path(__file__))

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt  # noqa: E402

PLOT_CONFIG = apply_standard_plot_config()
logger = logging.getLogger(__name__)

# =============================================================================
# 数据文件：grid_search 输出的 JSON
# =============================================================================
RESULTS_JSON = (
    project_root / "output/transfer/search_results_200-100-0.5-2.5-22.998482_3857848453.json"
)
# 示例: RESULTS_JSON = project_root / "output/transfer/search_results_10-101-0.5-2.5-2.298634_3857123456.json"

# 轨道数据文件（用于转移轨道积分和绘图）
DRO_FILE = project_root / "output/dro/dro_31_3857693511.json"
RO_FILE = project_root / "output/ro/ro_31_3857693516.json"


def compute_actual_transfer_time(r: dict, dt: float = 1.0 / (24.0 * TU)) -> float:
    """
    计算实际转移时间。

    e2m2e grid_search 输出的 transfer_time 是 max_transfer_time（积分总时长），
    而非实际到达目标轨道的时间。这里用 min_distance_idx * dt 来估算真实转移时间。
    """
    transfer_time = r.get("transfer_time")
    if transfer_time is None:
        return float("nan")
    # 使用 min_distance_idx 和 dt 计算真实转移时间
    min_idx = r.get("min_distance_idx")
    if min_idx is not None and min_idx >= 0:
        return float(min_idx) * dt
    # 如果没有 min_distance_idx，使用原始的 transfer_time（这不应该发生）
    return float(transfer_time)


def feasible_transfer_time_and_dv(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """仅可行解；返回 (transfer_times, dv_departure)。

    与 common 版本不同：这里使用 compute_actual_transfer_time 计算实际转移时间，
    通过 min_distance_idx * dt 而非原始 transfer_time。
    """
    times: list[float] = []
    dvs: list[float] = []
    DT = 1.0 / (24.0 * TU)
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
            actual_time = compute_actual_transfer_time(r, DT)
            if np.isfinite(actual_time):
                times.append(actual_time)
                dvs.append(dv)
    return np.asarray(times, dtype=np.float64), np.asarray(dvs, dtype=np.float64)


def _build_transfer_search() -> TransferSearch:
    """构建并配置 TransferSearch 实例（积分器参数与 grid_search_dro_to_ro.py 一致）。"""
    DT = 1.0 / (24.0 * TU)
    system = e2m2e.core.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.CR3BP_Dynamics(system=system)
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
        system = e2m2e.core.CR3BP_System(mu=mu, primary="earth", secondary="moon")
        dynamics = e2m2e.core.CR3BP_Dynamics(system=system)
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
            transfer_states, _ = ts._forward_integrate(initial_state, max_transfer_time, DT)

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


def _find_closest_orbit_phase_idx(transfer_states: np.ndarray, orbit: Orbit) -> int:
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


def _plot_single_transfer_orbit(
    departure_orbit: Orbit,
    arrival_orbit: Orbit,
    transfer_states: np.ndarray,
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
    """绘制单条 DRO→RO 转移轨道 3D 示意图。"""
    if ax is None:
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

    arrival_point = arrival_orbit.states[arrival_orbit_phase_idx]

    # DRO 出发轨道
    ax.plot(departure_orbit.states[:, 0], departure_orbit.states[:, 1],
            departure_orbit.states[:, 2], color="royalblue", lw=0.8, label="DRO")

    # RO 到达轨道
    ax.plot(arrival_orbit.states[:, 0], arrival_orbit.states[:, 1],
            arrival_orbit.states[:, 2], color="seagreen", lw=0.8, label="RO")

    # 转移轨迹
    ax.plot(transfer_states[:, 0], transfer_states[:, 1], transfer_states[:, 2],
            color="crimson", lw=1.2, label="转移轨道")

    # 出发点
    dep_pos = np.asarray(departure_state, dtype=float)[:3]
    ax.scatter(*dep_pos, color="green", s=40, zorder=5, label="出发点")

    # 到达点
    ax.scatter(*arrival_point[:3], color="orange", s=40, marker="s", zorder=5, label="终点")

    # 地球、月球、平动点（共享组件）
    plot_celestial_bodies(ax, system, PLOT_CONFIG)

    ax.set_xlabel("x (DU)")
    ax.set_ylabel("y (DU)")
    ax.set_zlabel("z (DU)")

    dv_dep_phys = dv_departure * VU / 1000
    dv_ins_phys = dv_insertion * VU / 1000
    ax.set_title(
        f"DRO→RO  α={alpha:.4f}  T={transfer_time:.2f} TU ({transfer_time * TU:.1f}天)\n"
        f"Δv_dep={dv_dep_phys:.4f} km/s  Δv_ins={dv_ins_phys:.4f} km/s"
    )
    ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

    # 等比例轴（共享组件）
    all_pts = np.concatenate([transfer_states[:, :3], departure_orbit.states[:, :3],
                              arrival_orbit.states[:, :3]])
    set_equal_aspect_3d(ax, all_pts)

    return ax


def main() -> None:
    """执行脚本主流程。
    
    Returns:
        None。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    parser = argparse.ArgumentParser(
        description="绘制 grid_search 结果（α–Δv 散点图 / 转移轨道示意图）"
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
    args = parser.parse_args()

    path = Path(args.file).expanduser().resolve() if args.file else Path(RESULTS_JSON).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    # 路径遍历防护：仅在用户通过 --file 指定路径时检查
    if args.file and safe_resolve_within(args.file, project_root) is None:
        logger.info(f"安全拒绝: {args.file} 不在项目根目录 {project_root} 内")
        sys.exit(1)
    logger.info(f"读取: {path}")

    rows = load_search_results(path)
    feasible_rows = [r for r in rows if r.get("is_feasible")]
    logger.info(f"总行数={len(rows)}，可行解={len(feasible_rows)}")

    if args.orbit:
        # ── 转移轨道示意图 ──────────────────────────────────────────────────
        dro_path = Path(DRO_FILE).expanduser().resolve()
        ro_path = Path(RO_FILE).expanduser().resolve()
        if not dro_path.is_file():
            raise FileNotFoundError(f"DRO 轨道文件不存在: {dro_path}")
        if not ro_path.is_file():
            raise FileNotFoundError(f"RO 轨道文件不存在: {ro_path}")

        logger.info(f"加载 DRO: {dro_path}")
        logger.info(f"加载 RO: {ro_path}")
        dro_orbit = load_orbit_from_json(str(dro_path))
        ro_orbit = load_orbit_from_json(str(ro_path))

        # 构建 system（用于 OrbitVisualizer 和子进程）
        ts_dummy = _build_transfer_search()
        system = ts_dummy.system

        sel_indices = select_feasible_indices(
            feasible_rows, args.idx, args.seed, max_indices=args.max_points
        )
        n_sel = len(sel_indices)

        # 并行积分（子进程各自构建积分器，不依赖外部对象）
        n_workers = args.n_workers
        use_parallel = n_sel > 1
        if use_parallel:
            logger.info(f"并行积分：{n_sel} 条轨道，n_workers={n_workers or 'CPU 核数'}...")
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
                    logger.info(f"  [{len(results)}/{n_sel}] α={alpha:.3f} 完成")
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
                else (float(np.linalg.norm(dv_arr)) if dv_arr is not None else float("nan"))
            )
            logger.info(f"积分转移轨道（α={alpha}, T={transfer_time:.3f} TU）...")
            transfer_states, _ = _reintegrate_transfer(
                ts_dummy, departure_state, alpha, float(transfer_time)
            )
            arrival_phase_idx = _find_closest_orbit_phase_idx(transfer_states, ro_orbit)
            results = {0: (transfer_states, alpha, dv_departure)}

        if n_sel == 1:
            transfer_states, alpha, dv_departure = results[0]
            departure_state = np.asarray(
                feasible_rows[sel_indices[0]]["departure_state"], dtype=np.float64
            )
            arrival_phase_idx = _find_closest_orbit_phase_idx(transfer_states, ro_orbit)
            dv_insertion_raw = feasible_rows[sel_indices[0]].get("dv_insertion")
            dv_insertion = float(dv_insertion_raw) if dv_insertion_raw is not None else float("nan")

            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")
            ax = _plot_single_transfer_orbit(
                departure_orbit=dro_orbit,
                arrival_orbit=ro_orbit,
                transfer_states=transfer_states,
                departure_state=departure_state,
                arrival_orbit_phase_idx=arrival_phase_idx,
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

            # DRO 出发轨道
            ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1],
                    dro_orbit.states[:, 2], color="royalblue", lw=0.8, label="DRO")
            # RO 到达轨道
            ax.plot(ro_orbit.states[:, 0], ro_orbit.states[:, 1],
                    ro_orbit.states[:, 2], color="seagreen", lw=0.8, label="RO")

            cmap = matplotlib.colormaps["plasma"]
            for cm_idx in range(n_sel):
                transfer_states, alpha, dv_departure = results[cm_idx]
                sel_idx = sel_indices[cm_idx]
                departure_state = np.asarray(
                    feasible_rows[sel_idx]["departure_state"], dtype=np.float64
                )

                color = cmap(cm_idx / max(n_sel - 1, 1))
                ax.plot(transfer_states[:, 0], transfer_states[:, 1],
                        transfer_states[:, 2], color=color, lw=1.2, alpha=0.7)
                ax.scatter(*departure_state[:3], color=color, s=30, alpha=0.8)

            # 地球、月球、平动点（共享组件）
            plot_celestial_bodies(ax, system, PLOT_CONFIG)

            ax.set_xlabel("x (DU)")
            ax.set_ylabel("y (DU)")
            ax.set_zlabel("z (DU)")
            ax.set_title(f"DRO→RO: {n_sel} 条转移轨道")
            ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

            # 等比例轴（共享组件）
            all_pts = np.concatenate([dro_orbit.states[:, :3], ro_orbit.states[:, :3]])
            set_equal_aspect_3d(ax, all_pts)

        if args.save:
            png = Path(args.save).expanduser().resolve()
            if png.suffix.lower() != ".png":
                png = png.with_suffix(".png")
            png.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
            logger.info(f"Saved: {png}")
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
            plot_transfer_time_delta_v(ax, times, dvs, "DRO→RO:")
            fig.tight_layout()

            if args.save:
                png = Path(args.save).expanduser().resolve()
                if png.suffix.lower() != ".png":
                    png = png.with_suffix(".png")
                png.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
                logger.info(f"Saved: {png}")
            else:
                plt.show()
            plt.close(fig)
        else:
            # ── α–Δv 散点图（原有功能）─────────────────────────────────────
            alpha_all, dv_all = feasible_alpha_and_departure_dv(rows)
            n_feas = len(alpha_all)
            idx = subsample_indices(n_feas, args.max_points, args.seed)
            alpha = alpha_all[idx]
            dv = dv_all[idx]

            fig, ax = plt.subplots(figsize=(10, 6))
            plot_alpha_delta_v(ax, alpha, dv, "DRO→RO:")
            fig.tight_layout()

            if args.save:
                png = Path(args.save).expanduser().resolve()
                if png.suffix.lower() != ".png":
                    png = png.with_suffix(".png")
                png.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
                logger.info(f"Saved: {png}")
            else:
                plt.show()
            plt.close(fig)


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--max-points", "50000",                     # 散点最多绘制的可行点数
            "--seed", "0",                                # 子采样随机种子
            "--dpi", "150",                               # 图像 DPI
            "--idx", "0",                                 # 选择可行解索引
        ]
        logger.debug("使用代码内置调试参数")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_search_results_dro_to_ro',
    description='绘制搜索结果',
    script_path='tod/plot/transfer/dro_to_ro/plot_search_results_dro_to_ro.py',
    output_dir='output/transfer',
    group_label='DRO→RO',
    cli_params=[
        CliParam('--file', '搜索结果文件', 'str', '', help='搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='绘制转移时间 vs Δv 散点图。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', '0', help='整数索引、best、best:N、random 或 all。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大散点数', 'int', '50000', help='散点子采样上限，避免过多点导致卡顿。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率。', advanced=True),
        CliParam('--n-workers', '并行 worker 数', 'int', '', help='并行积分进程数，仅 --orbit 模式。', advanced=True),
    ],
)
