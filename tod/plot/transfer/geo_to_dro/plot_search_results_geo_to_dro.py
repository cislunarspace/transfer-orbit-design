"""plot_search_results_geo_to_dro 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.transfer.geo_to_dro.plot_search_results_geo_to_dro --help
"""


import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional  # noqa: F401

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

import matplotlib
import numpy as np
from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from tod.commons.orbits import (
    R_GEO,
    EARTH_CENTER,
    geo_circular_velocity_rotating,
    compute_departure_velocity,
)
from e2m2e.transfer import load_orbit_from_json
from tod.commons.constants import MU, TU, VU
from tod.commons.common import find_project_root
from tod.cli.input_file import (
    InputFileRequest,
    InputResolutionError,
    resolve_input_file,
)
from tod.plot.config import apply_standard_plot_config, subsample_indices
from tod.plot.transfer.common import (
    load_search_results,
    plot_alpha_delta_v,
    plot_transfer_time_delta_v,
    select_feasible_indices,
    geo_circle_points,
    build_transfer_dynamics,
    plot_celestial_bodies,
    set_equal_aspect_3d,
)

project_root = find_project_root(Path(__file__))

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt  # noqa: E402

PLOT_CONFIG = apply_standard_plot_config()
logger = logging.getLogger(__name__)

# =====================================================================
# 配置 — 默认自动发现最新文件，可用环境变量覆盖
# =====================================================================


# =====================================================================
# 数据加载 — departure_delta_v_norm 使用 geo 模块的 compute_departure_velocity
# =====================================================================


def departure_delta_v_norm(state6, alpha):
    """从状态和 alpha 重算出发 Δv。"""
    state = np.asarray(state6, dtype=float)
    v_new = compute_departure_velocity(state, alpha)
    return float(np.linalg.norm(v_new - state[3:]))


def feasible_alpha_and_departure_dv(rows):
    """执行 feasible_alpha_and_departure_dv 对应的处理逻辑。
    
    Args:
        rows: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    alpha_list, dv_list = [], []
    for r in rows:
        if not r.get("is_feasible"):
            continue
        a = r.get("alpha")
        dv = r.get("dv_departure")
        if dv is None and "departure_state" in r and a is not None:
            dv = departure_delta_v_norm(r["departure_state"], a)
        if a is not None and dv is not None:
            alpha_list.append(float(a))
            dv_list.append(float(dv))
    return np.array(alpha_list), np.array(dv_list)


def feasible_transfer_time_and_dv(rows):
    """执行 feasible_transfer_time_and_dv 对应的处理逻辑。
    
    Args:
        rows: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    tt_list, dv_list = [], []
    for r in rows:
        if not r.get("is_feasible"):
            continue
        tt = r.get("transfer_time")
        dv = r.get("dv_departure")
        if dv is None and "departure_state" in r and "alpha" in r:
            dv = departure_delta_v_norm(r["departure_state"], r["alpha"])
        if tt is not None and dv is not None:
            tt_list.append(float(tt))
            dv_list.append(float(dv))
    return np.array(tt_list), np.array(dv_list)


# =====================================================================
# GEO 轨道和辅助
# =====================================================================


def generate_geo_orbit(n_points=500):
    """生成 GEO 近似圆轨道状态（仅位置用于绘图）。"""
    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    states = np.zeros((n_points, 6))
    for i, th in enumerate(theta):
        x = EARTH_CENTER[0] + R_GEO * np.cos(th)
        y = R_GEO * np.sin(th)
        pos = np.array([x, y, 0.0])
        vel = geo_circular_velocity_rotating(pos)
        states[i] = [x, y, 0.0, vel[0], vel[1], vel[2]]
    return states


# =====================================================================
# 3D 轨道图
# =====================================================================


def _find_approach_index(transfer_states, dro_orbit):
    """找到转移轨道上最接近 DRO 轨道的点的索引。"""
    traj_pos = transfer_states[:, :3]
    dro_pos = dro_orbit.states[:, :3]

    min_dist_sq = float("inf")
    best_idx = 0
    chunk = 500
    for i_start in range(0, len(traj_pos), chunk):
        i_end = min(i_start + chunk, len(traj_pos))
        diff = traj_pos[i_start:i_end, np.newaxis, :] - dro_pos[np.newaxis, :, :]
        dist_sq = np.sum(diff ** 2, axis=2)
        flat_idx = np.argmin(dist_sq)
        ci, _ = np.unravel_index(flat_idx, dist_sq.shape)
        if dist_sq.flat[flat_idx] < min_dist_sq:
            min_dist_sq = dist_sq.flat[flat_idx]
            best_idx = i_start + ci
    return best_idx


def _reintegrate_transfer(dynamics, departure_state, alpha, max_transfer_time, dro_orbit=None):
    state = np.asarray(departure_state, dtype=float)
    v_new = compute_departure_velocity(state, alpha)
    s0 = np.concatenate([state[:3], v_new])
    step = max(0.01, dynamics.max_step)
    n_steps = int(max_transfer_time / step) + 1
    t_eval = np.linspace(0.0, max_transfer_time, n_steps)
    result = dynamics.propagate(
        initial_state=s0, t_span=(0.0, max_transfer_time),
        t_eval=t_eval, with_stm=False, with_jacobi=False,
    )
    states = result["states"]
    times = result["time"]
    if dro_orbit is not None and len(states) > 1:
        idx = _find_approach_index(states, dro_orbit)
        idx = max(idx, 1)  # 至少保留出发后的第一个点
        return states[: idx + 1], times[: idx + 1]
    return states, times


def _plot_single_transfer_orbit(
    geo_states, dro_orbit, transfer_states, departure_state,
    dv_departure, alpha, transfer_time, system, fig, ax,
    actual_transfer_time=None,
):
    """绘制单条 GEO→DRO 转移轨道（截断到最近 DRO 的点）。"""
    # GEO 圆
    gx, gy = geo_circle_points()
    ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")

    # DRO 轨道
    ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1], dro_orbit.states[:, 2],
            color="royalblue", lw=0.8, label="DRO")

    # 转移轨迹
    ax.plot(transfer_states[:, 0], transfer_states[:, 1], transfer_states[:, 2],
            color="crimson", lw=1.2, label="转移轨道")

    # 出发点
    dep_pos = np.asarray(departure_state, dtype=float)[:3]
    ax.scatter(*dep_pos, color="green", s=40, zorder=5, label="出发点")

    # 终点（截断后的最近 DRO 点）
    final_pos = transfer_states[-1, :3]
    ax.scatter(*final_pos, color="orange", s=40, marker="s", zorder=5, label="终点")

    # 地球、月球和平动点
    plot_celestial_bodies(ax, system, PLOT_CONFIG)

    ax.set_xlabel("x (DU)")
    ax.set_ylabel("y (DU)")
    ax.set_zlabel("z (DU)")
    t_disp = actual_transfer_time if actual_transfer_time is not None else transfer_time
    ax.set_title(
        f"GEO→DRO  α={alpha:.4f}  T={t_disp:.2f} TU ({t_disp * TU:.1f}天)\n"
        f"Δv_dep={dv_departure:.4f} VU ({dv_departure * VU:.0f} m/s)"
    )
    ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

    # 等比例轴
    all_pts = np.concatenate([transfer_states[:, :3], dro_orbit.states[:, :3]])
    set_equal_aspect_3d(ax, all_pts)

    return ax


# =====================================================================
# 交互式浏览
# =====================================================================


def interactive_browse_by_time(feasible_rows, dro_orbit, system, dynamics):
    """按转移时间排序，交互式逐条浏览 GEO→DRO 转移轨道。同一窗口内重绘。"""
    sorted_rows = sorted(feasible_rows, key=lambda r: r.get("transfer_time", 0))
    n = len(sorted_rows)
    current = 0

    if n == 0:
        logger.info("No feasible results to browse")
        return

    plt.ion()
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")

    # 预计算固定元素
    gx, gy = geo_circle_points()
    dro_x = dro_orbit.states[:, 0]
    dro_y = dro_orbit.states[:, 1]
    dro_z = dro_orbit.states[:, 2]
    system.compute_libration_points()
    if system.L1 is None or system.L2 is None:
        raise RuntimeError("L1/L2 平动点未计算")

    logger.info("\nInteractive browse: GEO -> DRO search results")
    logger.info(f"{n} feasible results, sorted by transfer time")
    logger.info("Commands: Enter=next, q=quit, s N=skip N, j N=jump to #N, r=redraw")

    while 0 <= current < n:
        row = sorted_rows[current]
        alpha = row["alpha"]
        tt = row.get("transfer_time", 0)
        dep_state = row.get("departure_state")
        dv = row.get("dv_departure", 0)

        logger.info(f"\n[{current+1}/{n}] a={alpha:.4f}, T_search={tt:.2f} TU ({tt * TU:.1f} d), "
              f"dv={dv:.4f} VU ({dv * VU:.0f} m/s), "
              f"min_dist={row.get('min_distance', 'N/A')}")

        if dep_state is None:
            logger.info("  no departure state, skip")
            current += 1
            continue

        try:
            transfer_states, times = _reintegrate_transfer(dynamics, dep_state, alpha, tt, dro_orbit=dro_orbit)
        except Exception as e:
            logger.info(f"  integration failed: {e}")
            current += 1
            continue

        # 清空 axes 并重绘，不关闭窗口
        ax.cla()

        # GEO 圆
        ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")
        # DRO
        ax.plot(dro_x, dro_y, dro_z, color="royalblue", lw=0.8, label="DRO")
        # 转移
        ax.plot(transfer_states[:, 0], transfer_states[:, 1], transfer_states[:, 2],
                color="crimson", lw=1.2, label="Transfer")
        # 出发/到达
        dep_pos = np.asarray(dep_state, dtype=float)[:3]
        ax.scatter(*dep_pos, color="green", s=40, zorder=5, label="Departure")
        ax.scatter(*transfer_states[-1, :3], color="orange", s=40, marker="s", zorder=5, label="Arrival")
        # 天体和平动点
        plot_celestial_bodies(ax, system, PLOT_CONFIG)

        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_zlabel("z (DU)")
        ax.set_title(
            f"[{current+1}/{n}] a={alpha:.4f}  T={times[-1]:.2f} TU ({times[-1] * TU:.1f} d)  "
            f"dv={dv * VU:.0f} m/s",
            fontsize=PLOT_CONFIG.title,
        )
        ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

        # 等比例轴
        dro_pts = np.column_stack([dro_x, dro_y, dro_z])
        all_pts = np.concatenate([transfer_states[:, :3], dro_pts])
        set_equal_aspect_3d(ax, all_pts)

        fig.canvas.draw()
        fig.canvas.flush_events()
        plt.pause(0.05)

        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd == "q":
            break
        elif cmd.startswith("s "):
            try:
                current += int(cmd.split()[1])
            except (ValueError, IndexError):
                current += 1
        elif cmd.startswith("j "):
            try:
                current = max(0, min(int(cmd.split()[1]) - 1, n - 1))
            except (ValueError, IndexError):
                current += 1
        elif cmd == "r":
            pass  # redraw current
        else:
            current += 1

    plt.ioff()
    plt.close(fig)
    logger.info("退出浏览")


# =====================================================================
# main
# =====================================================================


def main():
    """执行脚本主流程。
    
    Returns:
        None。
    """
    parser = argparse.ArgumentParser(description="GEO → DRO 搜索结果可视化", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--file", type=str, default=None, help="搜索结果 JSON 路径")
    parser.add_argument("--auto-latest", action="store_true", help="显式 opt-in：按 mtime 选最新 search_geo_dro_*.json")
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 路径")
    parser.add_argument("--auto-latest-dro", action="store_true", help="显式 opt-in：按 mtime 选最新 dro_<digits>.json")
    parser.add_argument("--save", type=str, default=None, help="保存 PNG 路径；不传则弹窗显示")
    parser.add_argument("--max-points", type=int, default=50000,
                        help="散点最多绘制的可行点数（过多时随机子采样）")
    parser.add_argument("--seed", type=int, default=0, help="子采样随机种子")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--time-dv", action="store_true", help="绘制转移时间 vs Δv 散点图")
    parser.add_argument("--orbit", action="store_true", help="绘制 3D 转移轨道图")
    parser.add_argument("--interactive", action="store_true", help="交互式浏览模式")
    parser.add_argument("--idx", type=str, default="best:10",
                        help="轨道选择: all, best, best:N, random, 或序号")
    args = parser.parse_args()

    # 搜索结果文件: 显式 --file 或 --auto-latest
    parser_obj = parser  # parser.error 需要原始 parser 触发 exit 2
    try:
        results_file = resolve_input_file(
            InputFileRequest(
                explicit_path=Path(args.file) if args.file else None,
                auto_latest=bool(args.auto_latest),
                search_root=project_root / "output/transfer",
                pattern="search_geo_dro_*.json",
                flag="--file",
                auto_latest_flag="--auto-latest",
            )
        )
        logger.info(f"读取: {results_file}")
    except InputResolutionError as exc:
        msg = str(exc)
        if exc.candidates or exc.remaining:
            msg = f"{msg}\n候选 (mtime new→old):\n{exc.format_candidates()}"
        parser_obj.error(msg)
        return  # unreachable; parser.error exits with 2

    rows = load_search_results(results_file)
    feasible_rows = [r for r in rows if r.get("is_feasible")]
    logger.info(f"加载 {len(rows)} 条记录, {len(feasible_rows)} 个可行解")

    # DRO 文件: 显式 --dro-file 或 --auto-latest-dro（与主输入同样走契约）
    try:
        dro_file = resolve_input_file(
            InputFileRequest(
                explicit_path=Path(args.dro_file) if args.dro_file else None,
                auto_latest=bool(args.auto_latest_dro),
                search_root=project_root / "output/dro",
                pattern="dro_*.json",
                flag="--dro-file",
                auto_latest_flag="--auto-latest-dro",
            )
        )
        logger.info(f"DRO: {dro_file}")
    except InputResolutionError as exc:
        msg = str(exc)
        if exc.candidates or exc.remaining:
            msg = f"{msg}\n候选 (mtime new→old):\n{exc.format_candidates()}"
        parser_obj.error(msg)
        return

    dro_orbit = load_orbit_from_json(str(dro_file))
    with open(dro_file) as f:
        dro_data = json.load(f)
    dro_orbit.period = dro_data.get("properties", {}).get("period")

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    if args.interactive:
        dynamics = CR3BP_Dynamics(system=system)
        dynamics.integrator = "DOP853"
        dynamics.rtol = 1e-12
        dynamics.atol = 1e-12
        dynamics.max_step = 1.0 / (24.0 * TU)
        interactive_browse_by_time(feasible_rows, dro_orbit, system, dynamics)

    elif args.orbit:
        indices = select_feasible_indices(feasible_rows, args.idx,
                                           seed=args.seed, max_indices=args.max_points)
        system_dyn, dynamics = build_transfer_dynamics()

        fig = None
        for i in indices:
            row = feasible_rows[i]
            dep_state = row.get("departure_state")
            if dep_state is None:
                continue
            alpha = row["alpha"]
            tt = row.get("transfer_time", 30.0)
            dv = row.get("dv_departure", 0)

            transfer_states, times = _reintegrate_transfer(dynamics, dep_state, alpha, tt, dro_orbit=dro_orbit)

            if fig is not None:
                plt.close(fig)
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")
            _plot_single_transfer_orbit(
                generate_geo_orbit(), dro_orbit, transfer_states,
                dep_state, dv, alpha, tt, system_dyn, fig, ax,
                actual_transfer_time=times[-1],
            )

            if args.save:
                save_path = args.save
                base, ext = os.path.splitext(save_path)
                save_path = f"{base}_{i}{ext}" if len(indices) > 1 else save_path
                fig.savefig(save_path, dpi=args.dpi, bbox_inches="tight")
                logger.info(f"图片保存至: {save_path}")

        if fig is not None:
            if not args.save:
                plt.show()
            plt.close(fig)

    elif args.time_dv:
        tt_all, dv_all = feasible_transfer_time_and_dv(rows)
        n = len(tt_all)
        idx = subsample_indices(n, args.max_points, args.seed)
        tt = tt_all[idx]
        dv = dv_all[idx]
        fig, ax = plt.subplots(figsize=(10, 6))
        plot_transfer_time_delta_v(ax, tt, dv, "GEO → DRO:")
        fig.tight_layout()
        if args.save:
            fig.savefig(args.save, dpi=args.dpi, bbox_inches="tight")
            logger.info(f"图片保存至: {args.save}")
        else:
            plt.show()

    else:
        alpha_all, dv_all = feasible_alpha_and_departure_dv(rows)
        n = len(alpha_all)
        idx = subsample_indices(n, args.max_points, args.seed)
        alpha = alpha_all[idx]
        dv = dv_all[idx]
        fig, ax = plt.subplots(figsize=(10, 6))
        plot_alpha_delta_v(ax, alpha, dv, "GEO → DRO:")
        fig.tight_layout()
        if args.save:
            fig.savefig(args.save, dpi=args.dpi, bbox_inches="tight")
            logger.info(f"图片保存至: {args.save}")
        else:
            plt.show()


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--max-points", "50000",                     # 散点最多绘制的可行点数
            "--seed", "0",                                # 子采样随机种子
            "--dpi", "150",                               # 图像 DPI
            "--idx", "best:10",                           # 轨道选择
        ]
        logger.debug("使用代码内置调试参数")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_search_results_geo_to_dro',
    description='绘制搜索结果',
    script_path='tod/plot/transfer/geo_to_dro/plot_search_results_geo_to_dro.py',
    output_dir='output/transfer',
    group_label='GEO→DRO',
    cli_params=[
        CliParam('--file', '搜索结果文件', 'str', '', help='搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--auto-latest', '自动选最新搜索结果', 'bool', '', help='选最新的 search_geo_dro_*.json；与 --file 互斥。', advanced=True),
        CliParam('--dro-file', 'DRO 轨道文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--auto-latest-dro', '自动选最新 DRO', 'bool', '', help='选最新的 dro_<digits>.json；与 --dro-file 互斥。', advanced=True),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='绘制转移时间 vs Δv 散点图。'),
        CliParam('--interactive', '逐条浏览模式', 'bool', '', help='按转移时间排序逐条浏览。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', 'best:10', help='all、best、best:N、random 或序号。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大散点数', 'int', '50000', help='散点子采样上限，避免过多点导致卡顿。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率。', advanced=True),
    ],
)
