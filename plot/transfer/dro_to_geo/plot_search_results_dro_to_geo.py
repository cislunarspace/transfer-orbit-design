# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""plot_search_results_dro_to_geo 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、
稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；
输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m plot.transfer.dro_to_geo.plot_search_results_dro_to_geo --help
"""

from __future__ import annotations

import argparse
import logging
import os
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
from e2m2e.algorithm.dynamics import CR3BP_System, Orbit
from e2m2e.transfer import TransferSearch, load_orbit_from_json

from plot._artifact_helpers import find_latest_single_dro
from plot.config import apply_standard_plot_config, subsample_indices
from plot.transfer.common import (
    compute_departure_velocity as _compute_departure_velocity,
)
from plot.transfer.common import (
    feasible_alpha_and_departure_dv,
    feasible_time_dv_total,
    feasible_transfer_time_and_dv,
    geo_circle_points,
    load_search_results,
    plot_alpha_delta_v,
    plot_celestial_bodies,
    plot_transfer_time_delta_v,
    save_or_show,
    select_feasible_indices,
    set_equal_aspect_3d,
)
from src.commons.constants import MU, TU, VU
from src.commons.orbits import R_GEO
from src.commons.paths import find_project_root, safe_resolve_within

project_root = find_project_root(Path(__file__))

try:
    if not os.environ.get("MPLBACKEND"):
        matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt  # noqa: E402

PLOT_CONFIG = apply_standard_plot_config()
logger = logging.getLogger(__name__)

# =============================================================================
# 数据文件
# =============================================================================
RESULTS_JSON = (
    project_root / "output/transfer/search_dro_geo_200-100-0.5-2.5-22.9985_3858323266.json"
)


def _resolve_dro_file(cli_path: str | None) -> Path:
    """DRO 文件解析优先级: CLI --dro-file > env DRO_FILE > output/dro 下最新 dro_*.json。

    与 transfer 搜索脚本保持一致，避免写死过期文件名。
    """
    if cli_path:
        return Path(cli_path).expanduser().resolve()
    env_path = os.environ.get("DRO_FILE")
    if env_path:
        return Path(env_path).expanduser().resolve()
    try:
        return find_latest_single_dro(project_root)
    except FileNotFoundError as exc:
        raise FileNotFoundError(str(exc)) from exc


def _resolve_and_load_dro(cli_path: str | None) -> Orbit:
    dro_path = _resolve_dro_file(cli_path)
    if not dro_path.is_file():
        raise FileNotFoundError(f"DRO 轨道文件不存在: {dro_path}")
    logger.info("加载 DRO: %s", dro_path)
    return load_orbit_from_json(str(dro_path))


def _resolve_truncation(row: dict) -> tuple[int | None, float]:
    """根据 row 的首次可行性字段决定绘图截断位置（F1 切片 + D1 fallback）。

    选择规则（与 issue #71 中 grill 后确认的设计一致）:

    - ``intersection_found == True`` 时，使用 ``first_intersection_idx/time``
      （首次进入 ``intersection_threshold`` 内）。
    - 否则使用 ``first_min_distance_idx/time``（首次进入 ``min_distance_threshold`` 内）。
    - 若解析到的 ``k_star`` 为 ``None`` 或 ``0``（旧 JSON 缺字段 / 出发即在阈值内），
      回退到不截断：``k_star=None``，``t_star = row["transfer_time"]``（全程时间）。

    Returns:
        ``(k_star, t_star)``：

        * ``k_star``：切片上界（含），``None`` 表示不截断。
        * ``t_star``：标题中显示的转移时间（TU）。
    """
    total_T = float(row["transfer_time"])
    if row.get("intersection_found"):
        k = row.get("first_intersection_idx")
        t = row.get("first_intersection_time")
    else:
        k = row.get("first_min_distance_idx")
        t = row.get("first_min_distance_time")

    # D1 fallback: 字段缺失或 idx=0（出发即在阈值内 / 旧 JSON）
    if k is None or int(k) == 0 or t is None:
        return None, total_T
    return int(k), float(t)


def _build_transfer_search() -> TransferSearch:
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
        tangential = np.array([-pos[1], pos[0], 0.0]) / max(r_xy, 1e-10)
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

    ax.plot(
        departure_orbit.states[:, 0],
        departure_orbit.states[:, 1],
        departure_orbit.states[:, 2],
        color="royalblue",
        lw=0.8,
        label="DRO",
    )
    ax.plot(
        transfer_states[:, 0],
        transfer_states[:, 1],
        transfer_states[:, 2],
        color="crimson",
        lw=1.2,
        label="转移轨道",
    )

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
    """启动交互式浏览流程。

    Args:
        feasible_rows: 调用方传入的参数值。
        dro_orbit: 调用方传入的参数值。
        system: 调用方传入的参数值。
        ts: 调用方传入的参数值。

    Returns:
        None。
    """
    plt.ion()

    sorted_rows = sorted(feasible_rows, key=lambda r: float(r.get("transfer_time", float("inf"))))
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
            np.asarray(dv_dep_raw, dtype=np.float64).ravel() if dv_dep_raw is not None else None
        )
        dv_departure = (
            float(dv_arr[0])
            if dv_arr is not None and dv_arr.size == 1
            else (float(np.linalg.norm(dv_arr)) if dv_arr is not None else float("nan"))
        )
        dv_insertion_raw = row.get("dv_insertion")
        dv_insertion = float(dv_insertion_raw) if dv_insertion_raw is not None else float("nan")

        logger.info("[%d/%d] 转移轨道信息:", current_idx + 1, n)
        logger.info("  α = %.4f", alpha)
        logger.info("  转移时间 = %.4f TU", transfer_time)
        logger.info("  Δv_dep = %.6f (%.1f m/s)", dv_departure, dv_departure * VU * 1000)
        logger.info("  Δv_ins = %.6f (%.1f m/s)", dv_insertion, dv_insertion * VU * 1000)
        if np.isfinite(dv_departure) and np.isfinite(dv_insertion):
            dv_total = dv_departure + dv_insertion
            logger.info("  Δv_total = %.6f (%.1f m/s)", dv_total, dv_total * VU * 1000)

        # F1 切片：积分到 max_transfer_time，按 k_star 切到首次可行点
        k_star, t_star = _resolve_truncation(row)
        transfer_states, _ = _reintegrate_transfer(ts, departure_state, alpha, transfer_time)
        if k_star is not None:
            transfer_states = transfer_states[: k_star + 1]
            logger.info("  截断到首次可行点: k*=%d, t*=%.4f TU", k_star, t_star)

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
            transfer_time=t_star,
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


def _resolve_figsize_cm(arg: str | None) -> tuple[float, float] | None:
    """将 '--figsize' 参数（厘米）转为 matplotlib 英寸尺寸。

    支持 '宽,高' 或单值（正方形）。返回 None 表示用默认 10x6 英寸。
    """
    if not arg:
        return None
    parts = [float(x) for x in arg.replace("，", ",").split(",")]
    if len(parts) == 1:
        parts = [parts[0], parts[0]]
    if len(parts) != 2:
        raise ValueError(f"--figsize 需 '宽,高'（厘米），收到 {arg!r}")
    w, h = parts
    return (w / 2.54, h / 2.54)


def main() -> None:

    parser = argparse.ArgumentParser(
        description="绘制 grid_search_dro_to_geo 结果（α–Δv 散点图 / 转移轨道示意图）"
    )
    parser.add_argument("--file", type=str, default=None, help="搜索结果 JSON 路径")
    parser.add_argument(
        "--dro-file",
        type=str,
        default=None,
        help="DRO 轨道 JSON 路径；不传则按 env DRO_FILE / output/dro 最新 dro_*.json 自动发现",
    )
    parser.add_argument("--save", type=str, default=None, help="保存 PNG 路径")
    parser.add_argument("--max-points", type=int, default=50000, help="散点最多可行点数")
    parser.add_argument("--seed", type=int, default=0, help="子采样随机种子")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--orbit", action="store_true", help="绘制转移轨道示意图")
    parser.add_argument(
        "--idx", type=str, default="0", help="选择可行解：整数索引/best/best:N/random/all"
    )
    parser.add_argument("--n-workers", type=int, default=None, help="并行积分 worker 数")
    parser.add_argument("--time-dv", action="store_true", help="绘制转移时间 vs Δv 散点图")
    parser.add_argument("--interactive", action="store_true", help="交互式逐条浏览")
    parser.add_argument(
        "--no-show", action="store_true", help="生成图像后不弹窗显示（GUI 后台运行）"
    )
    parser.add_argument(
        "--figsize",
        type=str,
        default=None,
        help="图尺寸（厘米），格式 '宽,高'，如 '8.5,6'；不传则使用默认 10x6 英寸。",
    )
    parser.add_argument(
        "--color-by",
        type=str,
        default="transfer_time",
        choices=["transfer_time", "total_dv"],
        help="散点着色量：transfer_time（默认，转移时间）或 total_dv（总 Δv）。",
    )
    parser.add_argument("--scatter-size", type=float, default=10.0, help="散点大小，默认 10。")
    parser.add_argument("--scatter-alpha", type=float, default=0.7, help="散点透明度，默认 0.7。")
    parser.add_argument("--no-title", action="store_true", help="不显示图标题（论文配图用）。")
    parser.add_argument("--caption", type=str, default=None, help="图注文字，置于图下方")
    args = parser.parse_args()

    path = (
        Path(args.file).expanduser().resolve()
        if args.file
        else Path(RESULTS_JSON).expanduser().resolve()
    )
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
        dro_orbit = _resolve_and_load_dro(args.dro_file)
        ts = _build_transfer_search()
        interactive_browse_by_time(feasible_rows, dro_orbit, ts.system, ts)
    elif args.orbit:
        dro_orbit = _resolve_and_load_dro(args.dro_file)
        ts_dummy = _build_transfer_search()
        system = ts_dummy.system

        sel_indices = select_feasible_indices(
            feasible_rows, args.idx, args.seed, max_indices=args.max_points
        )
        n_sel = len(sel_indices)

        use_parallel = n_sel > 1
        if use_parallel:
            logger.info("并行积分：%d 条轨道，n_workers=%s...", n_sel, args.n_workers or "CPU 核数")
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
                np.asarray(dv_dep_raw, dtype=np.float64).ravel() if dv_dep_raw is not None else None
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
            row0 = feasible_rows[sel_indices[0]]
            departure_state = np.asarray(row0["departure_state"], dtype=np.float64)
            dv_ins_raw = row0.get("dv_insertion")
            dv_insertion = float(dv_ins_raw) if dv_ins_raw is not None else float("nan")

            # F1 切片：worker 积分到 max_transfer_time，主进程按 row 切到首次可行点
            k_star, t_star = _resolve_truncation(row0)
            if k_star is not None and transfer_states is not None:
                transfer_states = transfer_states[: k_star + 1]
                logger.info("截断到首次可行点: k*=%d, t*=%.4f TU", k_star, t_star)

            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")
            _plot_single_transfer_orbit(
                departure_orbit=dro_orbit,
                transfer_states=transfer_states,
                departure_state=departure_state,
                dv_departure=dv_departure,
                dv_insertion=dv_insertion,
                transfer_time=t_star,
                alpha=alpha,
                system=system,
                fig=fig,
                ax=ax,
            )
        else:
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")

            ax.plot(
                dro_orbit.states[:, 0],
                dro_orbit.states[:, 1],
                dro_orbit.states[:, 2],
                color="royalblue",
                lw=0.8,
                label="DRO",
            )
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
                row_i = feasible_rows[sel_idx]
                departure_state = np.asarray(row_i["departure_state"], dtype=np.float64)
                # F1 切片：worker 积分到 max_transfer_time，主进程按 row 切到首次可行点
                k_star, _t_star = _resolve_truncation(row_i)
                if k_star is not None:
                    transfer_states = transfer_states[: k_star + 1]
                color = cmap(cm_idx / max(n_sel - 1, 1))
                ax.plot(
                    transfer_states[:, 0],
                    transfer_states[:, 1],
                    transfer_states[:, 2],
                    color=color,
                    lw=1.2,
                    alpha=0.7,
                )
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

        save_or_show(fig, args)
    else:
        figsize = _resolve_figsize_cm(args.figsize) or (10, 6)
        title = "" if args.no_title else None
        if args.time_dv:
            if args.color_by == "total_dv":
                times_all, dvs_all, totals_all = feasible_time_dv_total(rows)
                color_all = totals_all * VU / 1000
                colorbar_label = "总 Δv (km/s)"
            else:
                times_all, dvs_all = feasible_transfer_time_and_dv(rows)
                color_all = None
                colorbar_label = "转移时间 (天)"
            n_feas = len(times_all)
            idx = subsample_indices(n_feas, args.max_points, args.seed)
            fig, ax = plt.subplots(figsize=figsize)
            plot_transfer_time_delta_v(
                ax,
                times_all[idx],
                dvs_all[idx],
                "DRO→GEO:",
                scatter_size=args.scatter_size,
                scatter_alpha=args.scatter_alpha,
                color=(color_all[idx] if color_all is not None else None),
                colorbar_label=colorbar_label,
                title=title,
            )
            fig.tight_layout()
            if args.caption:
                fig.text(0.5, -0.02, args.caption, ha="center", va="top", fontsize=PLOT_CONFIG.tick)
            save_or_show(fig, args)
        else:
            alpha_all, dv_all = feasible_alpha_and_departure_dv(rows)
            n_feas = len(alpha_all)
            idx = subsample_indices(n_feas, args.max_points, args.seed)
            fig, ax = plt.subplots(figsize=figsize)
            plot_alpha_delta_v(ax, alpha_all[idx], dv_all[idx], "DRO→GEO:")
            fig.tight_layout()
            if args.caption:
                fig.text(0.5, -0.02, args.caption, ha="center", va="top", fontsize=PLOT_CONFIG.tick)
            save_or_show(fig, args)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += [
            "--max-points",
            "50000",
            "--seed",
            "0",
            "--dpi",
            "150",
            "--idx",
            "0",
        ]
        logger.debug("使用代码内置调试参数")
    main()
