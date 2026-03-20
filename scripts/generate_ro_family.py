"""
生成共振轨道族

本脚本实现：
1. 创建CR3BP系统和动力学模型
2. 设置RO种子轨道的初始状态向量（3:2和3:1共振轨道）
3. 利用差分修正器修正种子轨道
4. 采用自然延拓方法生成完整轨道族

共振轨道(Resonant Orbits)特征：
  - 3:2 RO: T = 4π ≈ 12.566 TU (航天器3圈/月球2圈)
  - 3:1 RO: T = 2π ≈  6.283 TU (航天器3圈/月球1圈)

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

import argparse
import os
from fontTools.misc.timeTools import timestampNow

import e2m2e
from e2m2e.core import Orbit, OrbitFamily
from e2m2e.core.system import CR3BP_System
from e2m2e.core.dynamics import CR3BP_Dynamics
from e2m2e.algorithms import DifferentialCorrection, Continuation
import numpy as np
from scipy.integrate import solve_ivp

from scripts.utils.common import MU

# =============================================================================
# 系统参数（论文Table 1）
# =============================================================================
T_MOON = 2 * np.pi  # 月球恒星周期(无量纲)

# 目标共振轨道周期
T_RO_32 = 2 * T_MOON  # 4π ≈ 12.566
T_RO_31 = 1 * T_MOON  # 2π ≈  6.283

# 种子轨道参数（论文Table 2）
# RO是关于x轴对称的周期轨道
# 论文Table 2中的x,y是y幅值点（vy=0），不是x轴交点
RO_SEEDS = {
    "3:2": {
        "x0": -1.1453,  # y幅值点x坐标
        "y0": 0.4633,   # y幅值点y坐标
        "period": 2 * T_MOON,  # T = 4π ≈ 12.566 TU
        "y_dot0_initial": 0.58566,  # 修正后的y_dot0
        "x0_range": (-1.2, -0.8),  # 延拓x0范围
    },
    "3:1": {
        "x0": -0.8805,  # y幅值点x坐标
        "y0": 0.3921,   # y幅值点y坐标
        "period": 1 * T_MOON,  # T = 2π ≈ 6.283 TU
        "y_dot0_initial": None,  # 需要通过微分修正确定
        "x0_range": (-1.0, -0.7),  # 延拓x0范围
    },
}


def correct_seed_ro(dynamics, seed_dict, system):
    """修正RO种子轨道

    参数:
        dynamics: CR3BP_Dynamics对象
        seed_dict: dict, 包含x0, y0, period, y_dot0_initial
        system: CR3BP_System对象

    返回:
        修正后的Orbit或None
    """
    x0 = seed_dict["x0"]
    y0 = seed_dict["y0"]
    period = seed_dict["period"]
    y_dot0_initial = seed_dict.get("y_dot0_initial", 0.0)

    # 创建初始状态（从y幅值点出发）
    initial_state = [x0, y0, 0.0, 0.0, y_dot0_initial, 0.0]

    # 积分一个周期
    t_eval = np.linspace(0, period, 500)
    res = solve_ivp(
        dynamics.equations_of_motion,
        (0, period),
        initial_state,
        method="DOP853",
        t_eval=t_eval,
        rtol=1e-10,
        atol=1e-10,
    )

    if not res.success:
        print(f"  [错误] 初始积分失败！")
        return None

    orbit = Orbit(res.y.T, res.t, system=system)
    orbit.period = period

    # 微分修正 - 固定x0，自由变量为[y_dot0, T_half]
    corrector = DifferentialCorrection(dynamics)
    corrector.setup_2D_symmetric_x_fixed_x0(x0)
    corrector.tolerance = 1e-12
    corrector.max_iterations = 50

    corrected_orbit = corrector.iterate_correction(orbit, verbose=True)

    if corrected_orbit is None or not corrected_orbit.correction_success:
        print(f"  [错误] 种子轨道修正失败！")
        return None

    print(f"  修正后周期: {corrected_orbit.period:.6f} TU")
    print(f"  修正后y_dot0: {corrected_orbit.states[0, 4]:.6f}")

    return corrected_orbit


def generate_ro_family(ro_type, system, dynamics):
    """生成指定类型的RO族

    参数:
        ro_type: str, "3:2" 或 "3:1"
        system: CR3BP_System对象
        dynamics: CR3BP_Dynamics对象

    返回:
        OrbitFamily对象或None
    """
    seed_dict = RO_SEEDS[ro_type]
    print(f"\n生成 {ro_type} RO族...")
    print(f"  目标周期: {seed_dict['period']:.6f} TU")

    # 步骤1: 修正种子轨道
    print(f"\n[步骤1] 修正种子轨道...")
    corrected_orbit = correct_seed_ro(dynamics, seed_dict, system)
    if corrected_orbit is None:
        return None

    # 步骤2: 自然延拓
    print(f"\n[步骤2] 开始延拓...")

    corrector_for_cont = DifferentialCorrection(dynamics)
    corrector_for_cont.setup_2D_symmetric_x_fixed_x0(seed_dict["x0"])
    corrector_for_cont.tolerance = 1e-12
    corrector_for_cont.max_iterations = 50

    continuation = Continuation(corrector_for_cont, param="x0")

    x0_range = seed_dict["x0_range"]
    family_result = continuation.natural_continuation(
        corrected_orbit, x0_range, 0.005, verbose=False
    )

    if family_result is not None and len(family_result) > 0:
        print(f"\n{ro_type} RO族生成: {len(family_result)} 条轨道")
    else:
        print(f"\n{ro_type} RO族延拓失败")

    return family_result


# =============================================================================
# 主程序
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="RO族生成")
    parser.add_argument(
        "--family",
        choices=["32", "31", "both"],
        default="both",
        help="选择要处理的RO族",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/ro",
        help="输出目录",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("共振轨道(RO)族生成")
    print(f"e2m2e version: {e2m2e.__version__}")
    print("=" * 60)

    # 创建系统
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system)
    dynamics.integrator = "DOP853"

    # 生成轨道族
    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)

    if args.family in ["32", "both"]:
        family_32 = generate_ro_family("3:2", system, dynamics)
        if family_32 is not None:
            # 保存轨道族
            filename = f"ro_32_family_{timestampNow()}.json"
            output_path = f"{args.output_dir}/{filename}"
            family_32.save_to_file(output_path)
            print(f"3:2 RO族已保存: {output_path}")

    if args.family in ["31", "both"]:
        family_31 = generate_ro_family("3:1", system, dynamics)
        if family_31 is not None:
            # 保存轨道族
            filename = f"ro_31_family_{timestampNow()}.json"
            output_path = f"{args.output_dir}/{filename}"
            family_31.save_to_file(output_path)
            print(f"3:1 RO族已保存: {output_path}")

    print(f"\n{'=' * 60}")
    print("完成！")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
