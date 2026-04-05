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
import os
import time
from pathlib import Path

import numpy as np
from datetime import datetime

from e2m2e.core import Orbit, CR3BP_System
from e2m2e.core import SPICEManager, EphemerisSystem
from e2m2e.core import HomotopyEphemerisDynamics
from e2m2e.core import SynodicJ2000Transformation
from e2m2e.algorithms import MultipleShooting

from scripts.utils.params import MU, DU, TU

project_root = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = project_root / "output" / "ephemeris"

TU_SECONDS = TU * 86400
VU = DU / TU_SECONDS

DRO_JSON_FILE = project_root / "output" / "dro" / "dro_31_3857864736.json"

N_PATCH_POINTS = 8
POSITION_CONTINUITY_TOL = 1e-6

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


def find_spice_kernel():
    for name in ["de435.bsp", "de440.bsp", "de440s.bsp", "de438.bsp"]:
        path = os.path.join(SPICE_KERNEL_DIR, name)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"SPICE kernel not found in {SPICE_KERNEL_DIR}. Set SPICE_KERNEL_DIR environment variable."
    )


def load_dro_orbit(system):
    print("=" * 60)
    print("Step 1: 加载 DRO 轨道 (JSON)")
    print("=" * 60)

    dro_orbit = Orbit.load_from_file(filename=DRO_JSON_FILE, system=system)

    if dro_orbit.period is None:
        dro_orbit._estimate_period()

    assert dro_orbit.period is not None, "无法确定 DRO 轨道周期"

    print(f"  文件: {DRO_JSON_FILE.name}")
    print(f"  状态数: {len(dro_orbit.states)}")
    period = dro_orbit.period
    print(f"  周期: {period:.6f} TU ({period * TU:.2f} days)")
    print(f"  初始状态: {dro_orbit.states[0]}")
    return dro_orbit


def prepare_patch_points(dro_orbit, cr3bp_system, spice, reference_et):
    print(f"\n{'=' * 60}")
    print("Step 2: 采样 patch points + Synodic → J2000")
    print(f"{'=' * 60}")

    period = dro_orbit.period
    assert period is not None, "轨道周期未知，无法采样 patch points"
    n_points = N_PATCH_POINTS
    t_patch_syn = np.linspace(0, period, n_points, endpoint=False)

    orbit_states = np.array(dro_orbit.states)
    orbit_times = np.array(dro_orbit.times)

    states_syn = np.zeros((n_points, 6))
    for dim in range(6):
        states_syn[:, dim] = np.interp(t_patch_syn, orbit_times, orbit_states[:, dim])

    syn_j2000 = SynodicJ2000Transformation(
        cr3bp_system=cr3bp_system,
        spice=spice,
    )

    states_j2000 = syn_j2000.batch_synodic_to_j2000(
        states_syn=states_syn,
        t_syn_arr=t_patch_syn,
        et0=reference_et,
    )
    t_patch_j2000 = reference_et + t_patch_syn * TU_SECONDS

    print(f"  参考历元: {REFERENCE_EPOCH} (ET={reference_et:.2f} s)")
    print(f"  Patch points: {n_points}")
    for i in range(n_points):
        r = np.linalg.norm(states_j2000[i, :3])
        print(f"  Patch {i}: ET={t_patch_j2000[i]:.2f}, r={r:.0f} km")

    return t_patch_j2000, states_j2000


def run_homotopy_correction(t_patch_j2000, states_j2000, eph_system):
    print(f"\n{'=' * 60}")
    print("Step 3-4: 同伦法修正 (Homotopy Correction)")
    print(f"{'=' * 60}")
    print(f"  同伦路径: λ = {HOMOTOPY_STEPS}")
    print(f"  基础天体: {BASE_BODIES}")
    print(f"  摄动天体: {PERTURBATION_BODIES}")
    print(f"  收敛容差: {MS_TOLERANCE:.1e} km")

    total_t0 = time.time()
    homotopy_log = []

    current_t = t_patch_j2000.copy()
    current_states = states_j2000.copy()

    for step_idx, lam in enumerate(HOMOTOPY_STEPS):
        print(f"\n{'─' * 50}")
        print(f"  Homotopy step {step_idx + 1}/{len(HOMOTOPY_STEPS)}: λ = {lam:.4f}")
        print(f"{'─' * 50}")

        hdynamics = HomotopyEphemerisDynamics(
            system=eph_system,
            base_bodies=BASE_BODIES,
            perturbation_bodies=PERTURBATION_BODIES,
            homotopy_param=lam,
        )

        ms = MultipleShooting(dynamics=hdynamics)
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
            print(f"  [ok] λ={lam:.4f} 收敛! 迭代={result.iterations}, "
                  f"残差={result.max_residual:.2e} km, 耗时={dt_step:.1f}s")
            current_t = result.t_patch.copy()
            current_states = result.state_patch.copy()
        else:
            print(f"  [warning] λ={lam:.4f} 未收敛! 残差={result.max_residual:.2e} km")
            print(f"  尝试减半步长重新延拓...")

            if step_idx == 0:
                print(f"  [error] λ=0 阶段即不收敛，终止")
                return result, homotopy_log, total_t0

            sub_steps = np.linspace(
                HOMOTOPY_STEPS[step_idx - 1], lam, 3
            )[1:]

            sub_ok = True
            for sub_lam in sub_steps:
                hdynamics_sub = HomotopyEphemerisDynamics(
                    system=eph_system,
                    base_bodies=BASE_BODIES,
                    perturbation_bodies=PERTURBATION_BODIES,
                    homotopy_param=sub_lam,
                )
                ms_sub = MultipleShooting(dynamics=hdynamics_sub)
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

                homotopy_log.append({
                    "lambda": float(sub_lam),
                    "converged": result_sub.converged,
                    "iterations": result_sub.iterations,
                    "max_residual": float(result_sub.max_residual),
                    "time_s": round(dt_sub, 2),
                    "note": "sub-step",
                })

                if result_sub.converged:
                    current_t = result_sub.t_patch.copy()
                    current_states = result_sub.state_patch.copy()
                    print(f"    子步 λ={sub_lam:.4f} 收敛, "
                          f"残差={result_sub.max_residual:.2e}")
                else:
                    print(f"    子步 λ={sub_lam:.4f} 仍未收敛, "
                          f"残差={result_sub.max_residual:.2e}")
                    sub_ok = False
                    break

            if not sub_ok:
                print(f"  [error] 减半步长后仍不收敛，使用当前最优解")
                break

    total_dt = time.time() - total_t0
    print(f"\n{'=' * 60}")
    print(f"  同伦修正完成! 总耗时={total_dt:.1f}s")
    total_iters = sum(s["iterations"] for s in homotopy_log)
    print(f"  总迭代次数: {total_iters}")
    print(f"  各步详情:")
    for s in homotopy_log:
        status = "ok" if s["converged"] else "FAIL"
        print(f"    λ={s['lambda']:.4f} [{status}] "
              f"iter={s['iterations']} res={s['max_residual']:.2e} "
              f"t={s['time_s']:.1f}s")

    return result, homotopy_log, total_dt


def validate_and_save(result, homotopy_log, total_time, eph_system, dro_orbit):
    print(f"\n{'=' * 60}")
    print("Step 5: 验证与保存")
    print(f"{'=' * 60}")

    eph_dynamics_full = HomotopyEphemerisDynamics(
        system=eph_system,
        base_bodies=BASE_BODIES,
        perturbation_bodies=PERTURBATION_BODIES,
        homotopy_param=1.0,
    )

    corrected_states = result.state_patch
    corrected_times = result.t_patch
    n_seg = len(corrected_states) - 1

    print(f"  修正后 patch points 距地球距离:")
    for i in range(len(corrected_states)):
        r = np.linalg.norm(corrected_states[i, :3])
        print(f"    Patch {i}: r={r:.0f} km")

    distances = np.linalg.norm(corrected_states[:, :3], axis=1)
    mean_dist = np.mean(distances)
    std_dist = np.std(distances)
    print(f"  平均距地球: {mean_dist:.0f} km")
    print(f"  距离标准差: {std_dist:.0f} km (std/mean={std_dist / mean_dist:.4f})")

    pos_errors = []
    for i in range(n_seg):
        prop = eph_dynamics_full.propagate(
            corrected_states[i],
            (corrected_times[i], corrected_times[i + 1]),
        )
        propagated_final = prop["states"][:, -1]
        pos_error = np.linalg.norm(propagated_final[:3] - corrected_states[i + 1, :3])
        pos_errors.append(pos_error)
        print(f"    段 {i}→{i + 1}: 位置连续性误差 = {pos_error:.2e} km")

    max_error = max(pos_errors)
    print(f"\n  最大位置连续性误差: {max_error:.2e} km")
    if max_error < POSITION_CONTINUITY_TOL:
        print(f"  [ok] 满足连续性要求 (< {POSITION_CONTINUITY_TOL:.1e} km)")
    else:
        print(f"  [warning] 未满足连续性要求 (< {POSITION_CONTINUITY_TOL:.1e} km)")

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
    print(f"\n  结果已保存: {output_file}")

    return output_file


def main():
    print("DRO CR3BP → 星历模型修正 (同伦法)")
    print(f"参考历元: {REFERENCE_EPOCH}")
    print(f"基础天体: {BASE_BODIES}")
    print(f"摄动天体: {PERTURBATION_BODIES}")
    print(f"同伦路径: {HOMOTOPY_STEPS}")
    print(f"Patch points: {N_PATCH_POINTS}")

    kernel_path = find_spice_kernel()
    print(f"SPICE kernel: {kernel_path}")

    spice = SPICEManager()
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
