"""
GEO → DRO 搜索结果可视化

可视化 grid_search_geo_to_dro.py 的输出结果。
支持散点图、3D 转移轨道图和交互式浏览模式。

运行:
    python scripts/transfer/geo_to_dro/plot_search_results_geo_to_dro.py              # alpha vs Δv 散点图
    python scripts/transfer/geo_to_dro/plot_search_results_geo_to_dro.py --time-dv    # 转移时间 vs Δv
    python scripts/transfer/geo_to_dro/plot_search_results_geo_to_dro.py --orbit       # 3D 轨道图
    python scripts/transfer/geo_to_dro/plot_search_results_geo_to_dro.py --interactive # 交互式浏览
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional  # noqa: F401

import numpy as np
import matplotlib

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt

import e2m2e
from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.transfer import load_orbit_from_json
from scripts.utils.common import DU, MU, TU, VU
from scripts.utils.geo import (
    R_GEO,
    EARTH_CENTER,
    geo_circular_velocity_rotating,
    compute_departure_velocity,
    check_collision,
)

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.utils.plot_helpers import apply_standard_plot_config, style_colorbar, subsample_indices

PLOT_CONFIG = apply_standard_plot_config()

# =====================================================================
# 配置 — 默认自动发现最新文件，可用环境变量覆盖
# =====================================================================


# =====================================================================
# 数据加载
# =====================================================================


def load_search_results(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "results" in data:
        return list(data["results"])
    if not isinstance(data, list):
        raise TypeError(f"期望 list 或含 'results' key 的 dict, 实际 {type(data)}")
    return data


def departure_delta_v_norm(state6, alpha):
    """从状态和 alpha 重算出发 Δv。"""
    state = np.asarray(state6, dtype=float)
    v_new = compute_departure_velocity(state, alpha)
    return float(np.linalg.norm(v_new - state[3:]))


def feasible_alpha_and_departure_dv(rows):
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
# 散点图
# =====================================================================


def plot_alpha_delta_v(ax, alpha, delta_v):
    if len(alpha) == 0:
        ax.text(0.5, 0.5, "无可行解", transform=ax.transAxes, ha="center", va="center")
        return
    ax.scatter(alpha, delta_v * VU / 1000, s=6, alpha=0.6, c="steelblue")
    ax.set_xlabel("α")
    ax.set_ylabel("Δv_departure (km/s)")
    ax.set_title("GEO → DRO: α vs Δv_departure")
    ax.grid(True, alpha=0.3)


def plot_transfer_time_delta_v(ax, transfer_time, delta_v):
    if len(transfer_time) == 0:
        ax.text(0.5, 0.5, "无可行解", transform=ax.transAxes, ha="center", va="center")
        return
    sc = ax.scatter(transfer_time * TU, delta_v * VU / 1000, s=6, alpha=0.6,
                    c=transfer_time * TU, cmap="viridis")
    style_colorbar(plt.colorbar(sc, ax=ax, label="转移时间 (天)"), PLOT_CONFIG)
    ax.set_xlabel("转移时间 (天)")
    ax.set_ylabel("Δv_departure (km/s)")
    ax.set_title("GEO → DRO: 转移时间 vs Δv_departure")
    ax.grid(True, alpha=0.3)


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


def _geo_circle_points():
    """GEO 球面在 x-y 平面上的投影圆。"""
    th = np.linspace(0, 2 * np.pi, 200)
    return EARTH_CENTER[0] + R_GEO * np.cos(th), R_GEO * np.sin(th)


# =====================================================================
# 3D 轨道图
# =====================================================================


def _build_dynamics():
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = 1.0 / (24.0 * TU)
    return system, dynamics


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
    gx, gy = _geo_circle_points()
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

    # 地球和月球
    ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
    ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
    ax.text(EARTH_CENTER[0], EARTH_CENTER[1] + 0.03, 0, "地球", fontsize=PLOT_CONFIG.lp_label, ha="center")
    ax.text(1.0 - MU, 0.03, 0, "月球", fontsize=PLOT_CONFIG.lp_label, ha="center")

    # 平动点
    system.compute_libration_points()
    if system.L1 is None or system.L2 is None:
        raise RuntimeError("L1/L2 平动点未计算")
    for lp_name, lp_x in [("L1", system.L1[0]),
                           ("L2", system.L2[0])]:
        ax.scatter(lp_x, 0, 0, color="red", marker="+", s=30, zorder=5)
        ax.text(lp_x, 0.02, 0, lp_name, fontsize=PLOT_CONFIG.lp_label, ha="center", color="red")

    ax.set_xlabel("x (DU)")
    ax.set_ylabel("y (DU)")
    ax.set_zlabel("z (DU)")
    t_disp = actual_transfer_time if actual_transfer_time is not None else transfer_time
    ax.set_title(
        f"GEO→DRO  α={alpha:.4f}  T={t_disp:.2f} TU ({t_disp * TU:.1f}天)\n"
        f"Δv_dep={dv_departure:.4f} VU ({dv_departure * VU:.0f} m/s)"
    )
    ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

    # 等比例轴：三轴范围取数据包围盒的最大跨度，居中对齐
    all_pts = np.concatenate([transfer_states[:, :3], dro_orbit.states[:, :3]])
    mid = all_pts.mean(axis=0)
    half = np.ptp(all_pts, axis=0).max() / 2.0 + 0.1
    ax.set_xlim(mid[0] - half, mid[0] + half)
    ax.set_ylim(mid[1] - half, mid[1] + half)
    ax.set_zlim(mid[2] - half, mid[2] + half)
    ax.set_box_aspect([1, 1, 1])

    return ax


def _select_feasible_indices(feasible_rows, idx_arg, seed=42, max_indices=200):
    n = len(feasible_rows)
    if idx_arg == "all":
        idx = list(range(n))
        if len(idx) > max_indices:
            sel = subsample_indices(len(idx), max_indices, seed)
            idx = [idx[i] for i in sel]
        return idx
    elif idx_arg.startswith("best"):
        parts = idx_arg.split(":")
        top_n = int(parts[1]) if len(parts) > 1 else 10
        by_dv = sorted(range(n), key=lambda i: feasible_rows[i].get("dv_departure", 1e10))
        return by_dv[:top_n]
    elif idx_arg == "random":
        return [np.random.default_rng(seed).integers(0, n)]
    else:
        i = int(idx_arg)
        return [i] if 0 <= i < n else []


# =====================================================================
# 交互式浏览
# =====================================================================


def interactive_browse_by_time(feasible_rows, dro_orbit, system, dynamics):
    """按转移时间排序，交互式逐条浏览 GEO→DRO 转移轨道。同一窗口内重绘。"""
    sorted_rows = sorted(feasible_rows, key=lambda r: r.get("transfer_time", 0))
    n = len(sorted_rows)
    current = 0

    if n == 0:
        print("No feasible results to browse")
        return

    plt.ion()
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")

    # 预计算固定元素
    gx, gy = _geo_circle_points()
    dro_x = dro_orbit.states[:, 0]
    dro_y = dro_orbit.states[:, 1]
    dro_z = dro_orbit.states[:, 2]
    system.compute_libration_points()
    if system.L1 is None or system.L2 is None:
        raise RuntimeError("L1/L2 平动点未计算")
    lp_data = [("L1", system.L1[0]), ("L2", system.L2[0])]

    print("\nInteractive browse: GEO -> DRO search results")
    print(f"{n} feasible results, sorted by transfer time")
    print("Commands: Enter=next, q=quit, s N=skip N, j N=jump to #N, r=redraw")

    while 0 <= current < n:
        row = sorted_rows[current]
        alpha = row["alpha"]
        tt = row.get("transfer_time", 0)
        dep_state = row.get("departure_state")
        dv = row.get("dv_departure", 0)

        print(f"\n[{current+1}/{n}] a={alpha:.4f}, T_search={tt:.2f} TU ({tt * TU:.1f} d), "
              f"dv={dv:.4f} VU ({dv * VU:.0f} m/s), "
              f"min_dist={row.get('min_distance', 'N/A')}")

        if dep_state is None:
            print("  no departure state, skip")
            current += 1
            continue

        try:
            transfer_states, times = _reintegrate_transfer(dynamics, dep_state, alpha, tt, dro_orbit=dro_orbit)
        except Exception as e:
            print(f"  integration failed: {e}")
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
        # 天体
        ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
        ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
        ax.text(EARTH_CENTER[0], EARTH_CENTER[1] + 0.03, 0, "Earth", fontsize=PLOT_CONFIG.lp_label, ha="center")
        ax.text(1.0 - MU, 0.03, 0, "Moon", fontsize=PLOT_CONFIG.lp_label, ha="center")
        # 平动点
        for lp_name, lp_x in lp_data:
            ax.scatter(lp_x, 0, 0, color="red", marker="+", s=30, zorder=5)
            ax.text(lp_x, 0.02, 0, lp_name, fontsize=PLOT_CONFIG.lp_label, ha="center", color="red")

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
        mid = all_pts.mean(axis=0)
        half = np.ptp(all_pts, axis=0).max() / 2.0 + 0.1
        ax.set_xlim(mid[0] - half, mid[0] + half)
        ax.set_ylim(mid[1] - half, mid[1] + half)
        ax.set_zlim(mid[2] - half, mid[2] + half)
        ax.set_box_aspect([1, 1, 1])

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
    print("退出浏览")


# =====================================================================
# main
# =====================================================================


def main():
    parser = argparse.ArgumentParser(description="GEO → DRO 搜索结果可视化")
    parser.add_argument("--file", type=str, default=None, help="搜索结果 JSON 路径")
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

    # 搜索结果文件: CLI > 环境变量 > 自动发现
    if args.file:
        results_file = Path(args.file)
    else:
        env_val = os.environ.get("SEARCH_RESULTS_FILE")
        if env_val:
            results_file = Path(env_val)
        else:
            candidates = sorted((project_root / "output/transfer").glob("search_geo_dro_*.json"))
            if not candidates:
                print("未找到搜索结果文件，请用 --file 指定")
                return
            results_file = candidates[-1]
            print(f"自动发现: {results_file}")

    rows = load_search_results(results_file)
    feasible_rows = [r for r in rows if r.get("is_feasible")]
    print(f"加载 {len(rows)} 条记录, {len(feasible_rows)} 个可行解")

    # DRO 文件: CLI > 环境变量 > 自动发现
    dro_file_env = os.environ.get("DRO_FILE")
    if dro_file_env:
        dro_file = Path(dro_file_env)
    else:
        dro_files = sorted((project_root / "output/dro").glob("dro_31_*.json"))
        if not dro_files:
            print("找不到 DRO 文件")
            return
        dro_file = dro_files[-1]
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
        indices = _select_feasible_indices(feasible_rows, args.idx,
                                           seed=args.seed, max_indices=args.max_points)
        dynamics = CR3BP_Dynamics(system=system)
        dynamics.integrator = "DOP853"
        dynamics.rtol = 1e-12
        dynamics.atol = 1e-12
        dynamics.max_step = 1.0 / (24.0 * TU)

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
                dep_state, dv, alpha, tt, system, fig, ax,
                actual_transfer_time=times[-1],
            )

            if args.save:
                save_path = args.save
                base, ext = os.path.splitext(save_path)
                save_path = f"{base}_{i}{ext}" if len(indices) > 1 else save_path
                fig.savefig(save_path, dpi=args.dpi, bbox_inches="tight")
                print(f"图片保存至: {save_path}")

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
        plot_transfer_time_delta_v(ax, tt, dv)
        fig.tight_layout()
        if args.save:
            fig.savefig(args.save, dpi=args.dpi, bbox_inches="tight")
            print(f"图片保存至: {args.save}")
        else:
            plt.show()

    else:
        alpha_all, dv_all = feasible_alpha_and_departure_dv(rows)
        n = len(alpha_all)
        idx = subsample_indices(n, args.max_points, args.seed)
        alpha = alpha_all[idx]
        dv = dv_all[idx]
        fig, ax = plt.subplots(figsize=(10, 6))
        plot_alpha_delta_v(ax, alpha, dv)
        fig.tight_layout()
        if args.save:
            fig.savefig(args.save, dpi=args.dpi, bbox_inches="tight")
            print(f"图片保存至: {args.save}")
        else:
            plt.show()


if __name__ == "__main__":
    main()
