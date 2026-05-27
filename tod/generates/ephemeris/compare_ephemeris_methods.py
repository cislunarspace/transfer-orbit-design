"""compare_ephemeris_methods 星历转换脚本。

本模块将 CR3BP 轨道状态映射到真实星历模型，依赖 SPICE kernels（de440.bsp、naif0012.tls）和 UTC 参考历元。输入为 DRO/Halo 单轨道或轨道族 JSON，输出为含修正状态、残差和元数据的星历转换结果。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.ephemeris.compare_ephemeris_methods --help
"""

# pyright: reportAttributeAccessIssue=false


import json
import logging
import multiprocessing
import os
import time
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from e2m2e.algorithms import MultipleShooting, sample_patch_points, convert_to_j2000
from e2m2e.core import (
    CR3BP_System,
    EphemerisDynamics,
    EphemerisSystem,
    Orbit,
    SPICEManager,
    SynodicJ2000Transformation,
)
from tod.commons.constants import DU, MU, TU
from tod.plot.config import apply_standard_plot_config

logger = logging.getLogger(__name__)

# HomotopyEphemerisDynamics 和 BodyName 已从 e2m2e 中移除
# from e2m2e.core import HomotopyEphemerisDynamics, BodyName
HomotopyEphemerisDynamics = None  # type: ignore[assignment,misc] # placeholder for deprecated script

PLOT_CONFIG = apply_standard_plot_config()

project_root = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "ephemeris"

TU_SECONDS = TU * 86400

DRO_JSON_FILE = project_root / "output" / "dro" / "dro_31_3857864736.json"

N_PATCH_POINTS = 8
POSITION_CONTINUITY_TOL = (
    1e-6  # 比典型 1e-3 km 更严格；patch-point 连续性需要亚毫米精度
)
N_WORKERS = multiprocessing.cpu_count()

REFERENCE_EPOCH = "2025-06-21T11:00:06"
SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
BODIES = ["EARTH", "MOON", "SUN"]
BASE_BODIES = ["EARTH", "MOON"]
PERTURBATION_BODIES = ["SUN"]

HOMOTOPY_STEPS = [0.25, 0.5, 0.75, 1.0]
MAX_ITER_MS = 50
MS_TOLERANCE = POSITION_CONTINUITY_TOL

N_PERIODS = 3


def set_axes_equal(ax):
    """将三维坐标轴设置为等比例显示。
    
    Args:
        ax: 调用方传入的参数值。
    
    Returns:
        None。
    """
    x_range = ax.get_xlim()[1] - ax.get_xlim()[0]
    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    z_range = ax.get_zlim()[1] - ax.get_zlim()[0]
    max_range = max(x_range, y_range, z_range) / 2
    mid_x = np.mean(ax.get_xlim())
    mid_y = np.mean(ax.get_ylim())
    mid_z = np.mean(ax.get_zlim())
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)


def setup_shared_infrastructure():
    """执行 setup_shared_infrastructure 对应的处理逻辑。
    
    Returns:
        函数执行结果。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    logger.info("=" * 60)
    logger.info("Step 1: 公共初始化")
    logger.info("=" * 60)

    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    logger.info(f"  SPICE kernel: {kernel_path}")

    spice.load_kernel(kernel_path)

    try:
        reference_et = spice.utc_to_et(REFERENCE_EPOCH)
        logger.info(f"  参考历元: {REFERENCE_EPOCH} (ET={reference_et:.2f} s)")

        cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
        eph_system = EphemerisSystem(
            bodies=BODIES, spice=spice, origin="EARTH", frame="J2000"
        )

        dro_orbit = Orbit.load_from_file(filename=DRO_JSON_FILE, system=cr3bp_system)
        if dro_orbit.period is None:
            dro_orbit._estimate_period()
        if dro_orbit.period is None:
            raise ValueError("无法确定 DRO 轨道周期")
        logger.info(
            f"  DRO 周期: {dro_orbit.period:.6f} TU ({dro_orbit.period * TU:.2f} days)"
        )

        t_patch_syn, states_syn = sample_patch_points(dro_orbit, N_PATCH_POINTS)

        syn_j2000 = SynodicJ2000Transformation(cr3bp_system=cr3bp_system, spice=spice)
        t_patch_j2000, states_j2000 = convert_to_j2000(
            t_patch_syn, states_syn, syn_j2000, reference_et, TU
        )

        logger.info(f"  Patch points: {N_PATCH_POINTS}")
        logger.info(f"  坐标转换完成: Synodic → J2000")

        return {
            "spice": spice,
            "kernel_path": kernel_path,
            "cr3bp_system": cr3bp_system,
            "eph_system": eph_system,
            "syn_j2000": syn_j2000,
            "reference_et": reference_et,
            "dro_orbit": dro_orbit,
            "t_patch_j2000": t_patch_j2000,
            "states_j2000": states_j2000,
        }
    except Exception:
        spice.unload_kernel(kernel_path)
        raise


def run_direct_method(eph_system, t_patch_j2000, states_j2000):
    """运行对应计算流程。
    
    Args:
        eph_system: 调用方传入的参数值。
        t_patch_j2000: 调用方传入的参数值。
        states_j2000: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    logger.info(f"\n{'=' * 60}")
    logger.info("Step 2: 直接多重打靶法")
    logger.info(f"{'=' * 60}")

    eph_dynamics = EphemerisDynamics(system=eph_system)
    ms = MultipleShooting(
        dynamics=eph_dynamics,
        n_workers=N_WORKERS,
        kernel_dir=SPICE_KERNEL_DIR,
    )

    t0 = time.time()
    result = ms.correct(
        t_patch=t_patch_j2000,
        state_patch=states_j2000,
        var_time=True,
        max_iter=MAX_ITER_MS,
        tolerance=MS_TOLERANCE,
        verbose=True,
    )
    elapsed = time.time() - t0

    info = {
        "method": "direct_multiple_shooting",
        "converged": result.converged,
        "iterations": result.iterations,
        "max_residual": float(result.max_residual),
        "residual_history": [float(r) for r in result.residual_history],
        "time_s": round(elapsed, 3),
        "t_patch": result.t_patch,
        "state_patch": result.state_patch,
    }

    status = "收敛" if result.converged else "未收敛"
    logger.info(
        f"\n  [{status}] 迭代={result.iterations}, "
        f"残差={result.max_residual:.2e} km, 耗时={elapsed:.1f}s"
    )

    return info


def run_homotopy_method(eph_system, t_patch_j2000, states_j2000):
    """运行对应计算流程。
    
    Args:
        eph_system: 调用方传入的参数值。
        t_patch_j2000: 调用方传入的参数值。
        states_j2000: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    logger.info(f"\n{'=' * 60}")
    logger.info("Step 3: 同伦法")
    logger.info(f"{'=' * 60}")
    logger.info(f"  同伦路径: λ = {HOMOTOPY_STEPS}")

    total_t0 = time.time()
    homotopy_log = []

    current_t = t_patch_j2000.copy()
    current_states = states_j2000.copy()

    for step_idx, lam in enumerate(HOMOTOPY_STEPS):
        logger.info(f"\n  {'─' * 40}")
        logger.info(f"  λ = {lam:.4f} ({step_idx + 1}/{len(HOMOTOPY_STEPS)})")

        hdynamics = HomotopyEphemerisDynamics(  # type: ignore[misc]
            system=eph_system,
            base_bodies=BASE_BODIES,
            perturbation_bodies=PERTURBATION_BODIES,
            homotopy_param=lam,
        )
        ms = MultipleShooting(
            dynamics=hdynamics,
            n_workers=N_WORKERS,
            kernel_dir=SPICE_KERNEL_DIR,
        )

        t0_step = time.time()
        result = ms.correct(
            t_patch=current_t,
            state_patch=current_states,
            var_time=True,
            max_iter=MAX_ITER_MS,
            tolerance=MS_TOLERANCE,
            verbose=True,
        )
        dt_step = time.time() - t0_step

        step_info = {
            "lambda": lam,
            "converged": result.converged,
            "iterations": result.iterations,
            "max_residual": float(result.max_residual),
            "residual_history": [float(r) for r in result.residual_history],
            "time_s": round(dt_step, 3),
        }
        homotopy_log.append(step_info)

        if result.converged:
            current_t = result.t_patch.copy()
            current_states = result.state_patch.copy()
            logger.info(
                f"    iter={result.iterations}, "
                f"res={result.max_residual:.2e}, t={dt_step:.1f}s"
            )
        else:
            logger.warning(f"    未收敛, 尝试减半步长...")
            if step_idx == 0:
                logger.error(f"    首步不收敛，终止")
                break

            sub_steps = np.linspace(HOMOTOPY_STEPS[step_idx - 1], lam, 3)[1:]
            sub_ok = True
            for sub_lam in sub_steps:
                hdynamics_sub = HomotopyEphemerisDynamics(  # type: ignore[misc]
                    system=eph_system,
                    base_bodies=BASE_BODIES,
                    perturbation_bodies=PERTURBATION_BODIES,
                    homotopy_param=sub_lam,
                )
                ms_sub = MultipleShooting(
                    dynamics=hdynamics_sub,
                    n_workers=N_WORKERS,
                    kernel_dir=SPICE_KERNEL_DIR,
                )
                t0_sub = time.time()
                result_sub = ms_sub.correct(
                    t_patch=current_t,
                    state_patch=current_states,
                    var_time=True,
                    max_iter=MAX_ITER_MS,
                    tolerance=MS_TOLERANCE,
                    verbose=False,
                )
                dt_sub = time.time() - t0_sub

                homotopy_log.append(
                    {
                        "lambda": float(sub_lam),
                        "converged": result_sub.converged,
                        "iterations": result_sub.iterations,
                        "max_residual": float(result_sub.max_residual),
                        "residual_history": [
                            float(r) for r in result_sub.residual_history
                        ],
                        "time_s": round(dt_sub, 3),
                        "note": "sub-step",
                    }
                )

                if result_sub.converged:
                    current_t = result_sub.t_patch.copy()
                    current_states = result_sub.state_patch.copy()
                    logger.info(
                        f"      子步 λ={sub_lam:.4f} ok, res={result_sub.max_residual:.2e}"
                    )
                else:
                    logger.info(f"      子步 λ={sub_lam:.4f} 失败")
                    sub_ok = False
                    break

            if not sub_ok:
                logger.error(f"    减半步长后仍不收敛")
                break

    total_dt = time.time() - total_t0
    total_iters = sum(s["iterations"] for s in homotopy_log)
    final_converged = homotopy_log[-1]["converged"] if homotopy_log else False
    final_residual = homotopy_log[-1]["max_residual"] if homotopy_log else float("inf")

    logger.info(f"\n  同伦法完成: 总耗时={total_dt:.1f}s, 总迭代={total_iters}")

    info = {
        "method": "homotopy",
        "converged": final_converged,
        "total_iterations": total_iters,
        "max_residual": final_residual,
        "time_s": round(total_dt, 3),
        "homotopy_log": homotopy_log,
        "t_patch": current_t,
        "state_patch": current_states,
    }

    return info


def validate_result(info, eph_system):
    """验证修正或优化结果是否满足容差要求。
    
    Args:
        info: 调用方传入的参数值。
        eph_system: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    dynamics = EphemerisDynamics(system=eph_system)
    states = info["state_patch"]
    times = info["t_patch"]
    n_seg = len(states) - 1

    pos_errors = []
    for i in range(n_seg):
        prop = dynamics.propagate(states[i], (times[i], times[i + 1]))
        propagated_final = prop["states"][-1]
        pos_error = np.linalg.norm(propagated_final[:3] - states[i + 1, :3])
        pos_errors.append(float(pos_error))
        logger.info(f"    段 {i}→{i + 1}: {pos_error:.2e} km")

    info["position_errors_km"] = pos_errors
    info["max_position_error_km"] = max(pos_errors) if pos_errors else float("inf")
    return info


def print_comparison_table(direct_info, homotopy_info):
    """执行 print_comparison_table 对应的处理逻辑。
    
    Args:
        direct_info: 调用方传入的参数值。
        homotopy_info: 调用方传入的参数值。
    
    Returns:
        None。
    """
    logger.info(f"\n{'=' * 70}")
    logger.info("对比结果")
    logger.info(f"{'=' * 70}")

    header = f"{'指标':<22} {'直接多重打靶':>18} {'同伦法':>18}"
    sep = "─" * 62
    logger.info(header)
    logger.info(sep)

    d_conv = "是" if direct_info["converged"] else "否"
    h_conv = "是" if homotopy_info["converged"] else "否"
    logger.info(f"{'收敛':<22} {d_conv:>18} {h_conv:>18}")

    logger.info(
        f"{'总迭代次数':<22} {direct_info['iterations']:>18} "
        f"{homotopy_info['total_iterations']:>18}"
    )

    logger.info(
        f"{'运行时间 (s)':<22} {direct_info['time_s']:>18.2f} {homotopy_info['time_s']:>18.2f}"
    )

    logger.info(
        f"{'最终残差 (km)':<22} {direct_info['max_residual']:>18.2e} "
        f"{homotopy_info['max_residual']:>18.2e}"
    )

    d_perr = direct_info.get("max_position_error_km", float("inf"))
    h_perr = homotopy_info.get("max_position_error_km", float("inf"))
    logger.info(f"{'最大位置误差 (km)':<22} {d_perr:>18.2e} {h_perr:>18.2e}")

    d_ms_steps = 1
    h_ms_steps = len(homotopy_info["homotopy_log"])
    logger.info(f"{'MS 修正次数':<22} {d_ms_steps:>18} {h_ms_steps:>18}")

    logger.info(sep)

    if direct_info["time_s"] > 0 and homotopy_info["time_s"] > 0:
        speedup = direct_info["time_s"] / homotopy_info["time_s"]
        logger.info(f"  时间比 (直接/同伦): {speedup:.2f}x")
    if direct_info["iterations"] > 0 and homotopy_info["total_iterations"] > 0:
        iter_ratio = direct_info["iterations"] / homotopy_info["total_iterations"]
        logger.info(f"  迭代比 (直接/同伦): {iter_ratio:.2f}x")


def plot_residual_convergence(direct_info, homotopy_info):
    """绘制指定结果图形。
    
    Args:
        direct_info: 调用方传入的参数值。
        homotopy_info: 调用方传入的参数值。
    
    Returns:
        None。
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    d_res = direct_info["residual_history"]
    ax1.semilogy(
        range(1, len(d_res) + 1),
        d_res,
        "o-",
        color="royalblue",
        linewidth=2,
        markersize=6,
        label="直接多重打靶法",
    )
    ax1.axhline(
        y=MS_TOLERANCE,
        color="red",
        linestyle="--",
        linewidth=1,
        label=f"容差 ({MS_TOLERANCE:.0e} km)",
    )
    ax1.set_xlabel("迭代次数")
    ax1.set_ylabel("最大残差 (km)")
    ax1.set_title("直接多重打靶法 — 残差收敛")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    cum_iter = 0
    n_steps = len(homotopy_info["homotopy_log"])
    colors = matplotlib.colormaps["RdYlGn"](np.linspace(0.2, 0.8, max(n_steps, 1)))
    for i, step in enumerate(homotopy_info["homotopy_log"]):
        res_hist = step["residual_history"]
        iters = range(cum_iter + 1, cum_iter + len(res_hist) + 1)
        label = f"λ={step['lambda']:.2f}"
        if step.get("note") == "sub-step":
            label += " (子步)"
        ax2.semilogy(
            iters,
            res_hist,
            "o-",
            color=colors[i],
            linewidth=2,
            markersize=5,
            label=label,
        )
        cum_iter += len(res_hist)
    ax2.axhline(
        y=MS_TOLERANCE,
        color="red",
        linestyle="--",
        linewidth=1,
        label=f"容差 ({MS_TOLERANCE:.0e} km)",
    )
    ax2.set_xlabel("累计迭代次数")
    ax2.set_ylabel("最大残差 (km)")
    ax2.set_title("同伦法 — 残差收敛")
    ax2.legend(fontsize=PLOT_CONFIG.legend)
    ax2.grid(True, alpha=0.3)

    fig.suptitle("DRO→星历模型修正：残差收敛对比", fontsize=PLOT_CONFIG.suptitle, y=1.02)
    plt.tight_layout()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"residual_comparison_{ts}.png"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    logger.info(f"  残差对比图: {out_path}")
    plt.close(fig)


def plot_trajectory_comparison(direct_info, homotopy_info, setup):
    """绘制指定结果图形。
    
    Args:
        direct_info: 调用方传入的参数值。
        homotopy_info: 调用方传入的参数值。
        setup: 调用方传入的参数值。
    
    Returns:
        None。
    """
    eph_system = setup["eph_system"]
    dynamics = EphemerisDynamics(system=eph_system)
    period_tu = setup["dro_orbit"].period

    fig = plt.figure(figsize=(20, 9))

    d_states = direct_info["state_patch"]
    d_times = direct_info["t_patch"]
    state0_d = d_states[0]
    t0_d = d_times[0]
    t_end_d = t0_d + N_PERIODS * period_tu * TU_SECONDS
    prop_d = dynamics.propagate(state0_d, (t0_d, t_end_d))
    traj_d = prop_d["states"]

    ax1 = fig.add_subplot(121, projection="3d")
    ax1.plot(
        traj_d[:, 0] / DU,
        traj_d[:, 1] / DU,
        traj_d[:, 2] / DU,
        color="royalblue",
        linewidth=1.5,
        label=f"直接法 ({N_PERIODS}T)",
    )
    ax1.scatter(0, 0, 0, color="green", s=100, zorder=5, label="Earth")
    ax1.set_xlabel("X (×10⁵ km)")
    ax1.set_ylabel("Y (×10⁵ km)")
    ax1.set_zlabel("Z (×10⁵ km)")
    d_status = "收敛" if direct_info["converged"] else "未收敛"
    ax1.set_title(f"直接多重打靶法 ({d_status})", fontsize=PLOT_CONFIG.title)
    ax1.legend(fontsize=PLOT_CONFIG.legend)
    ax1.view_init(elev=25, azim=-60)
    set_axes_equal(ax1)

    h_states = homotopy_info["state_patch"]
    h_times = homotopy_info["t_patch"]
    state0_h = h_states[0]
    t0_h = h_times[0]
    t_end_h = t0_h + N_PERIODS * period_tu * TU_SECONDS
    prop_h = dynamics.propagate(state0_h, (t0_h, t_end_h))
    traj_h = prop_h["states"]

    ax2 = fig.add_subplot(122, projection="3d")
    ax2.plot(
        traj_h[:, 0] / DU,
        traj_h[:, 1] / DU,
        traj_h[:, 2] / DU,
        color="crimson",
        linewidth=1.5,
        label=f"同伦法 ({N_PERIODS}T)",
    )
    ax2.scatter(0, 0, 0, color="green", s=100, zorder=5, label="Earth")
    ax2.set_xlabel("X (×10⁵ km)")
    ax2.set_ylabel("Y (×10⁵ km)")
    ax2.set_zlabel("Z (×10⁵ km)")
    h_status = "收敛" if homotopy_info["converged"] else "未收敛"
    ax2.set_title(f"同伦法 ({h_status})", fontsize=PLOT_CONFIG.title)
    ax2.legend(fontsize=PLOT_CONFIG.legend)
    ax2.view_init(elev=25, azim=-60)
    set_axes_equal(ax2)

    fig.suptitle(
        f"DRO→星历模型修正：轨迹对比\nref: {REFERENCE_EPOCH}, bodies: {', '.join(BODIES)}",
        fontsize=PLOT_CONFIG.suptitle,
        y=1.02,
    )
    plt.tight_layout()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"trajectory_comparison_{ts}.png"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    logger.info(f"  轨迹对比图: {out_path}")
    plt.close(fig)


def save_comparison_report(direct_info, homotopy_info, setup):
    """保存计算或绘图结果。
    
    Args:
        direct_info: 调用方传入的参数值。
        homotopy_info: 调用方传入的参数值。
        setup: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = {
        "timestamp": ts,
        "reference_epoch": REFERENCE_EPOCH,
        "bodies": BODIES,
        "n_patch_points": N_PATCH_POINTS,
        "tolerance_km": MS_TOLERANCE,
        "max_iter_per_step": MAX_ITER_MS,
        "cr3bp_dro": {
            "source_file": str(DRO_JSON_FILE),
            "x0": setup["dro_orbit"].states[0][0],
            "vy0": setup["dro_orbit"].states[0][4],
            "period_tu": setup["dro_orbit"].period,
        },
        "direct_method": {
            "converged": direct_info["converged"],
            "iterations": direct_info["iterations"],
            "max_residual_km": direct_info["max_residual"],
            "time_s": direct_info["time_s"],
            "position_errors_km": direct_info["position_errors_km"],
            "max_position_error_km": direct_info["max_position_error_km"],
            "residual_history": direct_info["residual_history"],
            "corrected_states": direct_info["state_patch"].tolist(),
            "corrected_times_et": direct_info["t_patch"].tolist(),
        },
        "homotopy_method": {
            "converged": homotopy_info["converged"],
            "total_iterations": homotopy_info["total_iterations"],
            "max_residual_km": homotopy_info["max_residual"],
            "time_s": homotopy_info["time_s"],
            "n_ms_steps": len(homotopy_info["homotopy_log"]),
            "homotopy_log": homotopy_info["homotopy_log"],
            "position_errors_km": homotopy_info["position_errors_km"],
            "max_position_error_km": homotopy_info["max_position_error_km"],
            "corrected_states": homotopy_info["state_patch"].tolist(),
            "corrected_times_et": homotopy_info["t_patch"].tolist(),
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"methods_comparison_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"  对比报告: {out_file}")

    return out_file


def main():
    """执行脚本主流程。
    
    Returns:
        None。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    raise NotImplementedError(
        "HomotopyEphemerisDynamics has been removed from e2m2e; "
        "this comparison script is deprecated."
    )
    logger.info("DRO→星历模型修正：直接法 vs 同伦法效率对比")  # type: ignore[unreachable]
    logger.info(f"参考历元: {REFERENCE_EPOCH}")
    logger.info(f"Patch points: {N_PATCH_POINTS}")
    logger.info(f"容差: {MS_TOLERANCE:.1e} km")

    setup = setup_shared_infrastructure()

    try:
        eph_system = setup["eph_system"]
        t_patch = setup["t_patch_j2000"]
        states = setup["states_j2000"]

        direct_info = run_direct_method(eph_system, t_patch.copy(), states.copy())
        logger.info("\n  直接法验证:")
        direct_info = validate_result(direct_info, eph_system)

        homotopy_info = run_homotopy_method(eph_system, t_patch.copy(), states.copy())
        logger.info("\n  同伦法验证:")
        homotopy_info = validate_result(homotopy_info, eph_system)

        print_comparison_table(direct_info, homotopy_info)

        plot_residual_convergence(direct_info, homotopy_info)
        plot_trajectory_comparison(direct_info, homotopy_info, setup)
        save_comparison_report(direct_info, homotopy_info, setup)

    finally:
        setup["spice"].unload_kernel(setup["kernel_path"])


if __name__ == "__main__":
    main()
