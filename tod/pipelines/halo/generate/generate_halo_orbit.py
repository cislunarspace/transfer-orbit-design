"""
生成 Halo 轨道

使用Richardson三阶近似生成初始猜测，结合微分修正生成精确的Halo周期轨道。

参考文献:
    Richardson, D. L. (1980). Analytic construction of periodic orbits
    about the collinear points. Celestial Mechanics.

初值来源:
    FAMILY_L1Halo_North.m (MATLAB参考)
    SV0 = [0.9305, 0, 0.2300, 0, 0.1043, 0]'
    tf = 1.8397 (完整周期)
"""

import argparse
from pathlib import Path

import time

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

import e2m2e
from e2m2e.core import Orbit

from tod.commons.common import MU, TU

OUTPUT_DIR = project_root / "output" / "halo"


def parse_args():
    parser = argparse.ArgumentParser(description="生成 Halo 轨道（Richardson 三阶近似 + 微分修正）")
    parser.add_argument("--libration-point", type=str, default="L1", choices=["L1", "L2", "L3"], help="平动点：L1, L2, L3")
    parser.add_argument("--amplitude-z", type=float, default=0.23, help="Z 方向振幅（无量纲）")
    parser.add_argument("--halo-class", type=int, default=0, help="0=北 Halo (Class I), 1=南 Halo (Class II)")
    parser.add_argument("--period", type=float, default=1.839732, help="目标周期（无量纲）")
    parser.add_argument("--x0", type=float, default=0.9305269194214338, help="初始 x 坐标（无量纲）")
    parser.add_argument("--vy0", type=float, default=0.10431508546142665, help="初始 y 方向速度（无量纲）")
    parser.add_argument("--max-iterations", type=int, default=150, help="最大迭代次数")
    parser.add_argument("--tolerance", type=float, default=1e-6, help="修正容差")
    return parser.parse_args()


def main():
    args = parse_args()

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. Halo轨道参数
    # =============================================================================
    # Halo轨道特征：关于XZ平面对称，在拉格朗日点(L1/L2)附近振荡
    # 状态向量格式：[x, y, z, vx, vy, vz]，均为无量纲量

    LIBRATION_POINT_MAP = {"L1": 1, "L2": 2, "L3": 3}
    libration_point = LIBRATION_POINT_MAP[args.libration_point]  # 1=L1, 2=L2, 3=L3
    amplitude_z = args.amplitude_z  # Z方向振幅
    halo_class = args.halo_class  # 0=北Halo (Class I), 1=南Halo (Class II)

    # 目标参数
    target_period = args.period  # 完整周期（无量纲时间单位）
    t_half = target_period / 2  # 半周期

    print(f"目标轨道: L{libration_point} {'北' if halo_class == 0 else '南'} Halo")
    print(f"Z振幅: {amplitude_z}")
    print(f"目标周期: {target_period:.4f} TU ({target_period * TU:.2f} days)")
    print(f"半周期: {t_half:.4f} TU")

    # =============================================================================
    # 3. 配置微分校正器
    # =============================================================================
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    corrector.setup_halo_orbit_fixed_z0(
        z0=amplitude_z if halo_class == 0 else -amplitude_z, libration_point=libration_point
    )

    print(f"\n微分校正器配置:")
    print(f"  模式: setup_halo_orbit_fixed_z0")
    print(f"  固定参数: z0 = {amplitude_z if halo_class == 0 else -amplitude_z}")
    print(f"  自由变量: {corrector.free_variables}")
    print(f"  约束条件: {list(corrector.target_conditions.keys())}")

    # =============================================================================
    # 4. 初始猜测（来自Richardson三阶近似）
    # =============================================================================
    x0 = args.x0  # L1位置附近
    z0 = amplitude_z if halo_class == 0 else -amplitude_z
    vy0 = args.vy0

    initial_state = [x0, 0.0, z0, 0.0, vy0, 0.0]
    times = [0]

    orbit_init = Orbit(states=[initial_state], times=times)
    orbit_init.period = target_period

    print(f"\n初始猜测:")
    print(f"  状态: {initial_state}")
    print(f"  预估周期: {orbit_init.period:.4f} TU")

    # =============================================================================
    # 5. 执行迭代修正
    # =============================================================================
    corrector.max_iterations = args.max_iterations
    corrector.tolerance = args.tolerance

    print(f"\n开始迭代修正...")
    orbit_result = corrector.iterate_correction(initial_guess=orbit_init, verbose=True)

    # =============================================================================
    # 6. 保存结果
    # =============================================================================
    if orbit_result is not None:
        print(f"\n[ok] 成功找到 Halo 轨道!")
        print(f"  修正后周期: {orbit_result.period:.6f} TU")
        print(f"  周期误差: {abs(orbit_result.period - target_period):.6e}")
        print(f"  初始状态: {orbit_result.states[0].tolist()}")

        ts = int(time.time())
        output_file = (
            OUTPUT_DIR
            / f"halo_L{libration_point}_{'N' if halo_class == 0 else 'S'}_{amplitude_z}_{ts}.json"
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        orbit_result.save_to_file(filename=str(output_file))
        print(f"  保存至: {output_file}")
    else:
        print(f"\n[error] 修正失败: {corrector.termination_reason}")


if __name__ == "__main__":
    main()
