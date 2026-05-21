"""Thin wrapper for 3:2 RRO family plotting — delegates to FamilyPlotOrchestrator."""

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
    parser = build_argparser(description="绘制 RRO 轨道族")
    args = parser.parse_args()
    FamilyPlotOrchestrator(CONFIG, args).run()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += ["--start", "-1", "--end", "-1"]
        logger.debug("使用代码内置调试参数")
    main()
