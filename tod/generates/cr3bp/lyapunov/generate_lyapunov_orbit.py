"""generate_lyapunov_orbit Lyapunov轨道生成脚本。

本模块在地月 CR3BP 中通过微分修正生成单条轨道。运动局限在 xy 平面内的平面周期轨道，围绕共线平动点（L1/L2/L3）振荡，是 CR3BP 中最基本的周期轨道类型之一。
输入为命令行给出的初始状态、周期猜测和延拓配置；输出为 output/lyapunov/ 下对应轨道类别的 JSON/CSV 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.lyapunov.generate_lyapunov_orbit --help
"""
import argparse
import logging
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = project_root / "output" / "lyapunov"


def parse_args():
    """解析命令行参数。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="在地月 CR3BP 中生成 Lyapunov 轨道。运动局限在 xy 平面内的平面周期轨道，围绕共线平动点（L1/L2/L3）振荡，是 CR3BP 中最基本的周期轨道类型之一。（平面周期轨道）", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--libration-point", type=str, default="L1", choices=["L1", "L2", "L3"], help="共线平动点选择（L1/L2/L3）。")
    parser.add_argument("--amplitude-x", type=float, default=0.1, help="种子轨道 x 方向振幅（无量纲）。")
    parser.add_argument("--period-guess", type=float, default=3.0, help="初始周期猜测（无量纲 TU）。")
    return parser.parse_args()


def main():
    """执行脚本主流程。

    Returns:
        None。
    """
    parse_args()
    raise NotImplementedError("Lyapunov 轨道生成尚未实现")


if __name__ == "__main__":
    # IDE 调试模式
    if len(sys.argv) == 1:
        sys.argv += [
            "--libration-point", "L1",
            "--amplitude-x", "0.1",
            "--period-guess", "3.0",
        ]
        logger.debug("使用代码内置调试参数")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='lyapunov',
    name='generate_lyapunov_orbit',
    description='生成轨道',
    script_path='tod/generates/cr3bp/lyapunov/generate_lyapunov_orbit.py',
    output_dir='output/lyapunov',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L1', choices=('L1', 'L2', 'L3'), help='平动点选择（L1/L2/L3）。'),
        CliParam('--amplitude-x', 'x 方向振幅', 'float', '0.1', help='种子轨道 x 方向振幅（无量纲）。'),
        CliParam('--period-guess', '周期猜测值', 'float', '3.0', help='初始周期猜测（无量纲 TU）。'),
    ],
)
