"""generate_axial_orbit Axial轨道生成脚本。

本模块在地月 CR3BP 中通过微分修正生成单条轨道。运动主要沿平动点连线方向（z 轴方向）振荡，属于三维周期轨道的一种特殊形态。
输入为命令行给出的初始状态、周期猜测和延拓配置；输出为 output/axial/ 下对应轨道类别的 JSON/CSV 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.axial.generate_axial_orbit --help
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import e2m2e
import numpy as np
from e2m2e.core import Orbit
from scipy import integrate as sci_integrate
from scipy.optimize import least_squares
from tod.commons.constants import MU, TU

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = project_root / "output" / "axial"


def parse_args():
    """解析命令行参数。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="在地月 CR3BP 中生成 Axial 轨道。运动主要沿平动点连线方向（z 轴方向）振荡，属于三维周期轨道的一种特殊形态。（沿平动点轴向的周期轨道）", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--libration-point", type=str, default="L1", choices=["L1", "L2", "L3", "L4", "L5"], help="平动点选择（L1/L2/L3），默认 L1。")
    parser.add_argument("--amplitude-z", type=float, default=0.1, help="种子轨道 z 方向振幅（无量纲），默认 0.1。")
    parser.add_argument("--period-guess", type=float, default=3.0, help="初始周期猜测（无量纲 TU），默认 3.0。")
    return parser.parse_args()


def main():
    """执行脚本主流程。

    Returns:
        None。
    """
    args = parse_args()
    raise NotImplementedError("Axial 轨道生成尚未实现")


if __name__ == "__main__":
    # IDE 调试模式
    if len(sys.argv) == 1:
        sys.argv += [
            "--libration-point", "L1",
            "--amplitude-z", "0.1",
            "--period-guess", "3.0",
        ]
        logger.debug("使用代码内置调试参数")
    main()
