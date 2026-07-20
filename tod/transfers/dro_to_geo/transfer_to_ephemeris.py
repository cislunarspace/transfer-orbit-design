"""transfer_to_ephemeris 脚本。

将 DRO→GEO 优化后的转移轨迹从 CR3BP synodic 坐标系转换到星历模型（J2000），
使用 e2m2e 的 SynodicJ2000System 进行坐标转换，
在星历模型中前向传播并与 CR3BP 解对比。

注意：本脚本目前只做坐标转换和星历模型传播展示，
不做转移轨迹的多重打靶修正（那是后续工作）。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.dro_to_geo.transfer_to_ephemeris \
           --opt-file output/transfer/optimization_dro_geo_1781070822.json \
           --reference-epoch 2025-06-21T11:00:06
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SPICE_KERNEL_DIR = Path(
    project_root.parent / "e2m2e" / "kernels"
)

def parse_args():
    parser = argparse.ArgumentParser(
        description="将 DRO→GEO 优化转移轨迹转换到星历模型",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--opt-file", type=str, required=True,
        help="优化结果 JSON 文件路径（optimization_dro_geo_*.json）"
    )
    parser.add_argument(
        "--select-by", choices=["transfer_time", "objective"], default="transfer_time",
        help="选择标准：transfer_time=选最短转移时间，objective=选最优目标函数"
    )
    parser.add_argument(
        "--reference-epoch", type=str, default="2025-06-21T11:00:06",
        help="UTC 参考历元，用于 synodic→J2000 转换"
    )
    parser.add_argument(
        "--spice-kernel-dir", type=str, default=str(DEFAULT_SPICE_KERNEL_DIR),
        help="SPICE kernel 目录"
    )
    parser.add_argument(
        "--bodies", type=str, default="EARTH,MOON,SUN",
        help="参与的天体列表，逗号分隔"
    )
    parser.add_argument(
        "--n-samples", type=int, default=1000,
        help="积分采样点数（用于轨迹绘制）"
    )
    parser.add_argument(
        "--output-file", type=str, default=None,
        help="输出 JSON 路径，默认自动生成"
    )
    parser.add_argument(
        "--plot-save", type=str, default=None,
        help="保存轨迹对比图路径"
    )
    return parser.parse_args()

def load_optimization_results(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def select_best_result(data: dict, select_by: str) -> dict:
    """选取最优结果（最短转移时间或最优目标函数）。"""
    results = data.get("results", [])
    success = [r for r in results if r.get("nlp", {}).get("success", False)]
    if not success:
        raise ValueError("无成功优化结果")

    if select_by == "transfer_time":
        best = min(success, key=lambda r: r["nlp"]["transfer_time"])
    else:
        best = min(success, key=lambda r: r["nlp"]["objective_value"])
    return best

def cr3bp_propagate(state0: np.ndarray, transfer_time: float, dynamics) -> tuple[np.ndarray, np.ndarray]:
    """在 CR3BP synodic 坐标系中传播转移轨迹。"""
    step = max(0.01, dynamics.max_step)
    n_steps = int(transfer_time / step) + 1
    t_eval = np.linspace(0.0, transfer_time, n_steps)

    result = dynamics.propagate(
        initial_state=state0,
        t_span=(0.0, transfer_time),
        t_eval=t_eval,
        with_stm=False,
        with_jacobi=False,
    )
    return result["states"], result["time"]

def synodic_to_j2000_states(
    states_syn: np.ndarray,
    times_syn: np.ndarray,
    reference_et: float,
    cr3bp_system,
    spice,
) -> np.ndarray:
    """将 synodic 状态序列批量转换到 J2000。"""
    from e2m2e.core import SynodicJ2000System

    transform = SynodicJ2000System(cr3bp_system=cr3bp_system, spice=spice)

    # 转换所有时间点到 ET
    from tod.commons.constants import TU
    tu_seconds = TU * 86400
    times_et = reference_et + times_syn * tu_seconds

    # 批量转换状态
    states_j2000 = transform.batch_synodic_to_j2000(
        states_syn=states_syn,
        t_syn_arr=times_syn,
        et0=reference_et,
    )
    return states_j2000

def propagate_ephemeris(
    state0_j2000: np.ndarray,
    t_start_et: float,
    t_end_et: float,
    eph_dynamics,
    n_samples: int,
) -> tuple[np.ndarray, np.ndarray]:
    """在星历模型中传播转移轨迹。"""
    times_et = np.linspace(t_start_et, t_end_et, n_samples)
    dt = times_et[1] - times_et[0]

    states = [state0_j2000]
    for i in range(1, len(times_et)):
        result = eph_dynamics.propagate(
            initial_state=states[-1],
            t_span=(times_et[i - 1], times_et[i]),
            t_eval=None,
            with_stm=False,
        )
        states.append(result["states"][-1])

    return np.array(states), times_et

def plot_comparison(
    cr3bp_states_km: np.ndarray,
    eph_states: np.ndarray,
    save_path: str | None = None,
) -> None:
    """绘制 CR3BP 与星历模型轨迹对比。"""
    import matplotlib
    try:
        matplotlib.use("TkAgg")
    except ImportError:
        pass
    import matplotlib.pyplot as plt
    from tod.plot.config import apply_standard_plot_config
    apply_standard_plot_config()

    fig = plt.figure(figsize=(16, 5))

    # XY 平面
    ax1 = fig.add_subplot(131)
    ax1.plot(cr3bp_states_km[:, 0], cr3bp_states_km[:, 1], "b-", lw=1.5, alpha=0.8, label="CR3BP")
    ax1.plot(eph_states[:, 0], eph_states[:, 1], "r--", lw=1.5, alpha=0.8, label="星历模型")
    ax1.scatter([eph_states[0, 0]], [eph_states[0, 1]], c="green", s=50, zorder=5, label="出发")
    ax1.scatter([eph_states[-1, 0]], [eph_states[-1, 1]], c="orange", s=50, zorder=5, label="终点")
    ax1.set_xlabel("x (km)")
    ax1.set_ylabel("y (km)")
    ax1.set_title("XY 平面")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_aspect("equal")

    # XZ 平面
    ax2 = fig.add_subplot(132)
    ax2.plot(cr3bp_states_km[:, 0], cr3bp_states_km[:, 2], "b-", lw=1.5, alpha=0.8, label="CR3BP")
    ax2.plot(eph_states[:, 0], eph_states[:, 2], "r--", lw=1.5, alpha=0.8, label="星历模型")
    ax2.set_xlabel("x (km)")
    ax2.set_ylabel("z (km)")
    ax2.set_title("XZ 平面")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # 3D
    ax3 = fig.add_subplot(133, projection="3d")
    ax3.plot(cr3bp_states_km[:, 0], cr3bp_states_km[:, 1], cr3bp_states_km[:, 2],
             "b-", lw=1.5, alpha=0.8, label="CR3BP")
    ax3.plot(eph_states[:, 0], eph_states[:, 1], eph_states[:, 2],
             "r--", lw=1.5, alpha=0.8, label="星历模型")
    ax3.set_xlabel("x (km)")
    ax3.set_ylabel("y (km)")
    ax3.set_zlabel("z (km)")
    ax3.set_title("3D 视图")
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)

    fig.suptitle("DRO→GEO 转移轨迹：CR3BP vs 星历模型", fontsize=14)
    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
        print(f"\n图片已保存: {save_path}")
    else:
        plt.show()
    plt.close(fig)

def main():
    args = parse_args()

    opt_path = Path(args.opt_file)
    if not opt_path.is_file():
        raise FileNotFoundError(f"未找到优化结果文件: {opt_path}")

    print(f"读取优化结果: {opt_path}")
    data = load_optimization_results(opt_path)
    best = select_best_result(data, args.select_by)
    nlp = best["nlp"]

    from tod.commons.constants import DU, VU, TU

    T_days = nlp["transfer_time"] * TU * 86400 / 86400  # TU * days/TU = days
    dv_total = nlp["objective_value"] * VU * 1000  # m/s
    dv1 = nlp["delta_v1"] * VU * 1000
    dv2 = nlp["delta_v2"] * VU * 1000

    print(f"\n=== 选中结果 ({args.select_by}) ===")
    print(f"  search_index: {best['search_index']}")
    print(f"  alpha: {nlp['alpha']:.4f}")
    print(f"  transfer_time: {nlp['transfer_time']:.4f} TU = {nlp['transfer_time'] * TU:.1f} 天")
    print(f"  objective_value: {nlp['objective_value']:.4f} VU = {dv_total:.0f} m/s")
    print(f"  delta_v1: {nlp['delta_v1']:.4f} VU = {dv1:.0f} m/s")
    print(f"  delta_v2: {nlp['delta_v2']:.4f} VU = {dv2:.0f} m/s")

    # 构建 CR3BP 动力学
    print(f"\n1. CR3BP 传播...")
    from e2m2e.core import CR3BP_System, CR3BP_Dynamics
    from tod.commons.orbits import compute_departure_velocity
    import tod.commons.constants as _tod_constants

    system = CR3BP_System(mu=_tod_constants.MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = 1.0 / (24.0 * _tod_constants.TU)

    # departure_state 是未扰动的原始 DRO 状态，需要用 NLP 优化的 alpha 施加速度扰动
    departure_state_raw = np.array(best["departure_state"], dtype=float)
    alpha = nlp["alpha"]
    v_perturbed = compute_departure_velocity(departure_state_raw, alpha)
    state0 = np.concatenate([departure_state_raw[:3], v_perturbed])
    print(f"  施加 α={alpha:.4f} 速度扰动，dv1={nlp['delta_v1']:.4f} VU")

    transfer_time = nlp["transfer_time"]

    cr3bp_states, cr3bp_times = cr3bp_propagate(state0, transfer_time, dynamics)
    print(f"  CR3BP 积分点数: {len(cr3bp_states)}")
    print(f"  终点位置 (synodic DU): [{cr3bp_states[-1, 0]:.6f}, {cr3bp_states[-1, 1]:.6f}, {cr3bp_states[-1, 2]:.6f}]")

    # 加载 SPICE
    print(f"\n2. 加载 SPICE kernels...")
    from e2m2e.core.spice import SPICEManager
    from e2m2e.core.ephemeris_system import EphemerisSystem
    from e2m2e.core.ephemeris_dynamics import EphemerisDynamics
    import spiceypy

    spice = SPICEManager()
    spice_kernel_dir = Path(args.spice_kernel_dir)
    kernel_path = spice.find_ephemeris_kernel(str(spice_kernel_dir))
    leapseconds_path = spice_kernel_dir / "naif0012.tls"
    spiceypy.furnsh(str(leapseconds_path))
    spice.load_kernel(kernel_path)

    reference_et = float(spice.utc_to_et(args.reference_epoch))
    print(f"  参考历元 ET: {reference_et:.1f} s")

    # Synodic → J2000 转换
    print(f"\n3. Synodic → J2000 坐标转换...")
    states_j2000 = synodic_to_j2000_states(
        cr3bp_states, cr3bp_times, reference_et, system, spice
    )
    print(f"  转换后状态数: {len(states_j2000)}")
    print(f"  出发点 J2000 (km): [{states_j2000[0, 0]:.1f}, {states_j2000[0, 1]:.1f}, {states_j2000[0, 2]:.1f}]")
    print(f"  终点 J2000 (km): [{states_j2000[-1, 0]:.1f}, {states_j2000[-1, 1]:.1f}, {states_j2000[-1, 2]:.1f}]")

    # 星历模型传播
    print(f"\n4. 星历模型传播（仅展示，未修正）...")
    bodies = tuple(b.upper() for b in args.bodies.split(",") if b.strip())
    eph_system = EphemerisSystem(
        bodies=list(bodies),
        spice=spice,
        origin="EARTH",
        frame="J2000",
    )
    eph_dynamics = EphemerisDynamics(system=eph_system)

    t_start_et = reference_et
    t_end_et = reference_et + transfer_time * _tod_constants.TU * 86400

    # 使用初始状态的 J2000 转换值作为星历传播初值
    state0_j2000 = states_j2000[0]

    # 星历传播
    times_et = np.linspace(t_start_et, t_end_et, args.n_samples)
    eph_states = [state0_j2000]
    for i in range(1, len(times_et)):
        dt = times_et[i] - times_et[i - 1]
        result = eph_dynamics.propagate(
            initial_state=eph_states[-1],
            t_span=(times_et[i - 1], times_et[i]),
            t_eval=None,
            with_stm=False,
        )
        eph_states.append(result["states"][-1])
    eph_states = np.array(eph_states)

    print(f"  星历积分点数: {len(eph_states)}")
    print(f"  终点 J2000 (km): [{eph_states[-1, 0]:.1f}, {eph_states[-1, 1]:.1f}, {eph_states[-1, 2]:.1f}]")

    # 终点差异
    diff = eph_states[-1] - states_j2000[-1]
    diff_pos = np.linalg.norm(diff[:3])
    diff_vel = np.linalg.norm(diff[3:])
    print(f"\n  终点位置差异 (星历 - 转换): {diff_pos:.1f} km")
    print(f"  终点速度差异: {diff_vel:.3f} km/s")

    # 保存结果
    output_data = {
        "metadata": {
            "source_file": str(opt_path),
            "select_by": args.select_by,
            "selected_search_index": best["search_index"],
            "reference_epoch": args.reference_epoch,
            "reference_et_s": reference_et,
            "bodies": list(bodies),
        },
        "cr3bp": {
            "departure_state": best["departure_state"],
            "alpha": nlp["alpha"],
            "transfer_time_TU": nlp["transfer_time"],
            "transfer_time_days": nlp["transfer_time"] * _tod_constants.TU,
            "delta_v1_VU": nlp["delta_v1"],
            "delta_v1_m_s": dv1,
            "delta_v2_VU": nlp["delta_v2"],
            "delta_v2_m_s": dv2,
            "objective_value_VU": nlp["objective_value"],
            "objective_value_m_s": dv_total,
            "trajectory_states_synodic": cr3bp_states.tolist(),
            "trajectory_times_TU": cr3bp_times.tolist(),
        },
        "ephemeris": {
            "trajectory_states_j2000_km": states_j2000.tolist(),
            "trajectory_times_et_s": (reference_et + cr3bp_times * _tod_constants.TU * 86400).tolist(),
            "propagated_states_j2000_km": eph_states.tolist(),
            "propagated_times_et_s": times_et.tolist(),
            "endpoint_position_diff_km": diff_pos,
            "endpoint_velocity_diff_km_s": diff_vel,
        },
    }

    if args.output_file:
        out_path = Path(args.output_file)
    else:
        out_path = project_root / "output" / "transfer" / f"transfer_ephemeris_{int(time.time())}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {out_path}")

    # 绘图
    if args.plot_save:
        cr3bp_states_km = cr3bp_states * DU
        plot_comparison(cr3bp_states_km, eph_states, args.plot_save)

    print("\n完成。")

if __name__ == "__main__":
    main()
