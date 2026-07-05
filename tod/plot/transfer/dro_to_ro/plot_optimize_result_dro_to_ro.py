"""plot_optimize_result_dro_to_ro 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.transfer.dro_to_ro.plot_optimize_result_dro_to_ro --help
"""


from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
from e2m2e.core.orbit import Orbit
from e2m2e.orbits.geo import EARTH_CENTER
from e2m2e.transfer import load_orbit_from_json
from matplotlib.axes import Axes
from matplotlib.colors import Normalize
from tod.commons.constants import MU, TU, VU
from tod.commons.common import find_project_root
from tod.cli.input_file import (
    InputFileRequest,
    InputResolutionError,
    resolve_input_file,
)
from tod.plot.config import apply_standard_plot_config, style_colorbar

project_root = find_project_root(Path(__file__))

try:
    matplotlib.use("TkAgg")
except ImportError:
    pass
import matplotlib.pyplot as plt  # noqa: E402

PLOT_CONFIG = apply_standard_plot_config()
logger = logging.getLogger(__name__)

DRO_FILE = project_root / "output/dro/dro_31_3857864736.json"
RO_FILE = project_root / "output/ro/ro_31_3857864753.json"

DT = 1.0 / (24.0 * TU)


def _latest_optimization_json() -> Optional[Path]:
    transfer_dir = project_root / "output/transfer"
    candidates = sorted(transfer_dir.glob("optimization_results_*.json"))
    return candidates[-1] if candidates else None


def _resolve_opt_input(args) -> Path:
    """按 issue #183 契约解析 optimization_results_*.json。"""
    try:
        return resolve_input_file(
            InputFileRequest(
                explicit_path=Path(args.file) if args.file else None,
                auto_latest=bool(args.auto_latest),
                search_root=project_root / "output/transfer",
                pattern="optimization_results_*.json",
                flag="--file",
                auto_latest_flag="--auto-latest",
            )
        )
    except InputResolutionError as exc:
        parser = argparse.ArgumentParser(
            prog="plot_optimize_result_dro_to_ro",
            description="可视化 DRO→RO 优化结果",
        )
        if exc.candidates or exc.remaining:
            parser.error(
                f"{exc}\n候选 (mtime new→old):\n{exc.format_candidates()}"
            )
        parser.error(str(exc))


def load_optimization_results(path: Path) -> Dict[str, Any]:
    """读取转移优化结果 JSON 文件。
    
    Args:
        path: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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
    """绘制指定结果图形。
    
    Args:
        records: 调用方传入的参数值。
        ax: 调用方传入的参数值。
    
    Returns:
        None。
    """
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
        ax.set_xticklabels([str(i) for i in idx], fontsize=PLOT_CONFIG.tick)

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
    ax.legend(fontsize=PLOT_CONFIG.legend)
    ax.grid(True, alpha=0.3)


def plot_dv_scatter(records: List[Dict[str, Any]], ax: Axes) -> None:
    """绘制指定结果图形。
    
    Args:
        records: 调用方传入的参数值。
        ax: 调用方传入的参数值。
    
    Returns:
        None。
    """
    success = [r for r in records if r["success"]]
    if not success:
        ax.text(0.5, 0.5, "无成功结果", ha="center", va="center", transform=ax.transAxes)
        return

    dv1 = np.array([r["delta_v1"] for r in success]) * VU / 1000
    dv2 = np.array([r["delta_v2"] for r in success]) * VU / 1000
    total = np.array([r["objective_value"] for r in success]) * VU / 1000

    sc = ax.scatter(dv1, dv2, c=total, cmap="viridis", s=6, alpha=0.6)
    style_colorbar(plt.colorbar(sc, ax=ax, label="总 Δv (km/s)"), PLOT_CONFIG)
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
        fontsize=PLOT_CONFIG.legend,
        arrowprops=dict(arrowstyle="->", color="red"),
        color="red",
    )


def plot_transfer_time_vs_dv(records: List[Dict[str, Any]], ax: Axes) -> None:
    """绘制指定结果图形。
    
    Args:
        records: 调用方传入的参数值。
        ax: 调用方传入的参数值。
    
    Returns:
        None。
    """
    success = [r for r in records if r["success"]]
    if not success:
        ax.text(0.5, 0.5, "无成功结果", ha="center", va="center", transform=ax.transAxes)
        return

    tt_days = np.array([r["transfer_time"] * TU for r in success])
    total_dv = np.array([r["objective_value"] * VU / 1000 for r in success])

    sc = ax.scatter(tt_days, total_dv, c=total_dv, cmap="viridis", s=6, alpha=0.6)
    style_colorbar(plt.colorbar(sc, ax=ax, label="总 Δv (km/s)"), PLOT_CONFIG)
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
        fontsize=PLOT_CONFIG.legend,
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
    """绘制指定结果图形。
    
    Args:
        records: 调用方传入的参数值。
        sel_indices: 调用方传入的参数值。
        dro_orbit: 调用方传入的参数值。
        ro_orbit: 调用方传入的参数值。
        system: 调用方传入的参数值。
        dynamics: 调用方传入的参数值。
        save_path: 调用方传入的参数值。
        dpi: 调用方传入的参数值。
    
    Returns:
        None。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    n_sel = len(sel_indices)

    if n_sel == 1:
        rec = records[sel_indices[0]]
        departure_state = np.asarray(rec["departure_state"], dtype=np.float64)
        alpha = rec["alpha"]
        T = rec["transfer_time"]
        t_ins = rec["t_ins"]

        logger.info(f"积分转移轨道: α={alpha:.6f}, T={T:.4f} TU, t_ins={t_ins:.4f} TU ...")
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
            f"DRO→RO  α={alpha:.4f}  T={T:.2f} TU ({T * TU:.1f}天)\n"
            f"Δv_dep={dv1_km:.4f} km/s  Δv_ins={dv2_km:.4f} km/s  "
            f"Total={total_km:.4f} km/s"
        )
        ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

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
                logger.info(f"  [{cm_idx + 1}/{n_sel}] 已绘制")

        # 地球和月球
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
        ax.set_title(f"DRO→RO: {n_sel} 条转移轨道")
        ax.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")

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
        logger.info(f"Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


def main() -> None:
    """执行脚本主流程。
    
    Returns:
        None。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    parser = argparse.ArgumentParser(description="可视化 NLP 优化结果", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--file", type=str, default=None, help="optimization_results_*.json 路径（默认自动选最新）")
    parser.add_argument("--auto-latest", action="store_true", help="显式 opt-in：按 mtime 选最新 optimization_results_*.json")
    parser.add_argument("--save", type=str, default=None, help="保存图片路径")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--orbit", action="store_true", help="绘制转移轨道 3D 示意图")
    parser.add_argument("--time-dv", action="store_true", help="转移时间 vs Δv 散点图")
    parser.add_argument("--idx", type=str, default="best", help="选择结果：整数索引 / best / best:N / random / all")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-points", type=int, default=500, help="--orbit --idx all 时最多绘制条数")
    args = parser.parse_args()

    opt_path = _resolve_opt_input(args)
    if not opt_path.is_file():
        raise FileNotFoundError("未找到 optimization_results_*.json")
    logger.info(f"读取: {opt_path}")

    data = load_optimization_results(opt_path)
    records = _collect_nlp_records(data)
    n_success = sum(1 for r in records if r["success"])
    logger.info(f"结果总数: {len(records)}, 成功: {n_success}")

    meta = data.get("meta", {})
    logger.info(f"求解器: {meta.get('nlp_solver', 'N/A')}")
    logger.info(f"松弛速度约束: {meta.get('use_relaxed_velocity', 'N/A')}")

    if args.orbit:
        dro_orbit = load_orbit_from_json(str(DRO_FILE))
        ro_orbit = load_orbit_from_json(str(RO_FILE))
        with open(RO_FILE, encoding="utf-8") as f:
            roj = json.load(f)
        if "properties" in roj and "period" in roj["properties"]:
            ro_orbit.period = float(roj["properties"]["period"])

        system, dynamics = _build_dynamics()
        sel_indices = _select_indices(records, args.idx, args.seed, args.max_points)
        logger.info(f"绘制 {len(sel_indices)} 条轨道 (idx={args.idx})")

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
            logger.info(f"Saved: {png}")
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
            "--dpi", "150",                               # 图像 DPI
            "--idx", "best",                              # 选择结果索引
            "--seed", "0",                                # 随机种子
            "--max-points", "500",                        # --orbit --idx all 时最多绘制条数
        ]
        logger.debug("使用代码内置调试参数")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_optimize_result_dro_to_ro',
    description='绘制优化结果',
    script_path='tod/plot/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py',
    output_dir='output/transfer',
    group_label='DRO→RO',
    cli_params=[
        CliParam('--file', '优化结果文件', 'str', '', help='优化结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--auto-latest', '自动选最新结果', 'bool', '', help='选最新的 optimization_results_*.json；与 --file 互斥。', advanced=True),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='转移时间 vs Δv 散点图。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', 'best', help='整数索引、best、best:N、random 或 all。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大绘制轨道数', 'int', '500', help='--idx all 时最多绘制的条数。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率。', advanced=True),
    ],
)
