"""
生成 3:2 共振轨道族

本脚本实现：
1. 创建CR3BP系统和动力学模型
2. 设置3:2 RO种子轨道的初始状态向量
3. 利用差分修正器修正种子轨道
4. 采用自然延拓方法生成完整轨道族

3:2共振轨道特征：
  - T = 4π ≈ 12.566 TU (航天器3圈/月球2圈)
  - y幅值点: x=-1.1453, y=0.4633

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

import argparse
import logging
import sys
from pathlib import Path

import e2m2e
import time

from tod.commons.common import MU, TU

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
OUTPUT_DIR = project_root / "output"


def parse_args():
    parser = argparse.ArgumentParser(description="生成 3:2 共振轨道族（差分修正 + 自然延拓）")
    parser.add_argument("--x0", type=float, default=-1.1453, help="初始 x 坐标（无量纲）")
    parser.add_argument("--vy0", type=float, default=0.4633, help="初始 y 方向速度（无量纲）")
    parser.add_argument("--period", type=float, default=54.64 / TU, help="轨道周期（无量纲）")
    parser.add_argument("--param-min", type=float, default=-1.2, help="延拓参数范围下限")
    parser.add_argument("--param-max", type=float, default=-0.8, help="延拓参数范围上限")
    parser.add_argument("--step-size", type=float, default=0.005, help="延拓步长")
    return parser.parse_args()


def main():
    args = parse_args()

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. 种子轨道初始状态定义
    # =============================================================================
    # 3:2 RO特征：平面内运动（y幅值点处y_dot=0），关于x轴对称（vx=vz=0）
    # 初始状态向量格式：[x, y, z, vx, vy, vz]，均为无量纲量
    x0 = args.x0  # 初始x坐标（无量纲）
    z0 = 0.0  # 初始z坐标（无量纲）
    vy0 = args.vy0  # 初始y方向速度（无量纲）
    vz0 = 0.0  # 初始z方向速度（无量纲）
    initial_state = [x0, 0.0, z0, 0.0, vy0, vz0]
    times = [0]  # 第一个历元时刻
    seed_orbit = e2m2e.core.orbit.Orbit(states=[initial_state], times=times)
    seed_orbit.period = args.period  # 轨道周期（无量纲时间）

    # =============================================================================
    # 3. 种子轨道差分修正
    # =============================================================================
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    corrector.setup_2D_symmetric_x_fixed_x0(x0=x0)
    seed_RO = corrector.iterate_correction(initial_guess=seed_orbit, verbose=True)

    # =============================================================================
    # 4. 自然延拓生成轨道族
    # =============================================================================
    continuator = e2m2e.algorithms.Continuation(corrector=corrector)
    step_size = args.step_size
    param_min = args.param_min
    param_max = args.param_max
    family_result = continuator.natural_continuation(
        seed_orbit=seed_RO,
        param_range=(param_min, param_max),  # x0参数延拓范围
        step_size=step_size,  # 延拓步长
    )  # //TODO 这里的延拓逻辑存在问题，当延拓失败的时候，不会提示，好像会将轨道的值设置为一个特殊值。

    # =============================================================================
    # 5. 保存轨道数据
    # =============================================================================
    # 命名规则：ro_32_family_{param_min}-{param_max}-{step_size}_{ts}.json
    ts = int(time.time())
    family_result.save_to_file(
        filename=str(
            OUTPUT_DIR
            / "ro"
            / f"ro_32_family_{param_min}-{param_max}-{step_size}_{ts}.json"
        )
    )
    logger.info("已保存至：ro_32_family_%s-%s-%s_%d.json", param_min, param_max, step_size, ts)


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--x0", "-1.1453",                            # 初始 x 坐标（无量纲）
            "--vy0", "0.4633",                            # 初始 y 方向速度（无量纲）
            "--period", "12.566370614359172",             # 轨道周期（无量纲，54.64/TU）
            "--param-min", "-1.2",                        # 延拓参数范围下限
            "--param-max", "-0.8",                        # 延拓参数范围上限
            "--step-size", "0.005",                       # 延拓步长
        ]
        logger.debug("使用代码内置调试参数")
    main()
