"""plot_halo_family 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.halo.plot_halo_family --help
"""


import logging
import sys
from pathlib import Path

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

from tod.plot.family_plot_orchestrator import (
    FamilyPlotConfig,
    FamilyPlotOrchestrator,
    build_argparser,
)

logger = logging.getLogger(__name__)

CONFIG = FamilyPlotConfig(
    family_type="Halo",
    default_filename="halo_L1_N_family_3857278981",
    output_subdir="halo",
    plane="xz",
    dynamic_bounds=True,
    allow_single_orbit=True,
    libration_point_sizes=[20, 20, 20, 20, 20],
)


def main(
    plot1: bool | None = None,
    plot2: bool | None = None,
    plot3: bool | None = None,
) -> None:
    """执行脚本主流程。
    
    Args:
        plot1: 调用方传入的参数值。
        plot2: 调用方传入的参数值。
        plot3: 调用方传入的参数值。
    
    Returns:
        None。
    """
    parser = build_argparser(description="绘制 Halo 轨道族")
    args = parser.parse_args()

    if plot1 is not None:
        args.plot_global_2d = plot1
    if plot2 is not None:
        args.plot_global_3d = plot2
    if plot3 is not None:
        args.plot_jacobi_stability = plot3

    FamilyPlotOrchestrator(CONFIG, args).run()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += ["--start", "-1", "--end", "-1"]
        filepath = r"C:\Users\ouyan\codes\transfer-orbit-design\output\halo\halo_L1_N_0.1_1778419695.json"
        if filepath:
            sys.argv += ["--json-file", filepath]
        plot1 = 0
        plot2 = 1
        plot3 = 0
        logger.debug("使用代码内置调试参数")
        main(plot1=plot1, plot2=plot2, plot3=plot3)
    else:
        main()
