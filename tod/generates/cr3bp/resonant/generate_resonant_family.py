"""generate_resonant_family Resonant轨道生成脚本。

本模块在地月 CR3BP 中延拓生成 Resonant 轨道族。通过改变 z 方向参数，
系统生成一系列指定共振比例的周期轨道。

本脚本通过 ``FamilyGenerator`` 基类实现，族特有逻辑在子类钩子中声明，
共享流程由基类处理。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.resonant.generate_resonant_family --help
"""


from __future__ import annotations

import logging
import sys

from tod.generates.cr3bp._family_pipeline import (
    FamilyGenerator,
    FamilyGeneratorConfig,
    inject_debug_args,
    setup_logging,
)

logger = logging.getLogger(__name__)


class ResonantFamilyGenerator(FamilyGenerator):
    """Resonant 轨道族生成器。"""

    @classmethod
    def add_family_args(cls, parser) -> None:
        """声明 Resonant 族特有的 CLI 参数。"""
        parser.add_argument(
            "--ratio",
            type=str,
            default="3:1",
            choices=["3:1", "3:2", "2:1"],
            help="共振比例，默认 3:1",
        )
        parser.add_argument(
            "--method",
            type=str,
            default="natural",
            choices=["natural", "pseudo_arclength"],
            help="延拓方法，默认 natural",
        )
        parser.add_argument(
            "--z-min",
            type=float,
            default=0.01,
            help="延拓 z 参数下限（无量纲）",
        )
        parser.add_argument(
            "--z-max",
            type=float,
            default=0.5,
            help="延拓 z 参数上限（无量纲）",
        )
        parser.add_argument(
            "--step-size",
            type=float,
            default=0.01,
            help="延拓步长（无量纲）",
        )
        parser.add_argument(
            "--n-orbits",
            type=int,
            default=50,
            help="目标生成轨道数",
        )

    def _get_seed_orbit(self, args):
        """构造 Resonant 种子轨道（尚未实现）。"""
        raise NotImplementedError("Resonant 种子轨道构造尚未实现")

    def _setup_corrector(self, args):
        """配置 Resonant 微分修正器（尚未实现）。"""
        raise NotImplementedError("Resonant 微分修正器配置尚未实现")

    def _run_continuation(self, corrector, seed_orbit, args):
        """执行 Resonant 延拓生成轨道族（尚未实现）。"""
        raise NotImplementedError("Resonant 延拓生成尚未实现")


def main() -> None:
    """Resonant 轨道族生成入口。"""
    config = FamilyGeneratorConfig(
        family_type="resonant",
        output_subdir="resonant",
        summary_title="  Earth-Moon Resonant 轨道族：配置、统计与代表性轨道",
        summary_columns=[],
        n_milestones=5,
    )
    gen = ResonantFamilyGenerator(config)
    args = gen.parse_args()
    setup_logging(args.log_level)
    gen.run(args)


if __name__ == "__main__":
    inject_debug_args(
        sys.argv,
        [
            "--ratio", "3:1",
            "--method", "natural",
            "--z-min", "0.01",
            "--z-max", "0.5",
            "--step-size", "0.01",
            "--n-orbits", "50",
        ],
    )
    main()
