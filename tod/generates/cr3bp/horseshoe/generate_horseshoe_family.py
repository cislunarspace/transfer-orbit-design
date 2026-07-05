"""generate_horseshoe_family Horseshoe轨道生成脚本。

本模块在地月 CR3BP 中延拓生成 Horseshoe 轨道族。通过改变振幅参数，
系统生成一系列跨越两个三角平动点的马蹄形轨道。

本脚本通过 ``FamilyGenerator`` 基类实现，族特有逻辑在子类钩子中声明，
共享流程由基类处理。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.horseshoe.generate_horseshoe_family --help
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


class HorseshoeFamilyGenerator(FamilyGenerator):
    """Horseshoe 轨道族生成器。"""

    @classmethod
    def add_family_args(cls, parser) -> None:
        """声明 Horseshoe 族特有的 CLI 参数。"""
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
        """构造 Horseshoe 种子轨道（尚未实现）。"""
        raise NotImplementedError("Horseshoe 种子轨道构造尚未实现")

    def _setup_corrector(self, args):
        """配置 Horseshoe 微分修正器（尚未实现）。"""
        raise NotImplementedError("Horseshoe 微分修正器配置尚未实现")

    def _run_continuation(self, corrector, seed_orbit, args):
        """执行 Horseshoe 延拓生成轨道族（尚未实现）。"""
        raise NotImplementedError("Horseshoe 延拓生成尚未实现")


def main() -> None:
    """Horseshoe 轨道族生成入口。"""
    config = FamilyGeneratorConfig(
        family_type="horseshoe",
        output_subdir="horseshoe",
        summary_title="  Earth-Moon Horseshoe 轨道族：配置、统计与代表性轨道",
        summary_columns=[],
        n_milestones=5,
    )
    gen = HorseshoeFamilyGenerator(config)
    args = gen.parse_args()
    setup_logging(args.log_level)
    gen.run(args)


if __name__ == "__main__":
    inject_debug_args(
        sys.argv,
        [
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

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='horseshoe',
    name='generate_horseshoe_family',
    description='生成轨道族',
    script_path='tod/generates/cr3bp/horseshoe/generate_horseshoe_family.py',
    output_dir='output/horseshoe',
    group_label='生成',
    cli_params=[
        CliParam('--amplitude-min', '最小振幅', 'float', '0.01', help='延拓振幅下限（无量纲）。'),
        CliParam('--amplitude-max', '最大振幅', 'float', '0.5', help='延拓振幅上限（无量纲）。'),
        CliParam('--step-size', '步长', 'float', '0.01', help='延拓步长（无量纲）。'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50', help='目标生成轨道数。'),
    ],
)
