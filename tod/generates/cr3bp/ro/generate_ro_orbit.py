"""generate_ro_orbit RO（共振轨道）单轨生成脚本。

本模块在地月 CR3BP 中通过固定周期微分修正生成单条 3:1 或 3:2 共振轨道。
通过 ``--ratio`` 参数区分具体共振比例。

RO = Resonant Orbit（共振轨道），3:1 表示轨道周期是月球绕地球周期的 3 倍，
3:2 表示 1.5 倍。

运行示例:
    .. code-block:: bash

       uv run python tod/generates/cr3bp/ro/generate_ro_orbit.py --help
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import e2m2e
from e2m2e.core import Orbit

from tod.commons.constants import MU, TU

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "ro"

# 各共振比的默认种子初值（x0, vy0, period）
_RATIO_DEFAULTS: dict[str, dict[str, float]] = {
    "3:1": {"x0": -0.8805, "vy0": 0.3921, "period": 27.32},
    "3:2": {"x0": -1.1453, "vy0": 0.4633, "period": 54.64},
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 命令行参数列表；为 None 时使用 sys.argv[1:]。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(
        description="生成单条 RO（共振轨道）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ratio",
        type=str,
        default="3:1",
        choices=["3:1", "3:2"],
        help="共振比例",
    )
    parser.add_argument(
        "--x0",
        type=float,
        default=None,
        help="初始 x 坐标（无量纲），默认值由 --ratio 决定",
    )
    parser.add_argument(
        "--vy0",
        type=float,
        default=None,
        help="初始 y 方向速度（无量纲），默认值由 --ratio 决定",
    )
    parser.add_argument(
        "--period",
        type=float,
        default=None,
        help="目标周期（天），默认值由 --ratio 决定",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """执行脚本主流程。"""
    args = parse_args(argv)
    defaults = _RATIO_DEFAULTS[args.ratio]

    x0 = args.x0 if args.x0 is not None else defaults["x0"]
    vy0 = args.vy0 if args.vy0 is not None else defaults["vy0"]
    period_days = args.period if args.period is not None else defaults["period"]
    target_period = period_days / TU
    t_half = target_period / 2

    logger.info("目标轨道: %s RO", args.ratio)
    logger.info("初始状态: x0=%s, vy0=%s", x0, vy0)
    logger.info("目标周期: %.4f TU (%.2f days)", target_period, period_days)

    # 1. 系统与动力学模型初始化
    system = e2m2e.core.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.CR3BP_Dynamics(system=system)

    # 2. 配置固定周期微分校正器
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    corrector.setup_2D_symmetric_x_fixed_t(t_half=t_half)

    # 3. 初始猜测
    initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
    orbit_init = Orbit(states=[initial_state], times=[0])

    # 4. 执行迭代修正
    logger.info("开始迭代修正...")
    orbit_result = corrector.iterate_correction(initial_guess=orbit_init, verbose=True)

    # 5. 保存结果
    if orbit_result is not None:
        logger.info("成功找到 %s RO 轨道!", args.ratio)
        logger.info("  修正后周期: %.6f TU", orbit_result.period)

        ts = int(time.time())
        ratio_tag = args.ratio.replace(":", "")
        output_file = OUTPUT_DIR / f"ro_{ratio_tag}_{ts}.json"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        orbit_result.save_to_file(filename=str(output_file))
        logger.info("  保存至: %s", output_file)
    else:
        logger.error("修正失败: %s", corrector.termination_reason)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += [
            "--ratio", "3:1",
            "--x0", "-0.8805",
            "--vy0", "0.3921",
            "--period", "27.32",
        ]
        logger.debug("使用代码内置调试参数")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ro',
    name='generate_ro_orbit',
    description='生成共振轨道',
    script_path='tod/generates/cr3bp/ro/generate_ro_orbit.py',
    output_dir='output/ro',
    group_label='生成',
    cli_params=[
        CliParam('--ratio', '共振比例', 'select', '3:1', choices=('3:1', '3:2'), help='共振比例（3:1/3:2）。'),
        CliParam('--x0', '初始 x 坐标', 'float', '', help='初始 x 坐标（无量纲），默认值由共振比例决定。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '', help='初始 y 方向速度（无量纲），默认值由共振比例决定。', unit_group='velocity'),
        CliParam('--period', '目标周期', 'float', '', help='目标周期（天），默认值由共振比例决定。', unit_group='time', default_unit='days'),
    ],
)
