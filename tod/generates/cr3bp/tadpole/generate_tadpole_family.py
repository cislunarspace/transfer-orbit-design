"""generate_tadpole_family Tadpole轨道生成脚本。

本模块在地月 CR3BP 中延拓生成 Tadpole 轨道族。通过改变振幅参数，
系统生成一系列围绕单个三角平动点的蝌蚪形轨道。

本脚本通过 ``FamilyGenerator`` 基类实现，族特有逻辑在子类钩子中声明，
共享流程由基类处理。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.tadpole.generate_tadpole_family --help
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


class TadpoleFamilyGenerator(FamilyGenerator):
    """Tadpole 轨道族生成器。"""

    @classmethod
    def add_family_args(cls, parser) -> None:
        """声明 Tadpole 族特有的 CLI 参数。"""
        parser.add_argument(
            "--libration-point",
            type=str,
            default="L4",
            choices=["L4", "L5"],
            help="平动点选择，默认 L4",
        )
        parser.add_argument(
            "--leading-trailing",
            type=str,
            default="leading",
            choices=["leading", "trailing"],
            help="构型选择，默认 leading",
        )
        parser.add_argument(
            "--amplitude-min",
            type=float,
            default=0.01,
            help="延拓振幅下限（无量纲）",
        )
        parser.add_argument(
            "--amplitude-max",
            type=float,
            default=0.5,
            help="延拓振幅上限（无量纲）",
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
        """构造 Tadpole 种子轨道（尚未实现）。"""
        raise NotImplementedError("Tadpole 种子轨道构造尚未实现")

    def _setup_corrector(self, args):
        """配置 Tadpole 微分修正器（尚未实现）。"""
        raise NotImplementedError("Tadpole 微分修正器配置尚未实现")

    def _run_continuation(self, corrector, seed_orbit, args):
        """执行 Tadpole 延拓生成轨道族（尚未实现）。"""
        raise NotImplementedError("Tadpole 延拓生成尚未实现")


def main() -> None:
    """Tadpole 轨道族生成入口。"""
    config = FamilyGeneratorConfig(
        family_type="tadpole",
        output_subdir="tadpole",
        summary_title="  Earth-Moon Tadpole 轨道族：配置、统计与代表性轨道",
        summary_columns=[],
        n_milestones=5,
    )
    gen = TadpoleFamilyGenerator(config)
    args = gen.parse_args()
    setup_logging(args.log_level)
    gen.run(args)


if __name__ == "__main__":
    inject_debug_args(
        sys.argv,
        [
            "--libration-point", "L4",
            "--leading-trailing", "leading",
            "--amplitude-min", "0.01",
            "--amplitude-max", "0.5",
            "--step-size", "0.01",
            "--n-orbits", "50",
        ],
    )
    main()
