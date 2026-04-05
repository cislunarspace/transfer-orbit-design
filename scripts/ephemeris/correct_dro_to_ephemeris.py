"""
DRO 轨道 CR3BP → 星历模型 (Ephemeris N-body) 修正

将 CR3BP 中的 DRO 轨道转换到高精度星历模型下，
使用 Multiple Shooting 差分修正方法。

工作流:
  Step 1: 从 JSON 文件加载 DRO 轨道
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
from datetime import datetime

import spiceypy
from e2m2e.core import Orbit, CR3BP_System
from e2m2e.core import SPICEManager, EphemerisSystem, EphemerisDynamics
from e2m2e.core import SynodicJ2000Transformation
from e2m2e.algorithms import MultipleShooting

from scripts.utils.params import MU, DU, TU

# =============================================================================
# 输入输出路径设置
# =============================================================================
project_root = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = project_root / "output" / "ephemeris"
DRO_JSON_FILE = project_root / "output" / "dro" / "dro_31_3857864736.json"

# =============================================================================
# 多重打靶法所需要的各项参数
# =============================================================================
TU_SECONDS = TU * 86400
VU = DU / TU_SECONDS
N_PATCH_POINTS = 4
POSITION_CONTINUITY_TOL = 1e-3
REFERENCE_EPOCH = "2025-06-21T11:00:06"
SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
BODIES = ["EARTH", "MOON", "SUN"]


# =============================================================================
# 辅助函数
# =============================================================================
def load_dro_orbit(system):
    """从 JSON 文件加载 DRO 轨道数据并估计其周期。

    Args:
        system: CR3BP 系统对象，用于解析轨道数据的归一化参数。

    Returns:
        Orbit: 加载后的 DRO 轨道对象，包含状态序列和已估计的周期。

    Raises:
        AssertionError: 如果无法确定轨道周期。
    """
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


def sample_patch_points(dro_orbit, n_points):
    """沿 DRO 轨道等间距采样 patch points，用于 Multiple Shooting 修正。

    在轨道周期内均匀取 n_points 个时刻，通过线性插值获取对应的状态向量。

    Args:
        dro_orbit: DRO 轨道对象，需包含有效的 period 属性。
        n_points: 需要采样的 patch point 数量。

    Returns:
        tuple[np.ndarray, np.ndarray]:
            - t_patch: shape (n_points,)，各 patch point 对应的归一化时间（TU）。
            - states: shape (n_points, 6)，各 patch point 的六维状态向量（归一化）。

    Raises:
        AssertionError: 如果轨道周期为 None。
    """
    print(f"\n{'=' * 60}")
    print(f"Step 2: 采样 {n_points} 个 patch points")
    print(f"{'=' * 60}")

    period = dro_orbit.period
    assert period is not None, "轨道周期未知，无法采样 patch points"
    t_patch = np.linspace(0, period, n_points, endpoint=False)

    orbit_states = np.array(dro_orbit.states)
    orbit_times = np.array(dro_orbit.times)

    states = np.zeros((n_points, 6))
    for dim in range(6):
        states[:, dim] = np.interp(t_patch, orbit_times, orbit_states[:, dim])

    print(f"  时间范围: [0, {t_patch[-1]:.4f}] TU")
    print(f"  时间间隔: {t_patch[1] - t_patch[0]:.4f} TU")
    for i in range(n_points):
        r = np.linalg.norm(states[i, :3]) * DU
        print(f"  Patch {i}: t={t_patch[i]:.4f}, r={r:.0f} km")

    return t_patch, states


def convert_to_j2000(t_patch_syn, states_syn, cr3bp_system, spice, reference_et):
    """将 synodic 坐标系下的 patch points 批量转换为 J2000 坐标系。

    Args:
        t_patch_syn: shape (n,)，synodic 归一化时间数组（TU）。
        states_syn: shape (n, 6)，synodic 坐标系下的状态向量数组。
        cr3bp_system: CR3BP 系统对象，提供质量参数等归一化信息。
        spice: SPICEManager 实例，用于天体位置查询。
        reference_et: 参考历元的 ET（ephemeris time），单位秒。

    Returns:
        tuple[np.ndarray, np.ndarray]:
            - t_patch_j2000: shape (n,)，J2000 下的绝对 ET 时间数组（秒）。
            - states_j2000: shape (n, 6)，J2000 惯性系下的状态向量数组（km, km/s）。
    """
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
    """使用 Multiple Shooting 差分修正方法将 patch points 修正为连续轨迹。

    以时间自由的模式修正各段端点状态与时间，使相邻段的位置连续。

    Args:
        t_patch: shape (n,)，各 patch point 的 ET 时间数组（秒）。
        state_patch: shape (n, 6)，各 patch point 的初始状态向量（km, km/s）。
        eph_dynamics: EphemerisDynamics 实例，提供星历模型下的轨道传播与状态转移矩阵。
        max_iter: 最大修正迭代次数。默认为 50。
        tolerance: 位置连续性收敛容差（km）。默认为 POSITION_CONTINUITY_TOL。

    Returns:
        MultipleShootingResult: 修正结果对象，包含收敛状态、迭代次数、残差历史、
        修正后的时间和状态等信息。
    """
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
        verbose=True,
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


def validate_and_save(result, eph_dynamics, dro_orbit):
    """验证修正后轨迹的位置连续性并保存结果到 JSON 文件。

    逐段传播修正后的轨迹，检查相邻段端点的位置误差，
    并将修正结果、完整轨迹和元信息写入 output/ephemeris/ 目录。

    Args:
        result: MultipleShooting 修正结果对象。
        eph_dynamics: EphemerisDynamics 实例，用于轨道传播验证。
        dro_orbit: 原始 DRO 轨道对象，用于记录源轨道信息。

    Returns:
        Path: 保存的 JSON 结果文件的完整路径。
    """
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
    full_states_list = []
    full_times_list = []
    for i in range(n_seg):
        prop = eph_dynamics.propagate(
            corrected_states[i],
            (corrected_times[i], corrected_times[i + 1]),
        )
        propagated_final = prop["states"][:, -1]
        pos_error = np.linalg.norm(propagated_final[:3] - corrected_states[i + 1, :3])
        pos_errors.append(pos_error)
        print(f"    段 {i}→{i + 1}: 位置连续性误差 = {pos_error:.2e} km")

        seg_states = prop["states"].T
        seg_times = prop["time"]
        if i > 0:
            seg_states = seg_states[1:]
            seg_times = seg_times[1:]
        full_states_list.append(seg_states)
        full_times_list.append(seg_times)

    full_states = np.vstack(full_states_list)
    full_times = np.concatenate(full_times_list)
    print(f"\n  完整轨迹: {len(full_states)} 个状态点")

    max_error = max(pos_errors)
    print(f"  最大位置连续性误差: {max_error:.2e} km")
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
        "full_trajectory_states": full_states.tolist(),
        "full_trajectory_times_et": full_times.tolist(),
    }

    output_file = (
        OUTPUT_DIR / f"dro_ephemeris_correction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\n  结果已保存: {output_file}")

    return output_file


def main():
    """DRO 轨道 CR3BP → 星历模型修正的主流程入口。

    依次执行 SPICE 内核加载、DRO 轨道加载、patch points 采样、
    坐标转换、Multiple Shooting 差分修正和结果验证保存。
    """
    print("DRO CR3BP → 星历模型修正")
    print(f"参考历元: {REFERENCE_EPOCH}")
    print(f"天体: {BODIES}")
    print(f"Patch points: {N_PATCH_POINTS}")

    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    print(f"SPICE kernel: {kernel_path}")

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
        eph_dynamics = EphemerisDynamics(system=eph_system)

        dro_orbit = load_dro_orbit(cr3bp_system)

        t_patch_syn, states_syn = sample_patch_points(
            dro_orbit,
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

        validate_and_save(result, eph_dynamics, dro_orbit)

    finally:
        spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    main()
