"""generate_lpo_orbit LPO轨道生成脚本。

本模块在地月 CR3BP 中通过微分修正生成单条轨道。围绕三角平动点（L4 或 L5）的长周期振荡轨道，周期较长，覆盖范围更大。
输入为命令行给出的初始状态、周期猜测和延拓配置；输出为 output/lpo/ 下对应轨道类别的 JSON/CSV 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.lpo.generate_lpo_orbit --help
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

OUTPUT_DIR = project_root / "output" / "lpo"


def parse_args():
    """解析命令行参数。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="生成 LPO（Long Period Orbit，三角平动点附近长周期轨道）", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--libration-point", type=str, default="L4", choices=["L4", "L5"], help="平动点选择（L4/L5）。")
    parser.add_argument("--amplitude", type=float, default=0.1, help="种子轨道振幅（无量纲）。")
    parser.add_argument("--period-guess", type=float, default=3.0, help="初始周期猜测（无量纲 TU）。")
    return parser.parse_args()


def main():
    """执行脚本主流程。

    Returns:
        None。
    """
    parse_args()
    raise NotImplementedError("LPO 轨道生成尚未实现")


if __name__ == "__main__":
    # IDE 调试模式
    if len(sys.argv) == 1:
        sys.argv += [
            "--libration-point", "L4",
            "--amplitude", "0.1",
            "--period-guess", "3.0",
        ]
        logger.debug("使用代码内置调试参数")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='lpo',
    name='generate_lpo_orbit',
    description='生成轨道',
    script_path='tod/generates/cr3bp/lpo/generate_lpo_orbit.py',
    output_dir='output/lpo',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L4', choices=('L4', 'L5'), help='平动点选择（L4/L5）。'),
        CliParam('--amplitude', '振幅', 'float', '0.1', help='种子轨道振幅（无量纲）。'),
        CliParam('--period-guess', '周期猜测值', 'float', '3.0', help='初始周期猜测（无量纲 TU）。'),
    ],
)
