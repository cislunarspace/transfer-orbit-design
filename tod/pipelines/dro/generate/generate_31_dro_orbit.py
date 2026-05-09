"""
生成 3:1 DRO 轨道（远距离逆行轨道）

使用固定周期微分校正法，基于文献中的初值生成指定周期的 DRO 轨道。

参考文献:
    Cui et al. (2025). Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits.
    Journal of Guidance, Control, and Dynamics.

初值来源 (Table 2):
    - x = 1.1202 nd (初始x坐标，无量纲)
    - y_dot = -0.4618 nd (初始y方向速度，无量纲)
    - T = 9.11 days ≈ 2.095 TU (轨道周期)
"""

import argparse
from pathlib import Path
import time

import e2m2e
from e2m2e.core import Orbit
from tod.commons.common import MU, TU

project_root = Path(__file__).resolve().parent.parent.parent.parent

# 项目根目录
OUTPUT_DIR = project_root / "output" / "dro"


def parse_args():
    parser = argparse.ArgumentParser(description="生成 3:1 DRO 轨道（固定周期微分校正）")
    parser.add_argument("--x0", type=float, default=1.1202, help="初始 x 坐标（无量纲）")
    parser.add_argument("--vy0", type=float, default=-0.4618, help="初始 y 方向速度（无量纲）")
    parser.add_argument("--period", type=float, default=2.095, help="目标周期（无量纲）")
    return parser.parse_args()


def main():
    args = parse_args()

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. 3:1 DRO 初值（来自文献 Table 2）
    # =============================================================================
    # DRO特征：平面内运动（y=z=0），关于x轴对称（vx=vz=0）
    # 状态向量格式：[x, y, z, vx, vy, vz]，均为无量纲量
    x0 = args.x0  # 初始x坐标（无量纲）
    vy0 = args.vy0  # 初始y方向速度（无量纲）

    # 目标周期：9.11 days ≈ 2.095 TU (Time Unit)
    # TU = 4.34811305 days ( lunar sidereal period )
    target_period = args.period  # 无量纲时间单位
    t_half = target_period / 2  # 半周期

    print(f"目标轨道: 3:1 DRO")
    print(f"初始状态: x0={x0}, vy0={vy0}")
    print(f"目标周期: {target_period:.4f} TU ({target_period * TU:.2f} days)")
    print(f"半周期: {t_half:.4f} TU")

    # =============================================================================
    # 3. 配置固定周期微分校正器
    # =============================================================================
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    corrector.setup_2D_symmetric_x_fixed_t(t_half=t_half)

    print(f"\n微分校正器配置:")
    print(f"  模式: setup_2D_symmetric_x_fixed_t")
    print(f"  固定参数: T_half = {t_half:.4f}")
    print(f"  自由变量: {corrector.free_variables}")
    print(f"  约束条件: {list(corrector.target_conditions.keys())}")

    # =============================================================================
    # 4. 初始猜测
    # =============================================================================
    initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
    times = [0]  # 第一个历元时刻

    orbit_init = Orbit(states=[initial_state], times=times)

    print(f"\n初始猜测:")
    print(f"  状态: {initial_state}")

    # =============================================================================
    # 5. 执行迭代修正
    # =============================================================================
    print(f"\n开始迭代修正...")
    orbit_result = corrector.iterate_correction(initial_guess=orbit_init, verbose=True)

    # =============================================================================
    # 6. 保存结果
    # =============================================================================
    if orbit_result is not None:
        print(f"\n[ok] 成功找到 3:1 DRO 轨道!")
        print(f"  修正后周期: {orbit_result.period:.6f} TU")
        print(f"  周期误差: {abs(orbit_result.period - target_period):.6e}")

        # 保存轨道数据
        ts = int(time.time())
        output_file = OUTPUT_DIR / f"dro_31_{ts}.json"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        orbit_result.save_to_file(filename=str(output_file))
        print(f"  保存至: {output_file}")
    else:
        print(f"\n[error] 修正失败: {corrector.termination_reason}")


if __name__ == "__main__":
    main()
