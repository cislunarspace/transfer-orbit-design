"""
生成 3:1 共振轨道族

本脚本实现：
1. 创建CR3BP系统和动力学模型
2. 设置3:1 RO种子轨道的初始状态向量
3. 利用差分修正器修正种子轨道
4. 采用自然延拓方法生成完整轨道族

3:1共振轨道特征：
  - T = 2π ≈ 6.283 TU (航天器3圈/月球1圈)
  - y幅值点: x=-0.8805, y=0.3921

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
# 系统参数
# =============================================================================
T_MOON = 2 * np.pi  # 月球恒星周期(无量纲)
T_RO_31 = 1 * T_MOON  # 2π ≈ 6.283 TU

# 3:1 RO 种子轨道参数（论文Table 2）
SEED_X0 = -0.8805  # y幅值点x坐标
SEED_Y0 = 0.3921   # y幅值点y坐标
SEED_Y_DOT0 = 0.0  # 需要通过微分修正确定
X0_RANGE = (-1.0, -0.7)  # 延拓x0范围


def correct_seed_ro31(dynamics, system):
    """修正3:1 RO种子轨道

    参数:
        dynamics: CR3BP_Dynamics对象
        system: CR3BP_System对象

    返回:
        修正后的Orbit或None
    """
    period = T_RO_31

    # 创建初始状态（从y幅值点出发）
    initial_state = [SEED_X0, SEED_Y0, 0.0, 0.0, SEED_Y_DOT0, 0.0]

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
    corrector.setup_2D_symmetric_x_fixed_x0(SEED_X0)
    corrector.tolerance = 1e-12
    corrector.max_iterations = 50

    corrected_orbit = corrector.iterate_correction(orbit, verbose=True)

    if corrected_orbit is None or not corrected_orbit.correction_success:
        print(f"  [错误] 种子轨道修正失败！")
        return None

    print(f"  修正后周期: {corrected_orbit.period:.6f} TU")
    print(f"  修正后y_dot0: {corrected_orbit.states[0, 4]:.6f}")

    return corrected_orbit


def generate_ro31_family(system, dynamics):
    """生成3:1 RO族

    参数:
        system: CR3BP_System对象
        dynamics: CR3BP_Dynamics对象

    返回:
        OrbitFamily对象或None
    """
    print(f"\n生成 3:1 RO族...")
    print(f"  目标周期: {T_RO_31:.6f} TU")

    # 步骤1: 修正种子轨道
    print(f"\n[步骤1] 修正种子轨道...")
    corrected_orbit = correct_seed_ro31(dynamics, system)
    if corrected_orbit is None:
        return None

    # 步骤2: 自然延拓
    print(f"\n[步骤2] 开始延拓...")

    corrector_for_cont = DifferentialCorrection(dynamics)
    corrector_for_cont.setup_2D_symmetric_x_fixed_x0(SEED_X0)
    corrector_for_cont.tolerance = 1e-12
    corrector_for_cont.max_iterations = 50

    continuation = Continuation(corrector_for_cont, param="x0")

    family_result = continuation.natural_continuation(
        corrected_orbit, X0_RANGE, 0.005, verbose=False
    )

    if family_result is not None and len(family_result) > 0:
        print(f"\n3:1 RO族生成: {len(family_result)} 条轨道")
    else:
        print(f"\n3:1 RO族延拓失败")

    return family_result


# =============================================================================
# 主程序
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="3:1 RO族生成")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/ro",
        help="输出目录",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("3:1 共振轨道(RO)族生成")
    print(f"e2m2e version: {e2m2e.__version__}")
    print("=" * 60)

    # 创建系统
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system)
    dynamics.integrator = "DOP853"

    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)

    # 生成轨道族
    family_31 = generate_ro31_family(system, dynamics)
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
