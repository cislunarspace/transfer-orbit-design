"""
DRO → RO 转移轨道 NLP 优化结果可视化

可视化 dro_to_ro/optimize_dro_to_ro.py 输出的 NLP 优化结果 JSON：
- **散点图**（默认）: 每条 NLP 结果的 Δv1、Δv2、总 Δv 汇总
- **转移轨道 3D 示意图** (--orbit): 重新积分 NLP 最优解，叠加绘制 DRO / RO / 转移弧

用法:
    python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py                 # Δv 汇总散点图
    python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py --orbit          # 绘制最优解的转移轨道
    python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py --orbit --idx best       # 同上
    python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py --orbit --idx 0            # 绘制第 0 条结果
    python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py --orbit --idx all          # 绘制全部
    python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py --orbit --idx best:5      # Δv 最小的 5 条
    python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py --orbit --idx random --seed 42
    python scripts/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py --save output/transfer/figures/opt.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.colors import Normalize
import numpy as np

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "SimSun", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import load_orbit_from_json

from scripts.utils.common import DU, MU, TU, VU
from scripts.utils.geo import EARTH_CENTER

DRO_FILE = project_root / "output/dro/dro_31_3857864736.json"
RO_FILE = project_root / "output/ro/ro_31_3857864753.json"

DT = 1.0 / (24.0 * TU)


def _latest_optimization_json() -> Optional[Path]:
    transfer_dir = project_root / "output/transfer"
    candidates = sorted(transfer_dir.glob("optimization_results_*.json"))
    return candidates[-1] if candidates else None


def load_optimization_results(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_dynamics() -> Tuple[CR3BP_System, CR3BP_Dynamics]:
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = DT
    return system, dynamics


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
    return v_radial_comp * radial + alpha * v_tangential_comp * tangential


def _integrate_transfer(
    departure_state: np.ndarray, alpha: float, transfer_time: float, dynamics: CR3BP_Dynamics
) -> Tuple[np.ndarray, np.ndarray]:
    v_injection = _compute_departure_velocity(departure_state, alpha)
    initial_state = np.concatenate([departure_state[:3], v_injection])
    result = dynamics.propagate(
        initial_state=initial_state,
        t_span=(0.0, transfer_time),
        with_stm=False,
        with_jacobi=False,
    )
    return result["time"], result["states"]


def _collect_nlp_records(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = []
    for r in data.get("results", []):
        nlp = r.get("nlp")
        if nlp is None:
            continue
        records.append(
            {
                "search_index": r.get("search_index"),
                "departure_state": r.get("departure_state"),
                "search_alpha": r.get("alpha"),
                "search_dv": r.get("dv_departure"),
                "success": nlp.get("success", False),
                "alpha": nlp.get("alpha"),
                "transfer_time": nlp.get("transfer_time"),
                "t_ins": nlp.get("t_ins"),
                "delta_v1": nlp.get("delta_v1"),
                "delta_v2": nlp.get("delta_v2"),
                "objective_value": nlp.get("objective_value"),
                "transfer_type": nlp.get("transfer_type"),
                "constraints_violation": nlp.get("constraints_violation", {}),
                "message": nlp.get("message"),
            }
        )
    return records


def _select_indices(
    records: List[Dict[str, Any]], idx_arg: str, seed: int, max_points: Optional[int] = None
) -> List[int]:
    n = len(records)
    obj_vals = [r.get("objective_value", float("inf")) for r in records]

    if idx_arg == "all":
        if max_points is not None and n > max_points:
            rng = np.random.default_rng(seed)
            chosen = rng.choice(n, size=max_points, replace=False)
            return sorted(chosen.tolist())
        return list(range(n))
    elif idx_arg.startswith("best"):
        parts = idx_arg.split(":")
        top_n = int(parts[1]) if len(parts) == 2 else 1
        top_n = min(top_n, n)
        sorted_idx = sorted(range(n), key=lambda i: obj_vals[i])
        return sorted_idx[:top_n]
    elif idx_arg == "random":
        rng = np.random.default_rng(seed)
        return [int(rng.integers(0, n))]
    else:
        i = int(idx_arg)
        if i < 0 or i >= n:
            raise ValueError(f"索引 {i} 超出范围（总数={n}）")
        return [i]


# =====================================================================
# 图表
# =====================================================================


def plot_dv_summary(records: List[Dict[str, Any]], ax: Axes) -> None:
    if not records:
        ax.text(0.5, 0.5, "无数据", ha="center", va="center", transform=ax.transAxes)
        return

    success = [r for r in records if r["success"]]
    fail = [r for r in records if not r["success"]]

    if success:
        dv1 = np.array([r["delta_v1"] for r in success]) * VU / 1000
        dv2 = np.array([r["delta_v2"] for r in success]) * VU / 1000
        total = np.array([r["objective_value"] for r in success]) * VU / 1000
        idx = np.arange(len(success))

        bar_w = 0.25
        ax.bar(idx - bar_w, dv1, bar_w, label="Δv₁ (出发)", color="steelblue")
        ax.bar(idx, dv2, bar_w, label="Δv₂ (入轨)", color="coral")
        ax.bar(idx + bar_w, total, bar_w, label="总 Δv", color="seagreen")
        ax.set_xticks(idx)
        ax.set_xticklabels([str(i) for i in idx], fontsize=8)

    if fail:
        n_s = len(success)
        fail_total = [r["objective_value"] * VU / 1000 for r in fail]
        ax.scatter(
            range(n_s, n_s + len(fail)),
            fail_total,
            marker="x",
            c="red",
            s=40,
            label=f"失败 ({len(fail)})",
            zorder=5,
        )

    ax.set_xlabel("结果索引")
    ax.set_ylabel("Δv (km/s)")
    ax.set_title("NLP 优化: Δv 汇总")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def plot_dv_scatter(records: List[Dict[str, Any]], ax: Axes) -> None:
    success = [r for r in records if r["success"]]
    if not success:
        ax.text(0.5, 0.5, "无成功结果", ha="center", va="center", transform=ax.transAxes)
        return

    dv1 = np.array([r["delta_v1"] for r in success]) * VU / 1000
    dv2 = np.array([r["delta_v2"] for r in success]) * VU / 1000
    total = np.array([r["objective_value"] for r in success]) * VU / 1000

    sc = ax.scatter(dv1, dv2, c=total, cmap="viridis", s=6, alpha=0.6)
    plt.colorbar(sc, ax=ax, label="总 Δv (km/s)")
    ax.set_xlabel("Δv₁ (km/s)")
    ax.set_ylabel("Δv₂ (km/s)")
    ax.set_title("NLP: Δv₁ vs Δv₂ (颜色=总 Δv)")
    ax.grid(True, alpha=0.3)

    best_idx = int(np.argmin(total))
    alpha = np.array([r["alpha"] for r in success])
    ax.annotate(
        f"最优: α={alpha[best_idx]:.3f}\nΔv={total[best_idx]:.3f} km/s",
        xy=(dv1[best_idx], dv2[best_idx]),
        xytext=(10, 10),
        textcoords="offset points",
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="red"),
        color="red",
    )


def plot_transfer_time_vs_dv(records: List[Dict[str, Any]], ax: Axes) -> None:
    success = [r for r in records if r["success"]]
    if not success:
        ax.text(0.5, 0.5, "无成功结果", ha="center", va="center", transform=ax.transAxes)
        return

    tt_days = np.array([r["transfer_time"] * TU for r in success])
    total_dv = np.array([r["objective_value"] * VU / 1000 for r in success])

    sc = ax.scatter(tt_days, total_dv, c=total_dv, cmap="viridis", s=6, alpha=0.6)
    plt.colorbar(sc, ax=ax, label="总 Δv (km/s)")
    ax.set_xlabel("转移时间 (天)")
    ax.set_ylabel("总 Δv (km/s)")
    ax.set_title("NLP: 转移时间 vs 总 Δv")
    ax.grid(True, alpha=0.3)

    best_idx = int(np.argmin(total_dv))
    ax.annotate(
        f"最优: T={tt_days[best_idx]:.1f} 天\nΔv={total_dv[best_idx]:.3f} km/s",
        xy=(tt_days[best_idx], total_dv[best_idx]),
        xytext=(10, 10),
        textcoords="offset points",
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="red"),
        color="red",
    )


# =====================================================================
# 3D 轨道
# =====================================================================


def plot_orbit_3d(
    records: List[Dict[str, Any]],
    sel_indices: List[int],
    dro_orbit: Orbit,
    ro_orbit: Orbit,
    system: CR3BP_System,
    dynamics: CR3BP_Dynamics,
    save_path: Optional[Path] = None,
    dpi: int = 150,
) -> None:
    n_sel = len(sel_indices)

    if n_sel == 1:
        rec = records[sel_indices[0]]
        departure_state = np.asarray(rec["departure_state"], dtype=np.float64)
        alpha = rec["alpha"]
        T = rec["transfer_time"]
        t_ins = rec["t_ins"]

        print(f"积分转移轨道: α={alpha:.6f}, T={T:.4f} TU, t_ins={t_ins:.4f} TU ...")
        times, states = _integrate_transfer(departure_state, alpha, T, dynamics)

        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        # DRO 出发轨道
        ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1],
                dro_orbit.states[:, 2], color="royalblue", lw=0.8, label="DRO")

        # RO 到达轨道
        ax.plot(ro_orbit.states[:, 0], ro_orbit.states[:, 1],
                ro_orbit.states[:, 2], color="seagreen", lw=0.8, label="RO")

        # 转移轨迹
        ax.plot(states[:, 0], states[:, 1], states[:, 2],
                color="crimson", lw=1.2, label="转移轨道")

        # 出发点和到达点
        ax.scatter(*departure_state[:3], color="green", s=40, zorder=5, label="出发点")

        # 到达点（t_ins 时刻 RO 上的点）
        arrival_state = dynamics.propagate_orbit_state_at_time(ro_orbit, t_ins)
        ax.scatter(*arrival_state[:3], color="orange", s=40, marker="s", zorder=5, label="终点")

        # 地球和月球
        ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
        ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
        ax.text(EARTH_CENTER[0], EARTH_CENTER[1] + 0.03, 0, "地球", fontsize=7, ha="center")
        ax.text(1.0 - MU, 0.03, 0, "月球", fontsize=7, ha="center")

        # 平动点
        system.compute_libration_points()
        assert system.L1 is not None and system.L2 is not None
        for lp_name, lp_x in [("L1", system.L1[0]), ("L2", system.L2[0])]:
            ax.scatter(lp_x, 0, 0, color="red", marker="+", s=30, zorder=5)
            ax.text(lp_x, 0.02, 0, lp_name, fontsize=6, ha="center", color="red")

        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_zlabel("z (DU)")

        dv1_km = rec["delta_v1"] * VU / 1000
        dv2_km = rec["delta_v2"] * VU / 1000
        total_km = rec["objective_value"] * VU / 1000
        ax.set_title(
            f"DRO→RO  α={alpha:.4f}  T={T:.2f} TU ({T * TU:.1f}天)\n"
            f"Δv_dep={dv1_km:.4f} km/s  Δv_ins={dv2_km:.4f} km/s  "
            f"Total={total_km:.4f} km/s"
        )
        ax.legend(fontsize=7, loc="upper left")

        # 等比例轴
        all_pts = np.concatenate([states[:, :3], dro_orbit.states[:, :3],
                                  ro_orbit.states[:, :3]])
        mid = all_pts.mean(axis=0)
        half = np.ptp(all_pts, axis=0).max() / 2.0 + 0.1
        ax.set_xlim(mid[0] - half, mid[0] + half)
        ax.set_ylim(mid[1] - half, mid[1] + half)
        ax.set_zlim(mid[2] - half, mid[2] + half)
        ax.set_box_aspect([1, 1, 1])
    else:
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        # DRO
        ax.plot(dro_orbit.states[:, 0], dro_orbit.states[:, 1],
                dro_orbit.states[:, 2], color="royalblue", lw=0.8, label="DRO")
        # RO
        ax.plot(ro_orbit.states[:, 0], ro_orbit.states[:, 1],
                ro_orbit.states[:, 2], color="seagreen", lw=0.8, label="RO")

        cmap = matplotlib.colormaps["plasma"]
        obj_vals = [records[i]["objective_value"] for i in sel_indices]
        obj_min, obj_max = min(obj_vals), max(obj_vals)
        obj_range = obj_max - obj_min if obj_max > obj_min else 1.0

        for cm_idx, sel_idx in enumerate(sel_indices):
            rec = records[sel_idx]
            departure_state = np.asarray(rec["departure_state"], dtype=np.float64)
            alpha = rec["alpha"]
            T = rec["transfer_time"]

            _, states = _integrate_transfer(departure_state, alpha, T, dynamics)

            norm_val = (rec["objective_value"] - obj_min) / obj_range
            color = cmap(norm_val)

            ax.plot(states[:, 0], states[:, 1], states[:, 2], color=color, lw=1.2, alpha=0.7)
            ax.scatter(*departure_state[:3], color=color, s=30, alpha=0.8)

            if (cm_idx + 1) % 10 == 0 or cm_idx == n_sel - 1:
                print(f"  [{cm_idx + 1}/{n_sel}] 已绘制")

        # 地球和月球
        ax.scatter(*EARTH_CENTER, color="blue", s=60, zorder=5)
        ax.scatter(1.0 - MU, 0, 0, color="gray", s=30, zorder=5)
        ax.text(EARTH_CENTER[0], EARTH_CENTER[1] + 0.03, 0, "地球", fontsize=7, ha="center")
        ax.text(1.0 - MU, 0.03, 0, "月球", fontsize=7, ha="center")

        # 平动点
        system.compute_libration_points()
        assert system.L1 is not None and system.L2 is not None
        for lp_name, lp_x in [("L1", system.L1[0]), ("L2", system.L2[0])]:
            ax.scatter(lp_x, 0, 0, color="red", marker="+", s=30, zorder=5)
            ax.text(lp_x, 0.02, 0, lp_name, fontsize=6, ha="center", color="red")

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=Normalize(
            vmin=obj_min * VU / 1000, vmax=obj_max * VU / 1000))
        sm.set_array([])
        plt.colorbar(sm, ax=ax, label="总 Δv (km/s)")

        ax.set_xlabel("x (DU)")
        ax.set_ylabel("y (DU)")
        ax.set_zlabel("z (DU)")
        ax.set_title(f"DRO→RO: {n_sel} 条转移轨道")
        ax.legend(fontsize=7, loc="upper left")

        # 等比例轴
        all_pts = np.concatenate([dro_orbit.states[:, :3], ro_orbit.states[:, :3]])
        mid = all_pts.mean(axis=0)
        half = np.ptp(all_pts, axis=0).max() / 2.0 + 0.1
        ax.set_xlim(mid[0] - half, mid[0] + half)
        ax.set_ylim(mid[1] - half, mid[1] + half)
        ax.set_zlim(mid[2] - half, mid[2] + half)
        ax.set_box_aspect([1, 1, 1])

    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
        print(f"Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="可视化 NLP 优化结果")
    parser.add_argument("--file", type=str, default=None, help="optimization_results_*.json 路径（默认自动选最新）")
    parser.add_argument("--save", type=str, default=None, help="保存图片路径")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--orbit", action="store_true", help="绘制转移轨道 3D 示意图")
    parser.add_argument("--time-dv", action="store_true", help="转移时间 vs Δv 散点图")
    parser.add_argument("--idx", type=str, default="best", help="选择结果：整数索引 / best / best:N / random / all")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-points", type=int, default=500, help="--orbit --idx all 时最多绘制条数")
    args = parser.parse_args()

    if args.file:
        opt_path = Path(args.file).expanduser().resolve()
    else:
        opt_path = _latest_optimization_json()
    if opt_path is None or not opt_path.is_file():
        raise FileNotFoundError("未找到 optimization_results_*.json")
    print(f"读取: {opt_path}")

    data = load_optimization_results(opt_path)
    records = _collect_nlp_records(data)
    n_success = sum(1 for r in records if r["success"])
    print(f"结果总数: {len(records)}, 成功: {n_success}")

    meta = data.get("meta", {})
    print(f"求解器: {meta.get('nlp_solver', 'N/A')}")
    print(f"松弛速度约束: {meta.get('use_relaxed_velocity', 'N/A')}")

    if args.orbit:
        dro_orbit = load_orbit_from_json(str(DRO_FILE))
        ro_orbit = load_orbit_from_json(str(RO_FILE))
        with open(RO_FILE, encoding="utf-8") as f:
            roj = json.load(f)
        if "properties" in roj and "period" in roj["properties"]:
            ro_orbit.period = float(roj["properties"]["period"])

        system, dynamics = _build_dynamics()
        sel_indices = _select_indices(records, args.idx, args.seed, args.max_points)
        print(f"绘制 {len(sel_indices)} 条轨道 (idx={args.idx})")

        save_path = Path(args.save) if args.save else None
        plot_orbit_3d(records, sel_indices, dro_orbit, ro_orbit, system, dynamics, save_path, args.dpi)
    elif args.time_dv:
        fig, ax = plt.subplots(figsize=(10, 6))
        plot_transfer_time_vs_dv(records, ax)
        fig.tight_layout()

        if args.save:
            png = Path(args.save).expanduser().resolve()
            png.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
            print(f"Saved: {png}")
        else:
            plt.show()
        plt.close(fig)
    else:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        plot_dv_summary(records, ax1)
        plot_dv_scatter(records, ax2)
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
