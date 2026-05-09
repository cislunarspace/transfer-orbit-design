"""
GEO → DRO 优化结果可视化

可视化 optimize_geo_to_dro.py 的输出结果。
支持 Δv 汇总图、散点图、3D 转移轨道图和交互式浏览模式。

运行:
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro              # Δv 汇总 + 散点图
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --time-dv    # 转移时间 vs Δv
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --orbit       # 3D 轨道图 (best:5)
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --orbit --idx best:1    # 最优解
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --orbit --idx 0          # 第 0 条
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --orbit --idx all         # 全部
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --orbit --idx best:10     # Δv 最小 10 条
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --orbit --idx random --seed 42
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --interactive             # 交互式浏览
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --save output/transfer/fig.png
    python -m tod.pipelines.transfer.geo_to_dro.plot_optimize_result_geo_to_dro --max-pos-err 50         # 仅显示 pos<50km
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import matplotlib

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.transfer import load_orbit_from_json
from tod.commons.common import DU, MU, TU, VU
from e2m2e.orbits.geo import (
    R_GEO,
    EARTH_CENTER,
    compute_departure_velocity,
)

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tod.commons.plot_helpers import apply_standard_plot_config, style_colorbar

PLOT_CONFIG = apply_standard_plot_config()

# =====================================================================
# 配置
# =====================================================================
DRO_FILE = project_root / "output/dro/dro_31_3857864736.json"


# =====================================================================
# 数据加载
# =====================================================================


def _latest_optimization_json():
    candidates = sorted((project_root / "output/transfer").glob("optimization_geo_dro_*.json"))
    return candidates[-1] if candidates else None


def load_optimization_results(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _collect_nlp_records(data: Dict) -> List[Dict]:
    results = data.get("results", [])
    records = []
    for r in results:
        nlp = r.get("nlp", {})
        rec = {
            "search_index": r.get("search_index", -1),
            "departure_state": r.get("departure_state"),
            "search_alpha": r.get("search_alpha"),
            "search_dv": r.get("search_dv_departure"),
            "success": nlp.get("success", False),
            "alpha": nlp.get("alpha"),
            "transfer_time": nlp.get("transfer_time"),
            "t_ins": nlp.get("t_ins"),
            "delta_v1": nlp.get("delta_v1"),
            "delta_v2": nlp.get("delta_v2"),
            "objective_value": nlp.get("objective_value"),
            "pos_violation": nlp.get("pos_violation"),
            "angle_deg": nlp.get("angle_deg"),
            "message": nlp.get("message", ""),
        }
        records.append(rec)
    return records


# =====================================================================
# 动力学
# =====================================================================


def _build_dynamics():
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = 0.1
    return system, dynamics


def _integrate_transfer(departure_state, alpha, transfer_time, dynamics):
    state = np.asarray(departure_state, dtype=float)
    v_new = compute_departure_velocity(state, alpha)
    s0 = np.concatenate([state[:3], v_new])
    step = max(0.01, dynamics.max_step)
    n_steps = int(transfer_time / step) + 1
    t_eval = np.linspace(0.0, transfer_time, n_steps)
    result = dynamics.propagate(
        initial_state=s0, t_span=(0.0, transfer_time),
        t_eval=t_eval, with_stm=False, with_jacobi=False,
    )
    return result["states"], result["time"]


# =====================================================================
# GEO 辅助
# =====================================================================


def _geo_circle_points():
    th = np.linspace(0, 2 * np.pi, 200)
    return EARTH_CENTER[0] + R_GEO * np.cos(th), R_GEO * np.sin(th)


# =====================================================================
# 图表
# =====================================================================


def plot_dv_summary(records, ax):
    n = len(records)
    if n == 0:
        ax.text(0.5, 0.5, "无数据", transform=ax.transAxes, ha="center")
        return

    x = np.arange(n)
    dv1 = np.array([r.get("delta_v1", 0) or 0 for r in records]) * VU / 1000
    dv2 = np.array([r.get("delta_v2", 0) or 0 for r in records]) * VU / 1000
    total = dv1 + dv2
    success = [r["success"] for r in records]

    w = 0.25
    ax.bar(x - w, dv1, width=w, label="Δv₁ (出发)", color="steelblue")
    ax.bar(x, dv2, width=w, label="Δv₂ (入轨)", color="coral")
    ax.bar(x + w, total, width=w, label="总 Δv", color="seagreen")

    for i, s in enumerate(success):
        if not s:
            ax.axvline(i, color="red", alpha=0.3)

    ax.set_xlabel("结果索引")
    ax.set_ylabel("Δv (km/s)")
    ax.set_title("GEO→DRO: Δv 汇总")
    ax.legend(fontsize=PLOT_CONFIG.legend)
    ax.set_xticks(x)


def plot_dv_scatter(records, ax):
    success = [r for r in records if r["success"]]
    if not success:
        ax.text(0.5, 0.5, "无成功结果", transform=ax.transAxes, ha="center")
        return

    dv1 = np.array([r["delta_v1"] for r in success]) * VU / 1000
    dv2 = np.array([r["delta_v2"] for r in success]) * VU / 1000
    obj = np.array([r["objective_value"] for r in success]) * VU / 1000

    sc = ax.scatter(dv1, dv2, c=obj, cmap="viridis", s=6, alpha=0.6)
    style_colorbar(plt.colorbar(sc, ax=ax, label="总 Δv (km/s)"), PLOT_CONFIG)

    best = min(success, key=lambda r: r["objective_value"])
    ax.annotate(
        f"最优: α={best['alpha']:.4f}\nΔv={best['objective_value'] * VU / 1000:.3f} km/s",
        xy=(best["delta_v1"] * VU / 1000, best["delta_v2"] * VU / 1000),
        fontsize=PLOT_CONFIG.legend, color="red",
        arrowprops=dict(arrowstyle="->", color="red"),
        xytext=(10, 10), textcoords="offset points",
    )

    ax.set_xlabel("Δv₁ (km/s)")
    ax.set_ylabel("Δv₂ (km/s)")
    ax.set_title("GEO→DRO: Δv₁ vs Δv₂")
    ax.grid(True, alpha=0.3)


def plot_transfer_time_vs_dv(records, ax):
    success = [r for r in records if r["success"]]
    if not success:
        ax.text(0.5, 0.5, "无成功结果", transform=ax.transAxes, ha="center")
        return

    tt_days = np.array([r["transfer_time"] * TU for r in success])
    total_dv = np.array([r["objective_value"] * VU / 1000 for r in success])

    sc = ax.scatter(tt_days, total_dv, c=total_dv, cmap="viridis", s=6, alpha=0.6)
    style_colorbar(plt.colorbar(sc, ax=ax, label="总 Δv (km/s)"), PLOT_CONFIG)

    best = min(success, key=lambda r: r["objective_value"])
    ax.annotate(
        f"最优: T={best['transfer_time'] * TU:.1f} 天\nΔv={best['objective_value'] * VU / 1000:.3f} km/s",
        xy=(best["transfer_time"] * TU, best["objective_value"] * VU / 1000),
        fontsize=PLOT_CONFIG.legend, color="red",
        arrowprops=dict(arrowstyle="->", color="red"),
        xytext=(10, 10), textcoords="offset points",
    )

    ax.set_xlabel("转移时间 (天)")
    ax.set_ylabel("总 Δv (km/s)")
    ax.set_title("GEO→DRO: 转移时间 vs 总 Δv")
    ax.grid(True, alpha=0.3)


# =====================================================================
# 3D 轨道
# =====================================================================


def _select_indices(records, idx_arg, seed=42, max_points=200, max_pos_err_km=100.0):
    # 过滤: 成功且位置误差 < max_pos_err_km
    good = []
    for i, r in enumerate(records):
        if not r["success"]:
            continue
        pv = r.get("pos_violation")
        if pv is not None:
            pos_km = np.sqrt(max(0, float(pv))) * DU
            if pos_km > max_pos_err_km:
                continue
        good.append((i, r))

    if not good:
        return []

    if idx_arg == "all":
        indices = [i for i, _ in good]
        if len(indices) > max_points:
            rng = np.random.default_rng(seed)
            sel = rng.choice(len(indices), size=max_points, replace=False)
            indices = [indices[s] for s in sel]
        return indices
    elif idx_arg.startswith("best"):
        parts = idx_arg.split(":")
        top_n = int(parts[1]) if len(parts) > 1 else 5
        by_obj = sorted(good, key=lambda x: x[1]["objective_value"])
        return [i for i, _ in by_obj[:top_n]]
    elif idx_arg == "random":
        rng = np.random.default_rng(seed)
        pick = rng.choice(len(good))
        return [good[pick][0]]
    else:
        i = int(idx_arg)
        return [i] if 0 <= i < len(records) and records[i]["success"] else []


def plot_orbit_3d(records, sel_indices, dro_orbit, system, dynamics, save_path=None, dpi=150):
    if not sel_indices:
        print("无选中轨道")
        return

    sel_records = [records[i] for i in sel_indices]

    if len(sel_records) == 1:
        rec = sel_records[0]
        dep_state = rec["departure_state"]
        alpha = rec["alpha"]
        tt = rec["transfer_time"]

        print(f"积分转移轨道: a={alpha:.6f}, T={tt:.4f} TU ({tt * TU:.1f} d) ...")
        states, times = _integrate_transfer(dep_state, alpha, tt, dynamics)

        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        # GEO 圆
        gx, gy = _geo_circle_points()
        ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")

        # DRO
        ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1], dro_orbit.states[:, 2],
                color="royalblue", lw=0.8, label="DRO")

        # 转移轨道
        ax.plot(states[:, 0], states[:, 1], states[:, 2],
                color="crimson", lw=1.2, label="转移轨道")

        # 出发点和终点
        dep_pos = np.asarray(dep_state, dtype=float)[:3]
        ax.scatter(*dep_pos, color="green", s=40, zorder=5, label="出发点")
        ax.scatter(*states[-1, :3], color="orange", s=40, marker="s", zorder=5, label="终点")

        # 地球月球
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
        dv1_km = rec["delta_v1"] * VU / 1000
        dv2_km = rec["delta_v2"] * VU / 1000
        total_km = rec["objective_value"] * VU / 1000
        ax.set_title(
            f"GEO→DRO  α={alpha:.4f}  T={tt:.2f} TU ({tt * TU:.1f}天)\n"
            f"Δv_dep={dv1_km:.4f} km/s  Δv_ins={dv2_km:.4f} km/s  "
            f"Total={total_km:.4f} km/s"
        )
        ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

        # 等比例轴
        all_pts = np.concatenate([states[:, :3], dro_orbit.states[:, :3]])
        mid = all_pts.mean(axis=0)
        half = np.ptp(all_pts, axis=0).max() / 2.0 + 0.1
        ax.set_xlim(mid[0] - half, mid[0] + half)
        ax.set_ylim(mid[1] - half, mid[1] + half)
        ax.set_zlim(mid[2] - half, mid[2] + half)
        ax.set_box_aspect([1, 1, 1])
    else:
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        # 背景轨道
        gx, gy = _geo_circle_points()
        ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")
        ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1], dro_orbit.states[:, 2],
                color="royalblue", lw=0.8, label="DRO")

        obj_values = [r["objective_value"] for r in sel_records]
        obj_min, obj_max = min(obj_values), max(obj_values)
        obj_range = obj_max - obj_min if obj_max > obj_min else 1.0
        cmap = matplotlib.colormaps["plasma"]

        all_transfer_pts = []
        for rec in sel_records:
            dep_state = rec["departure_state"]
            alpha = rec["alpha"]
            states, _ = _integrate_transfer(dep_state, alpha, rec["transfer_time"], dynamics)
            norm_val = (rec["objective_value"] - obj_min) / obj_range
            color = cmap(norm_val)
            ax.plot(states[:, 0], states[:, 1], states[:, 2], color=color, lw=1.2, alpha=0.7)
            all_transfer_pts.append(states[:, :3])

        # 地球月球
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

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=Normalize(
            vmin=obj_min * VU / 1000, vmax=obj_max * VU / 1000))
        sm.set_array([])
        style_colorbar(plt.colorbar(sm, ax=ax, label="总 Δv (km/s)"), PLOT_CONFIG)

        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_zlabel("z (DU)")
        ax.set_title(f"GEO→DRO: {len(sel_records)} 条转移轨道")
        ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

        # 等比例轴
        if all_transfer_pts:
            all_pts = np.concatenate(all_transfer_pts + [dro_orbit.states[:, :3]])
            mid = all_pts.mean(axis=0)
            half = np.ptp(all_pts, axis=0).max() / 2.0 + 0.1
            ax.set_xlim(mid[0] - half, mid[0] + half)
            ax.set_ylim(mid[1] - half, mid[1] + half)
            ax.set_zlim(mid[2] - half, mid[2] + half)
            ax.set_box_aspect([1, 1, 1])

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
        print(f"Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


# =====================================================================
# 交互式浏览
# =====================================================================


def interactive_browse(records, dro_orbit, system, dynamics, max_pos_err_km=100.0):
    """按 Δv 排序，交互式逐条浏览 GEO→DRO 优化结果。同一窗口内重绘。"""
    # 过滤有效解
    good = []
    for i, r in enumerate(records):
        if not r["success"]:
            continue
        pv = r.get("pos_violation")
        if pv is not None:
            pos_km = np.sqrt(max(0, float(pv))) * DU
            if pos_km > max_pos_err_km:
                continue
        good.append((i, r))

    # 按 Δv 排序
    good.sort(key=lambda x: x[1]["objective_value"])
    n = len(good)
    current = 0

    if n == 0:
        print("No valid results to browse")
        return

    plt.ion()
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")

    # GEO 圆和 DRO 轨道是固定的，只算一次
    gx, gy = _geo_circle_points()
    dro_x = dro_orbit.states[:, 0]
    dro_y = dro_orbit.states[:, 1]
    dro_z = dro_orbit.states[:, 2]

    # 预计算平动点
    system.compute_libration_points()
    if system.L1 is None or system.L2 is None:
        raise RuntimeError("L1/L2 平动点未计算")
    lp_data = [("L1", system.L1[0]), ("L2", system.L2[0])]

    print(f"\nInteractive browse: GEO -> DRO optimized transfers")
    print(f"{n} valid results, sorted by dv_total")
    print("Commands: Enter=next, q=quit, s N=skip N, j N=jump to #N, r=redraw")

    while 0 <= current < n:
        orig_i, rec = good[current]
        alpha = rec["alpha"]
        tt = rec.get("transfer_time", 0)
        dv1 = rec.get("delta_v1", 0)
        dv2 = rec.get("delta_v2", 0)
        total = rec.get("objective_value", 0)
        pv = rec.get("pos_violation", 0)
        pos_km = np.sqrt(max(0, float(pv))) * DU
        angle = rec.get("angle_deg", 0)

        print(f"\n[{current+1}/{n}] (idx={orig_i}) a={alpha:.4f}, T={tt * TU:.1f} 天, "
              f"dv1={dv1 * VU / 1000:.4f}, dv2={dv2 * VU / 1000:.4f}, total={total * VU / 1000:.4f} km/s, "
              f"pos={pos_km:.1f} km, angle={angle:.1f} deg")

        dep_state = rec.get("departure_state")
        if dep_state is None:
            print("  no departure state, skip")
            current += 1
            continue

        try:
            states, times = _integrate_transfer(dep_state, alpha, tt, dynamics)
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
        ax.plot(states[:, 0], states[:, 1], states[:, 2],
                color="crimson", lw=1.2, label="转移轨道")
        # 出发/到达
        dep_pos = np.asarray(dep_state, dtype=float)[:3]
        ax.scatter(*dep_pos, color="green", s=40, zorder=5, label="出发点")
        ax.scatter(*states[-1, :3], color="orange", s=40, marker="s", zorder=5, label="终点")
        # 天体
        ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
        ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
        # 平动点
        for lp_name, lp_x in lp_data:
            ax.scatter(lp_x, 0, 0, color="red", marker="+", s=30, zorder=5)
            ax.text(lp_x, 0.02, 0, lp_name, fontsize=PLOT_CONFIG.lp_label, ha="center", color="red")

        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_zlabel("z (DU)")
        ax.set_title(
            f"[{current+1}/{n}] a={alpha:.4f}  T={tt * TU:.1f} 天  "
            f"Δv={total * VU / 1000:.4f} km/s  pos={pos_km:.1f} km",
            fontsize=PLOT_CONFIG.title,
        )
        ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

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
    print("Exit browse")


# =====================================================================
# main
# =====================================================================


def main():
    parser = argparse.ArgumentParser(
        description="GEO -> DRO optimization result visualization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--file", type=str, default=None, help="optimization JSON path (auto-detect latest)")
    parser.add_argument("--orbit", action="store_true", help="3D transfer orbit plot")
    parser.add_argument("--time-dv", action="store_true", help="transfer time vs dv scatter plot")
    parser.add_argument("--interactive", action="store_true", help="interactive browsing mode")
    parser.add_argument("--idx", type=str, default="best:5",
                        help="orbit selection: all, best, best:N, random, or index")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument("--max-points", type=int, default=200,
                        help="max orbits for --idx all")
    parser.add_argument("--max-pos-err", type=float, default=100.0,
                        help="max position error (km) to include")
    parser.add_argument("--save", type=str, default=None, help="save figure to path")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    if args.file:
        opt_path = Path(args.file).expanduser().resolve()
        # 路径遍历防护
        try:
            opt_path.relative_to(project_root.resolve())
        except ValueError:
            print(f"安全拒绝: {opt_path} 不在项目根目录 {project_root} 内")
            sys.exit(1)
    else:
        opt_path = _latest_optimization_json()
    if opt_path is None or not opt_path.exists():
        print("optimization result JSON not found")
        return

    print(f"Loading: {opt_path}")
    data = load_optimization_results(opt_path)
    records = _collect_nlp_records(data)

    # 加载 DRO
    dro_file = DRO_FILE
    if not dro_file.exists():
        dro_files = sorted((project_root / "output/dro").glob("dro_31_*.json"))
        if not dro_files:
            print("DRO file not found")
            return
        dro_file = dro_files[-1]
    dro_orbit = load_orbit_from_json(str(dro_file))
    with open(dro_file) as f:
        dro_data = json.load(f)
    dro_orbit.period = dro_data.get("properties", {}).get("period")

    # 统计
    n_total = len(records)
    n_success = sum(1 for r in records if r["success"])
    n_valid = sum(
        1 for r in records
        if r["success"] and np.sqrt(max(0, float(r.get("pos_violation", 1e10)))) * DU < args.max_pos_err
    )
    print(f"Total: {n_total}, success: {n_success}, valid (pos<{args.max_pos_err:.0f}km): {n_valid}")

    system, dynamics = _build_dynamics()

    if args.interactive:
        interactive_browse(records, dro_orbit, system, dynamics, args.max_pos_err)

    elif args.orbit:
        indices = _select_indices(
            records, args.idx, seed=args.seed,
            max_points=args.max_points, max_pos_err_km=args.max_pos_err,
        )
        print(f"Plotting {len(indices)} orbits (idx={args.idx})")
        plot_orbit_3d(records, indices, dro_orbit, system, dynamics,
                      save_path=args.save, dpi=args.dpi)

    else:
        # 过滤有效解用于散点图
        valid_records = [
            r for r in records
            if r["success"] and np.sqrt(max(0, float(r.get("pos_violation", 1e10)))) * DU < args.max_pos_err
        ]
        if not valid_records:
            print("No valid records to plot")
            return

        if args.time_dv:
            fig, ax = plt.subplots(figsize=(10, 6))
            plot_transfer_time_vs_dv(valid_records, ax)
            fig.tight_layout()
        else:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
            plot_dv_summary(valid_records, ax1)
            plot_dv_scatter(valid_records, ax2)
            meta = data.get("meta", {})
            fig.suptitle(
                f"N={len(valid_records)} 条有效结果 | {meta.get('nlp_solver', '')}",
                fontsize=PLOT_CONFIG.suptitle, y=1.02,
            )
            fig.tight_layout()

        if args.save:
            png = Path(args.save).expanduser().resolve()
            png.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
            print(f"Saved: {png}")
        else:
            plt.show()
        plt.close(fig)


if __name__ == "__main__":
    main()
