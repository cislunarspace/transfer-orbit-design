"""
GEO → DRO 优化结果可视化

可视化 optimize_geo_to_dro.py 的输出结果。
支持 Δv 汇总图、散点图和 3D 转移轨道图。

运行:
    python scripts/transfer/plot_optimize_result_geo_to_dro.py              # Δv 汇总图
    python scripts/transfer/plot_optimize_result_geo_to_dro.py --orbit       # 3D 轨道图
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "SimSun", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

import e2m2e
from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.transfer import load_orbit_from_json
from scripts.utils.common import DU, MU, TU, VU
from scripts.utils.geo import (
    R_GEO,
    EARTH_CENTER,
    compute_departure_velocity,
)

project_root = Path(__file__).resolve().parent.parent.parent

# =====================================================================
# 配置
# =====================================================================
OPT_JSON = None  # None = 自动查找最新
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
    ax.bar(x - w, dv1, width=w, label="Δv1 (出发)", color="steelblue")
    ax.bar(x, dv2, width=w, label="Δv2 (插入)", color="coral")
    ax.bar(x + w, total, width=w, label="Δv_total", color="seagreen")

    for i, s in enumerate(success):
        if not s:
            ax.axvline(i, color="red", alpha=0.3)

    ax.set_xlabel("解编号")
    ax.set_ylabel("Δv (km/s)")
    ax.set_title("GEO → DRO: Δv 汇总")
    ax.legend(fontsize=8)
    ax.set_xticks(x)


def plot_dv_scatter(records, ax):
    success = [r for r in records if r["success"]]
    if not success:
        ax.text(0.5, 0.5, "无成功解", transform=ax.transAxes, ha="center")
        return

    dv1 = np.array([r["delta_v1"] for r in success]) * VU / 1000
    dv2 = np.array([r["delta_v2"] for r in success]) * VU / 1000
    obj = np.array([r["objective_value"] for r in success]) * VU / 1000

    sc = ax.scatter(dv1, dv2, c=obj, cmap="plasma", s=20, alpha=0.8)
    plt.colorbar(sc, ax=ax, label="Δv_total (km/s)")

    best = min(success, key=lambda r: r["objective_value"])
    ax.annotate(
        f"最优 α={best['alpha']:.4f}\nΔv={best['objective_value'] * VU / 1000:.2f} km/s",
        xy=(best["delta_v1"] * VU / 1000, best["delta_v2"] * VU / 1000),
        fontsize=8, color="red",
        arrowprops=dict(arrowstyle="->", color="red"),
        xytext=(10, 10), textcoords="offset points",
    )

    ax.set_xlabel("Δv1 (km/s)")
    ax.set_ylabel("Δv2 (km/s)")
    ax.set_title("GEO → DRO: Δv1 vs Δv2")
    ax.grid(True, alpha=0.3)


# =====================================================================
# 3D 轨道
# =====================================================================


def _select_indices(records, idx_arg, max_points=200):
    success = [(i, r) for i, r in enumerate(records) if r["success"]]
    if not success:
        return []

    if idx_arg == "all":
        indices = [i for i, _ in success]
        if len(indices) > max_points:
            rng = np.random.default_rng(42)
            sel = rng.choice(len(indices), size=max_points, replace=False)
            indices = [indices[s] for s in sel]
        return indices
    elif idx_arg.startswith("best"):
        parts = idx_arg.split(":")
        top_n = int(parts[1]) if len(parts) > 1 else 5
        by_obj = sorted(success, key=lambda x: x[1]["objective_value"])
        return [i for i, _ in by_obj[:top_n]]
    elif idx_arg == "random":
        i = np.random.default_rng(42).choice([j for j, _ in success])
        return [i]
    else:
        i = int(idx_arg)
        return [i] if 0 <= i < len(records) and records[i]["success"] else []


def plot_orbit_3d(records, sel_indices, dro_orbit, system, dynamics, save_path=None):
    if not sel_indices:
        print("无选中轨道")
        return

    sel_records = [records[i] for i in sel_indices]

    if len(sel_records) == 1:
        rec = sel_records[0]
        dep_state = rec["departure_state"]
        alpha = rec["alpha"]
        tt = rec["transfer_time"]

        states, times = _integrate_transfer(dep_state, alpha, tt, dynamics)

        fig = plt.figure(figsize=(14, 10))
        ax = fig.add_subplot(111, projection="3d")

        # GEO 圆
        gx, gy = _geo_circle_points()
        ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.8, label="GEO")

        # DRO
        ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1], dro_orbit.states[:, 2],
                color="royalblue", lw=0.8, label="DRO")

        # 转移轨道
        ax.plot(states[:, 0], states[:, 1], states[:, 2],
                color="crimson", lw=1.5, label="转移轨道")

        # 出发点和终点
        dep_pos = np.asarray(dep_state, dtype=float)[:3]
        ax.scatter(*dep_pos, color="green", s=60, zorder=5, label="GEO 出发")
        ax.scatter(*states[-1, :3], color="orange", s=60, marker="s", zorder=5, label="DRO 插入")

        # 地球月球
        ax.scatter(*EARTH_CENTER, color="blue", s=80, zorder=5)
        ax.scatter(1.0 - MU, 0, 0, color="gray", s=40, zorder=5)

        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_zlabel("z (DU)")
        ax.set_title(
            f"GEO→DRO 最优解\n"
            f"α={alpha:.6f}  T={tt:.2f} TU ({tt * TU:.1f}天)  "
            f"t_ins={rec.get('t_ins', 'N/A'):.4f} TU\n"
            f"Δv1={rec['delta_v1']:.4f} VU ({rec['delta_v1'] * VU:.0f} m/s)  "
            f"Δv2={rec['delta_v2']:.4f} VU ({rec['delta_v2'] * VU:.0f} m/s)  "
            f"Total={rec['objective_value']:.4f} VU ({rec['objective_value'] * VU:.0f} m/s)"
        )
        ax.legend(fontsize=8)
    else:
        fig = plt.figure(figsize=(14, 10))
        ax = fig.add_subplot(111, projection="3d")

        # 背景轨道
        gx, gy = _geo_circle_points()
        ax.plot(gx, gy, np.zeros_like(gx), color="gray", ls="--", lw=0.5)
        ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1], dro_orbit.states[:, 2],
                color="royalblue", lw=0.5, alpha=0.5)

        obj_values = [r["objective_value"] for r in sel_records]
        norm = plt.Normalize(min(obj_values), max(obj_values))
        cmap = plt.cm.plasma

        for rec in sel_records:
            dep_state = rec["departure_state"]
            alpha = rec["alpha"]
            tt = rec["transfer_time"]
            states, _ = _integrate_transfer(dep_state, alpha, tt, dynamics)
            color = cmap(norm(rec["objective_value"]))
            ax.plot(states[:, 0], states[:, 1], states[:, 2], color=color, lw=0.8, alpha=0.7)

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        plt.colorbar(sm, ax=ax, label="Δv_total (VU)", shrink=0.7)

        ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
        ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_zlabel("z (DU)")
        ax.set_title(f"GEO→DRO: {len(sel_records)} 条转移轨道")

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"已保存: {save_path}")
    plt.show()


# =====================================================================
# main
# =====================================================================


def main():
    parser = argparse.ArgumentParser(description="GEO → DRO 优化结果可视化")
    parser.add_argument("--file", type=str, default=None, help="优化结果 JSON 路径")
    parser.add_argument("--orbit", action="store_true", help="绘制 3D 转移轨道图")
    parser.add_argument("--idx", type=str, default="best:5",
                        help="轨道选择: all, best, best:N, random, 或序号")
    args = parser.parse_args()

    if args.file:
        opt_path = Path(args.file)
    else:
        opt_path = _latest_optimization_json()
    if opt_path is None or not opt_path.exists():
        print("未找到优化结果文件")
        return

    print(f"加载: {opt_path}")
    data = load_optimization_results(opt_path)
    records = _collect_nlp_records(data)

    successes = [r for r in records if r["success"]]
    print(f"共 {len(records)} 条, 成功 {len(successes)} 条")

    # 加载 DRO
    dro_file = DRO_FILE
    if not dro_file.exists():
        dro_files = sorted((project_root / "output/dro").glob("dro_31_*.json"))
        if not dro_files:
            print("找不到 DRO 文件")
            return
        dro_file = dro_files[-1]
    dro_orbit = load_orbit_from_json(str(dro_file))
    with open(dro_file) as f:
        dro_data = json.load(f)
    dro_orbit.period = dro_data.get("properties", {}).get("period")

    system, dynamics = _build_dynamics()

    if args.orbit:
        indices = _select_indices(records, args.idx)
        plot_orbit_3d(records, indices, dro_orbit, system, dynamics)
    else:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        plot_dv_summary(records, ax1)
        plot_dv_scatter(records, ax2)
        fig.suptitle("GEO → DRO 优化结果", fontsize=14)
        fig.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
