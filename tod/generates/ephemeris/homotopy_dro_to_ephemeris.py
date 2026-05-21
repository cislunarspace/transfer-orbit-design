"""
DRO 轨道 CR3BP → 星历模型 修正（同伦法）

使用摄动天体逐步引入的同伦策略，将 CR3BP 中的 3:1 DRO 轨道
转换到高精度星历模型下。相比直接多重打靶法，同伦法通过分阶段
增加摄动天体引力，提高收敛成功率和计算效率。

同伦建模（方案 A）:
    在 J2000 惯性系下，逐步引入 Sun 的引力:
    - λ=0: 仅 Earth + Moon（接近 CRTBP 的星历等效模型）
    - λ=1: Earth + Moon + Sun（完整星历模型）

    加速度: a(r,t,λ) = Σ_{base} a_b + λ · Σ_{perturbation} a_p

工作流:
    Step 1: 从 JSON 文件加载 DRO 轨道
    Step 2: 采样 patch points，synodic → J2000 转换
    Step 3: Phase 1 — λ=0, E+M only, MultipleShooting 修正
    Step 4: Phase 2 — λ: 0→1, 自然延拓逐步引入 Sun
    Step 5: 验证修正后位置连续性

依赖:
    e2m2e: SPICEManager, EphemerisSystem, HomotopyEphemerisDynamics,
           SynodicJ2000Transformation, MultipleShooting
    SPICE kernels: de435.bsp (or de440.bsp), naif0012.tls
"""

import json
import logging
import multiprocessing
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from e2m2e.algorithms import MultipleShooting, sample_patch_points, convert_to_j2000
from e2m2e.core import Orbit, CR3BP_System
from e2m2e.core import SPICEManager, EphemerisSystem
# HomotopyEphemerisDynamics and BodyName have been removed from e2m2e
# from e2m2e.core import HomotopyEphemerisDynamics
# from e2m2e.core import SynodicJ2000Transformation, BodyName
from e2m2e.core import SynodicJ2000Transformation
from tod.commons.constants import DU, MU, TU

logger = logging.getLogger(__name__)

HomotopyEphemerisDynamics = None  # type: ignore[assignment,misc] # placeholder for deprecated script

project_root = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "ephemeris"

TU_SECONDS = TU * 86400
VU = DU / TU_SECONDS

DRO_JSON_FILE = project_root / "output" / "dro" / "dro_31_3857864736.json"

N_PATCH_POINTS = 8
POSITION_CONTINUITY_TOL = 1e-3
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


def load_dro_orbit(system):
    logger.info("=" * 60)
    logger.info("Step 1: 加载 DRO 轨道 (JSON)")
    logger.info("=" * 60)

    dro_orbit = Orbit.load_from_file(filename=DRO_JSON_FILE, system=system)

    if dro_orbit.period is None:
        dro_orbit._estimate_period()

    if dro_orbit.period is None:
        raise ValueError("无法确定 DRO 轨道周期")

    logger.info(f"  文件: {DRO_JSON_FILE.name}")
    logger.info(f"  状态数: {len(dro_orbit.states)}")
    period = dro_orbit.period
    logger.info(f"  周期: {period:.6f} TU ({period * TU:.2f} days)")
    logger.info(f"  初始状态: {dro_orbit.states[0]}")
    return dro_orbit


def prepare_patch_points(dro_orbit, cr3bp_system, spice, reference_et):
    logger.info(f"\n{'=' * 60}")
    logger.info("Step 2: 采样 patch points + Synodic → J2000")
    logger.info(f"{'=' * 60}")

    t_patch_syn, states_syn = sample_patch_points(dro_orbit, N_PATCH_POINTS)

    syn_j2000 = SynodicJ2000Transformation(
        cr3bp_system=cr3bp_system,
        spice=spice,
    )

    t_patch_j2000, states_j2000 = convert_to_j2000(
        t_patch_syn, states_syn, syn_j2000, reference_et, TU
    )

    logger.info(f"  参考历元: {REFERENCE_EPOCH} (ET={reference_et:.2f} s)")
    logger.info(f"  Patch points: {N_PATCH_POINTS}")
    for i in range(N_PATCH_POINTS):
        r = np.linalg.norm(states_j2000[i, :3])
        logger.info(f"  Patch {i}: ET={t_patch_j2000[i]:.2f}, r={r:.0f} km")

    return t_patch_j2000, states_j2000


def run_homotopy_correction(t_patch_j2000, states_j2000, eph_system):
    logger.info(f"\n{'=' * 60}")
    logger.info("Step 3-4: 同伦法修正 (Homotopy Correction)")
    logger.info(f"{'=' * 60}")
    logger.info(f"  同伦路径: λ = {HOMOTOPY_STEPS}")
    logger.info(f"  基础天体: {BASE_BODIES}")
    logger.info(f"  摄动天体: {PERTURBATION_BODIES}")
    logger.info(f"  收敛容差: {MS_TOLERANCE:.1e} km")
    logger.info(f"  并行 workers: {N_WORKERS}")

    total_t0 = time.time()
    homotopy_log = []

    current_t = t_patch_j2000.copy()
    current_states = states_j2000.copy()

    result = None
    for step_idx, lam in enumerate(HOMOTOPY_STEPS):
        logger.info(f"\n{'─' * 50}")
        logger.info(f"  Homotopy step {step_idx + 1}/{len(HOMOTOPY_STEPS)}: λ = {lam:.4f}")
        logger.info(f"{'─' * 50}")

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
            "time_s": round(dt_step, 2),
        }
        homotopy_log.append(step_info)

        if result.converged:
            logger.info(
                f"  λ={lam:.4f} 收敛! 迭代={result.iterations}, "
                f"残差={result.max_residual:.2e} km, 耗时={dt_step:.1f}s"
            )
            current_t = result.t_patch.copy()
            current_states = result.state_patch.copy()
        else:
            logger.warning(f"  λ={lam:.4f} 未收敛! 残差={result.max_residual:.2e} km")
            logger.info(f"  尝试减半步长重新延拓...")

            if step_idx == 0:
                logger.error(f"  λ=0 阶段即不收敛，终止")
                return result, homotopy_log, total_t0

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
                        "time_s": round(dt_sub, 2),
                        "note": "sub-step",
                    }
                )

                if result_sub.converged:
                    current_t = result_sub.t_patch.copy()
                    current_states = result_sub.state_patch.copy()
                    logger.info(
                        f"    子步 λ={sub_lam:.4f} 收敛, 残差={result_sub.max_residual:.2e}"
                    )
                else:
                    logger.info(
                        f"    子步 λ={sub_lam:.4f} 仍未收敛, 残差={result_sub.max_residual:.2e}"
                    )
                    sub_ok = False
                    break

            if not sub_ok:
                logger.error(f"  减半步长后仍不收敛，使用当前最优解")
                break

    total_dt = time.time() - total_t0
    logger.info(f"\n{'=' * 60}")
    logger.info(f"  同伦修正完成! 总耗时={total_dt:.1f}s")
    total_iters = sum(s["iterations"] for s in homotopy_log)
    logger.info(f"  总迭代次数: {total_iters}")
    logger.info(f"  各步详情:")
    for s in homotopy_log:
        status = "ok" if s["converged"] else "FAIL"
        logger.info(
            f"    λ={s['lambda']:.4f} [{status}] "
            f"iter={s['iterations']} res={s['max_residual']:.2e} "
            f"t={s['time_s']:.1f}s"
        )

    return result, homotopy_log, total_dt


def validate_and_save(result, homotopy_log, total_time, eph_system, dro_orbit):
    logger.info(f"\n{'=' * 60}")
    logger.info("Step 5: 验证与保存")
    logger.info(f"{'=' * 60}")

    eph_dynamics_full = HomotopyEphemerisDynamics(  # type: ignore[misc]
        system=eph_system,
        base_bodies=BASE_BODIES,
        perturbation_bodies=PERTURBATION_BODIES,
        homotopy_param=1.0,
    )

    corrected_states = result.state_patch
    corrected_times = result.t_patch
    n_seg = len(corrected_states) - 1

    logger.info(f"  修正后 patch points 距地球距离:")
    for i in range(len(corrected_states)):
        r = np.linalg.norm(corrected_states[i, :3])
        logger.info(f"    Patch {i}: r={r:.0f} km")

    distances = np.linalg.norm(corrected_states[:, :3], axis=1)
    mean_dist = np.mean(distances)
    std_dist = np.std(distances)
    logger.info(f"  平均距地球: {mean_dist:.0f} km")
    logger.info(f"  距离标准差: {std_dist:.0f} km (std/mean={std_dist / mean_dist:.4f})")

    pos_errors = []
    for i in range(n_seg):
        prop = eph_dynamics_full.propagate(
            corrected_states[i],
            (corrected_times[i], corrected_times[i + 1]),
        )
        propagated_final = prop["states"][-1]
        pos_error = np.linalg.norm(propagated_final[:3] - corrected_states[i + 1, :3])
        pos_errors.append(pos_error)
        logger.info(f"    段 {i}→{i + 1}: 位置连续性误差 = {pos_error:.2e} km")

    max_error = max(pos_errors)
    logger.info(f"\n  最大位置连续性误差: {max_error:.2e} km")
    if max_error < POSITION_CONTINUITY_TOL:
        logger.info(f"  满足连续性要求 (< {POSITION_CONTINUITY_TOL:.1e} km)")
    else:
        logger.warning(f"  未满足连续性要求 (< {POSITION_CONTINUITY_TOL:.1e} km)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total_iters = sum(s["iterations"] for s in homotopy_log)
    output_data = {
        "method": "homotopy_perturbation_introduction",
        "converged": result.converged,
        "total_iterations": total_iters,
        "total_time_s": round(total_time, 2),
        "homotopy_steps": homotopy_log,
        "max_residual": float(result.max_residual),
        "residual_history": [float(r) for r in result.residual_history],
        "reference_epoch": REFERENCE_EPOCH,
        "n_patch_points": len(corrected_states),
        "base_bodies": BASE_BODIES,
        "perturbation_bodies": PERTURBATION_BODIES,
        "cr3bp_dro": {
            "source_file": str(DRO_JSON_FILE),
            "x0": dro_orbit.states[0][0],
            "vy0": dro_orbit.states[0][4],
            "period_tu": dro_orbit.period,
        },
        "position_errors_km": [float(e) for e in pos_errors],
        "mean_distance_km": float(mean_dist),
        "std_distance_km": float(std_dist),
        "corrected_states": corrected_states.tolist(),
        "corrected_times_et": corrected_times.tolist(),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"dro_homotopy_correction_{ts}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    logger.info(f"\n  结果已保存: {output_file}")

    return output_file


def main():
    raise NotImplementedError(
        "HomotopyEphemerisDynamics has been removed from e2m2e; "
        "this homotopy script is deprecated."
    )
    logger.info("DRO CR3BP → 星历模型修正 (同伦法)")  # type: ignore[unreachable]
    logger.info(f"参考历元: {REFERENCE_EPOCH}")
    logger.info(f"基础天体: {BASE_BODIES}")
    logger.info(f"摄动天体: {PERTURBATION_BODIES}")
    logger.info(f"同伦路径: {HOMOTOPY_STEPS}")
    logger.info(f"Patch points: {N_PATCH_POINTS}")

    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    logger.info(f"SPICE kernel: {kernel_path}")
    import spiceypy

    leapseconds_path = os.path.join(SPICE_KERNEL_DIR, "naif0012.tls")
    spiceypy.furnsh(leapseconds_path)
    spice.load_kernel(kernel_path)

    try:
        reference_et = spice.utc_to_et(REFERENCE_EPOCH)

        cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

        eph_system = EphemerisSystem(
            bodies=BODIES,
            spice=spice,
            origin="EARTH",
            frame="J2000",
        )

        dro_orbit = load_dro_orbit(cr3bp_system)

        t_patch_j2000, states_j2000 = prepare_patch_points(
            dro_orbit, cr3bp_system, spice, reference_et
        )

        result, homotopy_log, total_time = run_homotopy_correction(
            t_patch_j2000, states_j2000, eph_system
        )

        validate_and_save(result, homotopy_log, total_time, eph_system, dro_orbit)

    finally:
        spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    main()
