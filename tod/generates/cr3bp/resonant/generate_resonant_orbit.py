"""generate_resonant_orbit 轨道生成脚本。

本模块在地月 CR3BP 中构造种子轨道，调用 e2m2e 的微分修正、自然延拓或伪弧长延拓算法生成目标轨道。输入为命令行给出的初始状态、周期猜测和延拓配置；输出为 output/ 下对应轨道类别的 JSON/CSV 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.resonant.generate_resonant_orbit --help
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

OUTPUT_DIR = project_root / "output" / "resonant"


def parse_args():
    """解析命令行参数。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="在地月 CR3BP 中生成指定 m:n 共振比例的周期轨道。", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--ratio", type=str, default="3:1", help="共振比例（如 3:1, 3:2, 2:1）")
    parser.add_argument("--z0", type=float, default=0.0, help="初始 z 位置")
    parser.add_argument("--vy0", type=float, default=0.0, help="初始 y 方向速度")
    parser.add_argument("--period-guess", type=float, default=3.0, help="周期猜测值")
    parser.add_argument("--libration-point", type=str, default="secondary", choices=["secondary", "L1", "L2"], help="平动点选择（默认secondary表示在次要天体附近）")
    return parser.parse_args()


def main():
    """执行脚本主流程。

    Returns:
        None。
    """
    args = parse_args()
    raise NotImplementedError("Resonant 轨道生成尚未实现")


if __name__ == "__main__":
    # IDE 调试模式
    if len(sys.argv) == 1:
        sys.argv += [
            "--ratio", "3:1",
            "--z0", "0.0",
            "--vy0", "0.0",
            "--period-guess", "3.0",
            "--libration-point", "secondary",
        ]
        logger.debug("使用代码内置调试参数")
    main()
