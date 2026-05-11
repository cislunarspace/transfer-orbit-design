"""
生成远距离逆行轨道族

本脚本实现：
1. 创建CR3BP系统和动力学模型
2. 设置DRO种子轨道的初始状态向量
3. 利用差分修正器修正种子轨道
4. 采用自然延拓方法生成完整轨道族

"""

import argparse
import logging
import sys
import time
from pathlib import Path

import e2m2e
from e2m2e.core import Orbit
from tod.commons.common import MU

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "dro"


def parse_args():
    parser = argparse.ArgumentParser(description="生成 DRO 轨道族（差分修正 + 自然延拓）")
    parser.add_argument("--x0", type=float, default=0.79188556619742,
                        help="种子轨道初始 x 坐标（无量纲）")
    parser.add_argument("--vy0", type=float, default=0.53682,
                        help="种子轨道初始 vy 速度（无量纲）")
    parser.add_argument("--period", type=float, default=3.472526005624708,
                        help="初始周期猜测（无量纲）")
    parser.add_argument("--param-min", type=float, default=0.141886,
                        help="延拓参数范围下限（x0 最小值）")
    parser.add_argument("--param-max", type=float, default=0.9,
                        help="延拓参数范围上限（x0 最大值）")
    parser.add_argument("--step-size", type=float, default=0.005,
                        help="延拓步长")
    return parser.parse_args()


def main():
    args = parse_args()

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamic = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. 种子轨道初始状态定义
    # =============================================================================
    # DRO特征：平面内运动（y=z=0），关于x轴对称（vx=vz=0）
    # 初始状态向量格式：[x, y, z, vx, vy, vz]，均为无量纲量
    x0 = args.x0  # 初始x坐标（无量纲）
    vy0 = args.vy0  # 初始y方向速度（无量纲）

    initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
    times = [0]  # 第一个历元时刻

    seed_state = Orbit(states=[initial_state], times=times)
    seed_state.period = args.period  # 初始周期猜测（无量纲时间）

    # =============================================================================
    # 3. 种子轨道差分修正
    # =============================================================================
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamic)
    corrector.setup_2D_symmetric_x_fixed_x0(x0=x0)
    seed_DRO = corrector.iterate_correction(initial_guess=seed_state)

    # =============================================================================
    # 4. 自然延拓生成轨道族
    # =============================================================================
    continuation = e2m2e.algorithms.Continuation(corrector=corrector)
    param_min = args.param_min
    param_max = args.param_max
    step_size = args.step_size
    family_result = continuation.natural_continuation(
        seed_orbit=seed_DRO,
        param_range=(param_min, param_max),  # x0参数延拓范围
        step_size=step_size,  # 延拓步长
    )

    # =============================================================================
    # 5. 保存轨道数据
    # =============================================================================
    # 命名规则：dro_31_family_{param_min}-{param_max}-{step_size}_{ts}.json
    family_result.save_to_file(
        filename=str(
            OUTPUT_DIR
            / f"dro_31_family_{param_min}-{param_max}-{step_size}_{int(time.time())}.json"
        )
    )
    logger.info("已保存至：dro_31_family_%s-%s-%s_%d.json", param_min, param_max, step_size, int(time.time()))


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--x0", "0.79188556619742",                    # 种子轨道初始 x 坐标（无量纲）
            "--vy0", "0.53682",                            # 种子轨道初始 vy 速度（无量纲）
            "--period", "3.472526005624708",               # 初始周期猜测（无量纲）
            "--param-min", "0.141886",                     # 延拓参数范围下限（x0 最小值）
            "--param-max", "0.9",                          # 延拓参数范围上限（x0 最大值）
            "--step-size", "0.005",                        # 延拓步长
        ]
        logger.debug("使用代码内置调试参数")
    main()
