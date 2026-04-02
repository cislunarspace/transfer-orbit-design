"""
可视化 optimize 阶段输出的 NLP 优化结果 JSON：

- **散点图**（默认）: 每条 NLP 结果的 Δv1、Δv2、总 Δv 汇总
- **转移轨道 3D 示意图** (--orbit): 重新积分 NLP 最优解，叠加绘制 DRO / RO / 转移弧

用法:
    python plot_optimize_result.py                                         # Δv 汇总散点图
    python plot_optimize_result.py --orbit                                 # 绘制最优解的转移轨道
    python plot_optimize_result.py --orbit --idx best                      # 同上
    python plot_optimize_result.py --orbit --idx 0                         # 绘制第 0 条结果
    python plot_optimize_result.py --orbit --idx all                       # 绘制全部
    python plot_optimize_result.py --orbit --idx best:5                    # Δv 最小的 5 条
    python plot_optimize_result.py --orbit --idx random --seed 42
    python plot_optimize_result.py --save output/transfer/figures/opt.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC",
    "Microsoft YaHei",
    "SimSun",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import load_orbit_from_json
from e2m2e.visualization.plotting import OrbitVisualizer

from scripts.utils.common import DU, MU, TU

DRO_FILE = project_root / "output/dro/dro_31_3857864736.json"
RO_FILE = project_root / "output/ro/ro_31_3857864753.json"

DT = 1.0 / (24.0 * TU)
V_SCALE = 1023.23281


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
    vel = np.asarray(state6[3:6], dtype=np.float64)
    v_mag = np.linalg.norm(vel)
    if v_mag < 1e-10:
        return vel.copy()
    tangential = vel / v_mag
    normal = np.array([0.0, 0.0, 1.0])
    normal_dir = np.cross(tangential, normal)
    norm_nd = np.linalg.norm(normal_dir)
    if norm_nd < 1e-10:
        normal_dir = np.array([1.0, 0.0, 0.0])
    else:
        normal_dir = normal_dir / norm_nd
    return alpha * v_mag * tangential


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


def plot_dv_summary(records: List[Dict[str, Any]], ax: plt.Axes) -> None:
    if not records:
        ax.text(0.5, 0.5, "no results", ha="center", va="center", transform=ax.transAxes)
        return

    success = [r for r in records if r["success"]]
    fail = [r for r in records if not r["success"]]

    if success:
        dv1 = np.array([r["delta_v1"] for r in success]) * V_SCALE
        dv2 = np.array([r["delta_v2"] for r in success]) * V_SCALE
        total = np.array([r["objective_value"] for r in success]) * V_SCALE
        idx = np.arange(len(success))

        bar_w = 0.25
        ax.bar(idx - bar_w, dv1, bar_w, label="Δv₁ (departure)", color="steelblue")
        ax.bar(idx, dv2, bar_w, label="Δv₂ (insertion)", color="coral")
        ax.bar(idx + bar_w, total, bar_w, label="Total Δv", color="seagreen")
        ax.set_xticks(idx)
        ax.set_xticklabels([str(i) for i in idx], fontsize=8)

    if fail:
        n_s = len(success)
        fail_total = [r["objective_value"] * V_SCALE for r in fail]
        ax.scatter(
            range(n_s, n_s + len(fail)),
            fail_total,
            marker="x",
            c="red",
            s=40,
            label=f"failed ({len(fail)})",
            zorder=5,
        )

    ax.set_xlabel("Result index")
    ax.set_ylabel("Δv (m/s)")
    ax.set_title("NLP Optimization: Δv Summary")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def plot_dv_scatter(records: List[Dict[str, Any]], ax: plt.Axes) -> None:
    success = [r for r in records if r["success"]]
    if not success:
        ax.text(0.5, 0.5, "no successful results", ha="center", va="center", transform=ax.transAxes)
        return

    dv1 = np.array([r["delta_v1"] for r in success]) * V_SCALE
    dv2 = np.array([r["delta_v2"] for r in success]) * V_SCALE
    total = np.array([r["objective_value"] for r in success]) * V_SCALE
    alpha = np.array([r["alpha"] for r in success])

    sc = ax.scatter(dv1, dv2, c=total, cmap="viridis_r", s=24, alpha=0.8, edgecolors="gray", linewidths=0.3)
    cbar = plt.colorbar(sc, ax=ax)
    cbar.set_label("Total Δv (m/s)", fontsize=9)
    ax.set_xlabel("Δv₁ (m/s)")
    ax.set_ylabel("Δv₂ (m/s)")
    ax.set_title("NLP: Δv₁ vs Δv₂ (color=Total Δv)")
    ax.grid(True, alpha=0.3)

    best_idx = int(np.argmin(total))
    ax.annotate(
        f"best: α={alpha[best_idx]:.3f}\nΔv={total[best_idx]:.1f} m/s",
        xy=(dv1[best_idx], dv2[best_idx]),
        xytext=(10, 10),
        textcoords="offset points",
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="red"),
        color="red",
    )


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
        insertion_state = dynamics.propagate_orbit_state_at_time(ro_orbit, t_ins)

        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection="3d")

        viz = OrbitVisualizer(system=system)
        viz.plot_transfer_orbit(
            departure_orbit=dro_orbit,
            arrival_orbit=ro_orbit,
            transfer_trajectory=states,
            departure_state=departure_state[:3],
            insertion_state=insertion_state[:3],
            ax=ax,
            label=f"Transfer (α={alpha:.3f})",
            color="crimson",
        )

        dv1_ms = rec["delta_v1"] * V_SCALE
        dv2_ms = rec["delta_v2"] * V_SCALE
        ax.set_title(
            f"NLP Transfer: α={alpha:.4f}, T={T:.2f} TU, t_ins={t_ins:.2f} TU\n"
            f"Δv₁={dv1_ms:.2f} m/s, Δv₂={dv2_ms:.2f} m/s, Total={rec['objective_value'] * V_SCALE:.2f} m/s",
            fontsize=11,
        )
        ax.view_init(elev=0, azim=-90)
    else:
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection="3d")

        ax.plot(
            dro_orbit.states[:, 0],
            dro_orbit.states[:, 1],
            dro_orbit.states[:, 2],
            "-",
            color="steelblue",
            lw=1.0,
            alpha=0.5,
            label="DRO",
        )
        ax.plot(
            ro_orbit.states[:, 0],
            ro_orbit.states[:, 1],
            ro_orbit.states[:, 2],
            "-",
            color="seagreen",
            lw=1.0,
            alpha=0.5,
            label="RO",
        )

        cmap = plt.cm.plasma
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

            ax.plot(states[:, 0], states[:, 1], states[:, 2], "-", color=color, lw=1.0, alpha=0.7)
            ax.scatter(
                [departure_state[0]], [departure_state[1]], [departure_state[2]],
                color=color, s=20, alpha=0.8,
            )
            if len(states) > 0:
                ax.scatter(
                    [states[-1, 0]], [states[-1, 1]], [states[-1, 2]],
                    color=color, s=20, alpha=0.8, marker="s",
                )

            if (cm_idx + 1) % 10 == 0 or cm_idx == n_sel - 1:
                print(f"  [{cm_idx + 1}/{n_sel}] 已绘制")

        viz = OrbitVisualizer(system=system)
        viz.plot_primary_bodies(ax=ax, is_3d=True)
        viz.plot_libration_points(ax=ax, is_3d=True, show_labels=True)

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=obj_min * V_SCALE, vmax=obj_max * V_SCALE))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.1)
        cbar.set_label("Total Δv (m/s)", fontsize=9)

        ax.set_xlabel("X", fontsize=10)
        ax.set_ylabel("Y", fontsize=10)
        ax.set_zlabel("Z", fontsize=10)
        ax.set_title(f"NLP Transfer Orbits: {n_sel} solutions", fontsize=11)
        ax.legend(loc="upper right", fontsize=9)
        ax.view_init(elev=0, azim=-90)

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
    else:
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        plot_dv_summary(records, axes[0])
        plot_dv_scatter(records, axes[1])

        fig.suptitle(
            f"N={len(records)} results, {n_success} successful | {meta.get('nlp_solver', '')}",
            fontsize=12,
            y=1.02,
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
