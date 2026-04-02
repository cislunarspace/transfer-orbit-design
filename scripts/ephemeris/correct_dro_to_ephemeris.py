"""
DRO 轨道 CR3BP → 星历模型 (Ephemeris N-body) 修正

将 CR3BP 中的 3:1 DRO 轨道转换到高精度星历模型下，
使用 Multiple Shooting 差分修正方法。

工作流:
  Step 1: 在 CR3BP 中生成 3:1 DRO 轨道
  Step 2: 对 DRO 轨道均匀采样生成 patch points
  Step 3: synodic → J2000 坐标转换（含速度）
  Step 4: Multiple Shooting 差分修正（星历模型）
  Step 5: 验证修正后位置连续性

参考文献:
    陈昱桔 (2024) "面向地月空间态势感知的DRO轨道设计与控制研究"
    Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits"

依赖:
    e2m2e (Layer 1a/1b/1c/2): SPICEManager, EphemerisSystem, EphemerisDynamics,
                               SynodicJ2000Transformation, MultipleShooting
    SPICE kernels: de440.bsp, naif0012.tls
"""

import json
import os
from pathlib import Path

import numpy as np
from fontTools.misc.timeTools import timestampNow

import e2m2e
from e2m2e.core import Orbit, CR3BP_System, CR3BP_Dynamics
from e2m2e.core import SPICEManager, EphemerisSystem, EphemerisDynamics
from e2m2e.core import SynodicJ2000Transformation
from e2m2e.algorithms import DifferentialCorrection, MultipleShooting

from scripts.utils.params import MU, DU, TU

project_root = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = project_root / "output" / "ephemeris"

# =============================================================================
# 物理参数
# =============================================================================
TU_SECONDS = TU * 86400
VU = DU / TU_SECONDS

DRO_31_X0 = 1.1202109158830986
DRO_31_VY0 = -0.46178983697629084
DRO_31_PERIOD = 2.095

N_PATCH_POINTS = 8
POSITION_CONTINUITY_TOL = 1e-6

REFERENCE_EPOCH = "2025-06-21T11:00:06"
SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
BODIES = ["EARTH", "MOON", "SUN"]


def find_spice_kernel():
    for name in ["de440.bsp", "de440s.bsp", "de438.bsp"]:
        path = os.path.join(SPICE_KERNEL_DIR, name)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"SPICE kernel not found in {SPICE_KERNEL_DIR}. Set SPICE_KERNEL_DIR environment variable."
    )


def generate_dro_orbit(system, dynamics):
    print("=" * 60)
    print("Step 1: 生成 3:1 DRO 轨道 (CR3BP)")
    print("=" * 60)

    seed_state = np.array([DRO_31_X0, 0.0, 0.0, 0.0, DRO_31_VY0, 0.0])
    seed_orbit = Orbit(states=[seed_state], times=[0])
    seed_orbit.period = DRO_31_PERIOD

    print(f"种子状态: x0={DRO_31_X0:.4f}, vy0={DRO_31_VY0:.4f}")
    print(f"目标周期: {DRO_31_PERIOD:.4f} TU ({DRO_31_PERIOD * TU:.2f} days)")

    corrector = DifferentialCorrection(dynamic=dynamics)
    corrector.setup_2D_symmetric_x_fixed_x0(x0=DRO_31_X0)
    orbit_result = corrector.iterate_correction(initial_guess=seed_orbit, verbose=True)

    if orbit_result is None:
        raise RuntimeError(f"DRO 微分修正失败: {corrector.termination_reason}")

    print(f"\n[ok] DRO 轨道生成成功!")
    print(f"  修正后周期: {orbit_result.period:.6f} TU")
    print(f"  初始状态: {orbit_result.states[0]}")
    return orbit_result


def sample_patch_points(dro_orbit, dynamics, n_points):
    print(f"\n{'=' * 60}")
    print(f"Step 2: 采样 {n_points} 个 patch points")
    print(f"{'=' * 60}")

    period = dro_orbit.period
    t_patch = np.linspace(0, period, n_points, endpoint=False)

    states = np.zeros((n_points, 6))
    states[0] = dro_orbit.states[0]
    for i in range(1, n_points):
        states[i] = dynamics.propagate_orbit_state_at_time(dro_orbit, t_patch[i])

    print(f"  时间范围: [0, {t_patch[-1]:.4f}] TU")
    print(f"  时间间隔: {t_patch[1] - t_patch[0]:.4f} TU")
    for i in range(n_points):
        r = np.linalg.norm(states[i, :3]) * DU
        print(f"  Patch {i}: t={t_patch[i]:.4f}, r={r:.0f} km")

    return t_patch, states


def convert_to_j2000(t_patch_syn, states_syn, cr3bp_system, spice, reference_et):
    print(f"\n{'=' * 60}")
    print("Step 3: Synodic → J2000 坐标转换")
    print(f"{'=' * 60}")

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
    for i in range(len(t_patch_syn)):
        r = np.linalg.norm(states_j2000[i, :3])
        v = np.linalg.norm(states_j2000[i, 3:])
        print(f"  Patch {i}: ET={t_patch_j2000[i]:.2f}, r={r:.0f} km, v={v:.4f} km/s")

    return t_patch_j2000, states_j2000


def run_multiple_shooting(
    t_patch, state_patch, eph_dynamics, max_iter=50, tolerance=POSITION_CONTINUITY_TOL
):
    print(f"\n{'=' * 60}")
    print("Step 4: Multiple Shooting 差分修正")
    print(f"{'=' * 60}")

    print(f"  Patch points: {len(t_patch)}")
    print(f"  最大迭代: {max_iter}")
    print(f"  收敛容差: {tolerance:.1e} km")
    print(f"  时间自由: True")

    ms = MultipleShooting(dynamics=eph_dynamics)
    result = ms.correct(
        t_patch=t_patch,
        state_patch=state_patch,
        var_time=True,
        max_iter=max_iter,
        tolerance=tolerance,
    )

    if result.converged:
        print(f"\n[ok] 修正收敛!")
        print(f"  迭代次数: {result.iterations}")
        print(f"  最大残差: {result.max_residual:.2e} km")
        print(f"  残差历史: {[f'{r:.2e}' for r in result.residual_history]}")
    else:
        print(f"\n[warning] 修正未收敛")
        print(f"  迭代次数: {result.iterations}")
        print(f"  最大残差: {result.max_residual:.2e} km")

    return result


def validate_and_save(result, eph_dynamics):
    print(f"\n{'=' * 60}")
    print("Step 5: 验证与保存")
    print(f"{'=' * 60}")

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
        prop = eph_dynamics.propagate(
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
    output_data = {
        "converged": result.converged,
        "iterations": result.iterations,
        "max_residual": float(result.max_residual),
        "residual_history": [float(r) for r in result.residual_history],
        "reference_epoch": REFERENCE_EPOCH,
        "n_patch_points": len(corrected_states),
        "bodies": BODIES,
        "cr3bp_dro": {
            "x0": DRO_31_X0,
            "vy0": DRO_31_VY0,
            "period_tu": DRO_31_PERIOD,
        },
        "position_errors_km": [float(e) for e in pos_errors],
        "mean_distance_km": float(mean_dist),
        "std_distance_km": float(std_dist),
        "corrected_states": corrected_states.tolist(),
        "corrected_times_et": corrected_times.tolist(),
    }

    output_file = OUTPUT_DIR / f"dro_ephemeris_correction_{timestampNow()}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\n  结果已保存: {output_file}")

    return output_file


def main():
    print("DRO CR3BP → 星历模型修正")
    print(f"参考历元: {REFERENCE_EPOCH}")
    print(f"天体: {BODIES}")
    print(f"Patch points: {N_PATCH_POINTS}")

    kernel_path = find_spice_kernel()
    print(f"SPICE kernel: {kernel_path}")

    spice = SPICEManager()
    spice.load_kernel(kernel_path)

    try:
        reference_et = spice.utc_to_et(REFERENCE_EPOCH)

        cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
        cr3bp_dynamics = CR3BP_Dynamics(system=cr3bp_system)

        eph_system = EphemerisSystem(
            bodies=BODIES,
            spice=spice,
            origin="EARTH",
            frame="J2000",
        )
        eph_dynamics = EphemerisDynamics(system=eph_system)

        dro_orbit = generate_dro_orbit(cr3bp_system, cr3bp_dynamics)

        t_patch_syn, states_syn = sample_patch_points(
            dro_orbit,
            cr3bp_dynamics,
            N_PATCH_POINTS,
        )

        t_patch_j2000, states_j2000 = convert_to_j2000(
            t_patch_syn,
            states_syn,
            cr3bp_system,
            spice,
            reference_et,
        )

        result = run_multiple_shooting(
            t_patch_j2000,
            states_j2000,
            eph_dynamics,
        )

        validate_and_save(result, eph_dynamics)

    finally:
        spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    main()
