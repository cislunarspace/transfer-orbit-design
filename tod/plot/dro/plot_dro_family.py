"""Thin wrapper for DRO family plotting — delegates to FamilyPlotOrchestrator."""

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
    family_type="DRO",
    default_filename="dro_31_family_0.141886-0.9-0.005_1779175978",
    output_subdir="dro",
    plane="xy",
    radius_3d=1.5,
    supports_center_choice=True,
    step=5,
)


def main() -> None:
    parser = build_argparser(description="绘制 DRO 轨道族")
    args = parser.parse_args()
    FamilyPlotOrchestrator(CONFIG, args).run()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        logger.debug("使用代码内置调试参数")
    main()
