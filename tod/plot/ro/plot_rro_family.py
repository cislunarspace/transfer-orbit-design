"""plot_rro_family 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.ro.plot_rro_family --help
"""


import logging
import sys

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
    family_type="3:2 RRO",
    default_filename="rro_32_family_3856916046",
    output_subdir="ro",
    plane="xy",
    center_3d=(-0.85, 0, 0.1),
    radius_3d=0.5,
    elev_3d=20,
    azim_3d=-90,
    show_seed_overlay=True,
    target_period=4 * __import__("numpy").pi,
)


def main() -> None:
    """执行脚本主流程。
    
    Returns:
        None。
    """
    parser = build_argparser(description="绘制 RRO 轨道族")
    args = parser.parse_args()
    FamilyPlotOrchestrator(CONFIG, args).run()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += ["--start", "-1", "--end", "-1"]
        logger.debug("使用代码内置调试参数")
    main()
