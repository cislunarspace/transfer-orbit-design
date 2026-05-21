"""Thin wrapper for 3:2 RO family plotting — delegates to FamilyPlotOrchestrator."""

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
    family_type="3:2 RO",
    default_filename="ro_32_family_-1.2--0.8-0.005_3857719350",
    output_subdir="ro",
    plane="xy",
    center_3d=(-0.9, 0, 0),
    radius_3d=0.5,
    elev_3d=0,
    azim_3d=-90,
    show_seed_overlay=True,
    target_period=4 * __import__("numpy").pi,
)


def main() -> None:
    parser = build_argparser(description="绘制 3:2 共振轨道族")
    args = parser.parse_args()
    FamilyPlotOrchestrator(CONFIG, args).run()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += ["--start", "-1", "--end", "42"]
        logger.debug("使用代码内置调试参数")
    main()
