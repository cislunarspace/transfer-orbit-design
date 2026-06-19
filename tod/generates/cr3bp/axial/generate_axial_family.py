"""generate_axial_family Axial轨道生成脚本。

本模块在地月 CR3BP 中延拓生成 Axial 轨道族。通过改变 z 方向振幅，
系统生成一系列沿平动点轴向振荡的周期轨道。

本脚本通过 ``FamilyGenerator`` 基类实现，族特有逻辑在子类钩子中声明，
共享流程由基类处理。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.axial.generate_axial_family --help
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


class AxialFamilyGenerator(FamilyGenerator):
    """Axial 轨道族生成器。"""

    @classmethod
    def add_family_args(cls, parser) -> None:
        """声明 Axial 族特有的 CLI 参数。"""
        parser.add_argument(
            "--libration-point",
            type=str,
            default="L1",
            choices=["L1", "L2", "L3", "L4", "L5"],
            help="平动点选择，默认 L1",
        )
        parser.add_argument(
            "--method",
            type=str,
            default="natural",
            choices=["natural", "pseudo_arclength"],
            help="延拓方法，默认 natural",
        )
        parser.add_argument(
            "--amplitude-z-min",
            type=float,
            default=0.01,
            help="延拓 z 方向振幅下限（无量纲）",
        )
        parser.add_argument(
            "--amplitude-z-max",
            type=float,
            default=0.5,
            help="延拓 z 方向振幅上限（无量纲）",
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
        """构造 Axial 种子轨道（尚未实现）。"""
        raise NotImplementedError("Axial 种子轨道构造尚未实现")

    def _setup_corrector(self, args):
        """配置 Axial 微分修正器（尚未实现）。"""
        raise NotImplementedError("Axial 微分修正器配置尚未实现")

    def _run_continuation(self, corrector, seed_orbit, args):
        """执行 Axial 延拓生成轨道族（尚未实现）。"""
        raise NotImplementedError("Axial 延拓生成尚未实现")


def main() -> None:
    """Axial 轨道族生成入口。"""
    config = FamilyGeneratorConfig(
        family_type="axial",
        output_subdir="axial",
        summary_title="  Earth-Moon Axial 轨道族：配置、统计与代表性轨道",
        summary_columns=[],
        n_milestones=5,
    )
    gen = AxialFamilyGenerator(config)
    args = gen.parse_args()
    setup_logging(args.log_level)
    gen.run(args)


if __name__ == "__main__":
    inject_debug_args(
        sys.argv,
        [
            "--libration-point", "L1",
            "--method", "natural",
            "--amplitude-z-min", "0.01",
            "--amplitude-z-max", "0.5",
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
    module='axial',
    name='generate_axial_family',
    description='生成轨道族',
    script_path='tod/generates/cr3bp/axial/generate_axial_family.py',
    output_dir='output/axial',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L1', choices=('L1', 'L2', 'L3'), help='平动点选择（L1/L2/L3），默认 L1。'),
        CliParam('--method', '延拓方法', 'select', 'natural', choices=('natural', 'pseudo_arclength'), help='延拓方法（natural/pseudo_arclength），默认 natural。'),
        CliParam('--amplitude-z-min', 'z 方向最小振幅', 'float', '0.01', help='延拓 z 方向振幅下限（无量纲），默认 0.01。'),
        CliParam('--amplitude-z-max', 'z 方向最大振幅', 'float', '0.5', help='延拓 z 方向振幅上限（无量纲），默认 0.5。'),
        CliParam('--step-size', '步长', 'float', '0.01', help='延拓步长（无量纲），默认 0.01。'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50', help='目标生成轨道数，默认 50。'),
    ],
)
