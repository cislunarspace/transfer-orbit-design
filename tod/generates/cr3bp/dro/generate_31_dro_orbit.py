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
import logging
import sys
from pathlib import Path
import time

import e2m2e
from e2m2e.core import Orbit
from tod.commons.common import MU, TU

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

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
    x0 = args.x0
    vy0 = args.vy0
    target_period = args.period
    t_half = target_period / 2

    logger.info("目标轨道: 3:1 DRO")
    logger.info("初始状态: x0=%s, vy0=%s", x0, vy0)
    logger.info("目标周期: %.4f TU (%.2f days)", target_period, target_period * TU)

    # =============================================================================
    # 3. 配置固定周期微分校正器
    # =============================================================================
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    corrector.setup_2D_symmetric_x_fixed_t(t_half=t_half)

    logger.debug("微分校正器配置:")
    logger.debug("  模式: setup_2D_symmetric_x_fixed_t")
    logger.debug("  固定参数: T_half = %.4f", t_half)
    logger.debug("  自由变量: %s", corrector.free_variables)
    logger.debug("  约束条件: %s", list(corrector.target_conditions.keys()))

    # =============================================================================
    # 4. 初始猜测
    # =============================================================================
    initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
    times = [0]

    orbit_init = Orbit(states=[initial_state], times=times)

    logger.debug("初始猜测:")
    logger.debug("  状态: %s", initial_state)

    # =============================================================================
    # 5. 执行迭代修正
    # =============================================================================
    def on_iteration(iteration, error, converged):
        tag = " [收敛]" if converged else ""
        logger.info("  迭代 %d: 残差 %.2e%s", iteration, error, tag)

    logger.info("开始迭代修正...")
    orbit_result = corrector.iterate_correction(
        initial_guess=orbit_init, verbose=False, callback=on_iteration,
    )

    # =============================================================================
    # 6. 保存结果
    # =============================================================================
    if orbit_result is not None:
        logger.info("成功找到 3:1 DRO 轨道!")
        logger.info("  修正后周期: %.6f TU (%.4f days)", orbit_result.period, orbit_result.period * TU)
        logger.debug("  周期误差: %.6e", abs(orbit_result.period - target_period))

        ts = int(time.time())
        output_file = OUTPUT_DIR / f"dro_31_{ts}.json"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        orbit_result.save_to_file(filename=str(output_file))
        logger.info("  保存至: %s", output_file)
    else:
        logger.error("修正失败: %s", corrector.termination_reason)


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--x0", "1.1202",                               # 初始 x 坐标（无量纲）
            "--vy0", "-0.4618",                             # 初始 y 方向速度（无量纲）
            "--period", "2.095",                            # 目标周期（无量纲）
        ]
        logger.debug("使用代码内置调试参数")
    main()
