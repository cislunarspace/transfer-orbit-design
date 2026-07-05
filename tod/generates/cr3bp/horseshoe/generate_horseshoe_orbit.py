"""generate_horseshoe_orbit Horseshoe轨道生成脚本。

本模块在地月 CR3BP 中通过微分修正生成单条轨道。轨道呈马蹄形跨越两个三角平动点（L4 和 L5），在地月空间中形成大范围顺行环绕结构。
输入为命令行给出的初始状态、周期猜测和延拓配置；输出为 output/horseshoe/ 下对应轨道类别的 JSON/CSV 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.horseshoe.generate_horseshoe_orbit --help
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

OUTPUT_DIR = project_root / "output" / "horseshoe"


def parse_args():
    """解析命令行参数。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="在地月 CR3BP 中生成 Horseshoe 轨道。轨道呈马蹄形跨越两个三角平动点（L4 和 L5），在地月空间中形成大范围顺行环绕结构。（跨越两个三角平动点的马蹄形轨道）", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--amplitude", type=float, default=0.1, help="种子轨道振幅（无量纲）。")
    parser.add_argument("--libration-point", type=str, default="L4", choices=["L4", "L5"], help="平动点选择（L4/L5）。")
    return parser.parse_args()


def main():
    """执行脚本主流程。

    Returns:
        None。
    """
    parse_args()
    raise NotImplementedError("Horseshoe 轨道生成尚未实现")


if __name__ == "__main__":
    # IDE 调试模式
    if len(sys.argv) == 1:
        sys.argv += [
            "--amplitude", "0.1",
            "--libration-point", "L4",
        ]
        logger.debug("使用代码内置调试参数")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='horseshoe',
    name='generate_horseshoe_orbit',
    description='生成轨道',
    script_path='tod/generates/cr3bp/horseshoe/generate_horseshoe_orbit.py',
    output_dir='output/horseshoe',
    group_label='生成',
    cli_params=[
        CliParam('--amplitude', '振幅', 'float', '0.1', help='种子轨道振幅（无量纲）。'),
        CliParam('--libration-point', '平动点', 'select', 'L4', choices=('L1', 'L2', 'L3', 'L4', 'L5'), help='平动点选择（L4/L5）。'),
    ],
)
