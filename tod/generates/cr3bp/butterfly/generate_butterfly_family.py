"""generate_butterfly_family Butterfly轨道生成脚本。

本模块在地月 CR3BP 中延拓生成 Butterfly 轨道族。通过改变振幅参数，
系统生成一系列连接两个共线平动点的对称周期轨道。

本脚本通过 ``FamilyGenerator`` 基类实现，族特有逻辑在子类钩子中声明，
共享流程由基类处理。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.butterfly.generate_butterfly_family --help
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


class ButterflyFamilyGenerator(FamilyGenerator):
    """Butterfly 轨道族生成器。"""

    @classmethod
    def add_family_args(cls, parser) -> None:
        """声明 Butterfly 族特有的 CLI 参数。"""
        parser.add_argument(
            "--libration-point",
            type=str,
            default="L1",
            choices=["L1", "L2", "L3"],
            help="平动点选择",
        )
        parser.add_argument(
            "--method",
            type=str,
            default="natural",
            choices=["natural", "pseudo_arclength"],
            help="延拓方法",
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
        """构造 Butterfly 种子轨道（尚未实现）。"""
        raise NotImplementedError("Butterfly 种子轨道构造尚未实现")

    def _setup_corrector(self, args):
        """配置 Butterfly 微分修正器（尚未实现）。"""
        raise NotImplementedError("Butterfly 微分修正器配置尚未实现")

    def _run_continuation(self, corrector, seed_orbit, args):
        """执行 Butterfly 延拓生成轨道族（尚未实现）。"""
        raise NotImplementedError("Butterfly 延拓生成尚未实现")


def main() -> None:
    """Butterfly 轨道族生成入口。"""
    config = FamilyGeneratorConfig(
        family_type="butterfly",
        output_subdir="butterfly",
        summary_title="  Earth-Moon Butterfly 轨道族：配置、统计与代表性轨道",
        summary_columns=[],
        n_milestones=5,
    )
    gen = ButterflyFamilyGenerator(config)
    args = gen.parse_args()
    setup_logging(args.log_level)
    gen.run(args)


if __name__ == "__main__":
    inject_debug_args(
        sys.argv,
        [
            "--libration-point", "L1",
            "--method", "natural",
            "--amplitude-min", "0.01",
            "--amplitude-max", "0.5",
            "--step-size", "0.01",
            "--n-orbits", "50",
        ],
    )
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='butterfly',
    name='generate_butterfly_family',
    description='生成轨道族',
    script_path='tod/generates/cr3bp/butterfly/generate_butterfly_family.py',
    output_dir='output/butterfly',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L1', choices=('L1', 'L2', 'L3'), help='平动点选择（L1/L2/L3）。'),
        CliParam('--method', '延拓方法', 'select', 'natural', choices=('natural', 'pseudo_arclength'), help='延拓方法（natural/pseudo_arclength）。'),
        CliParam('--amplitude-min', '最小振幅', 'float', '0.01', help='延拓振幅下限（无量纲）。'),
        CliParam('--amplitude-max', '最大振幅', 'float', '0.5', help='延拓振幅上限（无量纲）。'),
        CliParam('--step-size', '步长', 'float', '0.01', help='延拓步长（无量纲）。'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50', help='目标生成轨道数。'),
    ],
)
