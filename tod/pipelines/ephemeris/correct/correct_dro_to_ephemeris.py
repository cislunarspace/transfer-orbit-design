"""
DRO 轨道 CR3BP → 星历模型 (Ephemeris N-body) 修正

将 CR3BP 中的 DRO 轨道转换到高精度星历模型下，
使用 Multiple Shooting 差分修正方法。

工作流:
  Step 1: 使用 Orbit.load_from_file 加载 DRO 轨道
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
import multiprocessing
from pathlib import Path

import numpy as np
from datetime import datetime

import spiceypy
from e2m2e.core import Orbit, CR3BP_System
from e2m2e.core import SPICEManager, EphemerisSystem, EphemerisDynamics
from e2m2e.core import SynodicJ2000Transformation

# BodyName has been removed from e2m2e
# from e2m2e.core import SynodicJ2000Transformation, BodyName
from e2m2e.algorithms import MultipleShooting, sample_patch_points, convert_to_j2000

from tod.commons.common import MU, DU, TU

# =============================================================================
# 输入输出路径设置
# =============================================================================
project_root = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "ephemeris"
DRO_JSON_FILE = project_root / "output" / "dro" / "dro_31_3857864736.json"

# =============================================================================
# 多重打靶法所需要的各项参数
# =============================================================================
TU_SECONDS = TU * 86400
VU = DU / TU_SECONDS
N_PATCH_POINTS = 8
POSITION_CONTINUITY_TOL = 1e-3
N_WORKERS = multiprocessing.cpu_count()  # 多进程 worker 数，默认使用所有核心
REFERENCE_EPOCH = "2025-06-21T11:00:06"
SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
BODIES = ["EARTH", "MOON", "SUN"]  # 地球（原点）+ 月球 + 太阳；不引入其他行星摄动


def main():
    """DRO 轨道 CR3BP → 星历模型修正的主流程入口。

    依次执行 SPICE 内核加载、DRO 轨道加载、patch points 采样、
    坐标转换、Multiple Shooting 差分修正和结果验证保存。
    """
    # 打印任务基本信息
    print("DRO CR3BP → 星历模型修正")
    print(f"参考历元: {REFERENCE_EPOCH}")
    print(f"天体: {BODIES}")
    print(f"Patch points: {N_PATCH_POINTS}")
    print(f"并行 workers: {N_WORKERS} 进程")

    # 初始化 SPICE 管理器，定位并加载星历内核
    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(
        SPICE_KERNEL_DIR
    )  # 在指定目录中按优先级搜索星历内核文件
    print(f"SPICE kernel: {kernel_path}")

    # 加载闰秒内核（naif0012.tls），用于 UTC ↔ ET 时间转换
    leapseconds_path = os.path.join(SPICE_KERNEL_DIR, "naif0012.tls")
    spiceypy.furnsh(leapseconds_path)
    spice.load_kernel(kernel_path)

    try:
        # 将参考历元 UTC 字符串转换为 SPICE ephemeris time（ET，单位秒）
        reference_et = spice.utc_to_et(REFERENCE_EPOCH)

        # 构建 CR3BP 系统对象，用于后续归一化/反归一化及坐标变换
        cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

        # 构建星历模型系统与动力学对象，指定引力天体、原点和参考系
        eph_system = EphemerisSystem(
            bodies=BODIES,
            spice=spice,
            origin="EARTH",
            frame="J2000",
        )
        eph_dynamics = EphemerisDynamics(system=eph_system)

        # Step 1: 从 JSON 文件加载 CR3BP 下的 DRO 轨道
        print("Step 1: 加载 DRO 轨道 (JSON)")
        dro_orbit = Orbit.load_from_file(filename=DRO_JSON_FILE, system=cr3bp_system)
        if dro_orbit.period is None:
            raise ValueError("无法确定 DRO 轨道周期")
        print(f"  文件: {DRO_JSON_FILE.name}")
        print(f"  状态数: {len(dro_orbit.states)}")
        print(f"  周期: {dro_orbit.period:.6f} TU ({dro_orbit.period * TU:.2f} days)")
        print(f"  初始状态: {dro_orbit.states[0]}")

        # Step 2: 沿轨道周期均匀采样 patch points（归一化 synodic 坐标系）
        print(f"Step 2: 采样 {N_PATCH_POINTS} 个 patch points")

        t_patch_syn, states_syn = sample_patch_points(dro_orbit, N_PATCH_POINTS)

        print(f"  时间范围: [0, {t_patch_syn[-1]:.4f}] TU")
        print(f"  时间间隔: {t_patch_syn[1] - t_patch_syn[0]:.4f} TU")
        for i in range(N_PATCH_POINTS):
            r = np.linalg.norm(states_syn[i, :3]) * DU
            print(f"  Patch {i}: t={t_patch_syn[i]:.4f}, r={r:.0f} km")

        # Step 3: Synodic → J2000 坐标转换
        print("Step 3: Synodic → J2000 坐标转换")

        syn_j2000 = SynodicJ2000Transformation(
            cr3bp_system=cr3bp_system,
            spice=spice,
        )
        t_patch_j2000, states_j2000 = convert_to_j2000(
            t_patch_syn, states_syn, syn_j2000, reference_et, TU
        )

        print(f"  参考历元: {REFERENCE_EPOCH} (ET={reference_et:.2f} s)")
        for i in range(len(t_patch_syn)):
            r = np.linalg.norm(states_j2000[i, :3])
            v = np.linalg.norm(states_j2000[i, 3:])
            print(
                f"  Patch {i}: ET={t_patch_j2000[i]:.2f}, r={r:.0f} km, v={v:.4f} km/s"
            )

        # Step 4: 以 J2000 状态为初值，执行 Multiple Shooting 差分修正
        print(f"\n{'=' * 60}")
        print("Step 4: Multiple Shooting 差分修正")
        print(f"{'=' * 60}")

        print(f"  Patch points: {len(t_patch_j2000)}")
        print(f"  最大迭代: 50")
        print(f"  收敛容差: {POSITION_CONTINUITY_TOL:.1e} km")
        print(f"  时间自由: True")

        ms = MultipleShooting(
            dynamics=eph_dynamics,
            n_workers=N_WORKERS,
            kernel_dir=SPICE_KERNEL_DIR,
        )
        result = ms.correct(
            t_patch=t_patch_j2000,
            state_patch=states_j2000,
            var_time=True,
            max_iter=50,
            tolerance=POSITION_CONTINUITY_TOL,
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

        # Step 5: 验证修正后轨迹连续性，并将结果保存为 JSON
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
            propagated_final = prop["states"][-1]
            pos_error = np.linalg.norm(
                propagated_final[:3] - corrected_states[i + 1, :3]
            )
            pos_errors.append(pos_error)
            print(f"    段 {i}→{i + 1}: 位置连续性误差 = {pos_error:.2e} km")

            seg_states = prop["states"]
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
            OUTPUT_DIR
            / f"dro_ephemeris_correction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\n  结果已保存: {output_file}")

    finally:
        # 卸载星历内核，释放 SPICE 资源
        spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    main()
