"""generate_ro_family RO（共振轨道）族生成脚本。

本模块在地月 CR3BP 中通过差分修正 + 自然延拓生成 3:1 或 3:2 共振轨道族。
通过 ``--ratio`` 参数区分具体共振比例。

RO = Resonant Orbit（共振轨道），3:1 表示轨道周期是月球绕地球周期的 3 倍，
3:2 表示 1.5 倍。

本脚本通过 ``FamilyGenerator`` 基类实现，族特有逻辑在子类钩子中声明，
共享流程由基类处理。

运行示例:
    .. code-block:: bash

       uv run python tod/generates/cr3bp/ro/generate_ro_family.py --help
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

# 各共振比的默认种子初值（x0, vy0, period）
_RATIO_DEFAULTS: dict[str, dict[str, float]] = {
    "3:1": {"x0": -0.8805, "vy0": 0.3921, "period": 27.32},
    "3:2": {"x0": -1.1453, "vy0": 0.4633, "period": 54.64},
}


class RoFamilyGenerator(FamilyGenerator):
    """RO（共振轨道）族生成器。"""

    @classmethod
    def add_family_args(cls, parser) -> None:
        """声明 RO 族特有的 CLI 参数。"""
        parser.add_argument(
            "--ratio",
            type=str,
            default="3:1",
            choices=["3:1", "3:2"],
            help="共振比例，默认 3:1",
        )
        parser.add_argument(
            "--x0",
            type=float,
            default=None,
            help="初始 x 坐标（无量纲），默认值由 --ratio 决定",
        )
        parser.add_argument(
            "--vy0",
            type=float,
            default=None,
            help="初始 y 方向速度（无量纲），默认值由 --ratio 决定",
        )
        parser.add_argument(
            "--period",
            type=float,
            default=None,
            help="轨道周期（天），默认值由 --ratio 决定",
        )
        parser.add_argument(
            "--param-min",
            type=float,
            default=None,
            help="延拓参数范围下限（x0），默认值由 --ratio 决定",
        )
        parser.add_argument(
            "--param-max",
            type=float,
            default=None,
            help="延拓参数范围上限（x0），默认值由 --ratio 决定",
        )
        parser.add_argument(
            "--step-size",
            type=float,
            default=None,
            help="延拓步长，默认值由 --ratio 决定",
        )

    def _get_seed_orbit(self, args):
        """构造 RO 种子轨道。"""
        from e2m2e.core import Orbit
        from tod.commons.constants import TU

        defaults = _RATIO_DEFAULTS[args.ratio]
        x0 = args.x0 if args.x0 is not None else defaults["x0"]
        vy0 = args.vy0 if args.vy0 is not None else defaults["vy0"]
        period_days = args.period if args.period is not None else defaults["period"]
        period = period_days / TU

        initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
        seed_orbit = Orbit(states=[initial_state], times=[0])
        seed_orbit.period = period
        return seed_orbit

    def _setup_corrector(self, args):
        """配置 2D 对称微分修正器。"""
        from e2m2e.algorithms import DifferentialCorrection

        defaults = _RATIO_DEFAULTS[args.ratio]
        x0 = args.x0 if args.x0 is not None else defaults["x0"]
        corrector = DifferentialCorrection(dynamic=self.dynamics)
        corrector.setup_2D_symmetric_x_fixed_x0(x0=x0)
        return corrector

    def _run_continuation(self, corrector, seed_orbit, args):
        """执行自然延拓生成轨道族。"""
        from e2m2e.algorithms import Continuation

        defaults = _RATIO_DEFAULTS[args.ratio]
        param_min = args.param_min if args.param_min is not None else defaults["x0"] - 0.01
        param_max = args.param_max if args.param_max is not None else defaults["x0"] + 0.05
        step_size = args.step_size if args.step_size is not None else 0.001

        continuator = Continuation(corrector=corrector)
        return continuator.natural_continuation(
            seed_orbit=seed_orbit,
            param_range=(param_min, param_max),
            step_size=step_size,
        )

    def _build_json_filename(self, args, ts):
        """构建 JSON 文件名：ro_{ratio}_family_{params}_{ts}。"""
        defaults = _RATIO_DEFAULTS[args.ratio]
        param_min = args.param_min if args.param_min is not None else defaults["x0"] - 0.01
        param_max = args.param_max if args.param_max is not None else defaults["x0"] + 0.05
        step_size = args.step_size if args.step_size is not None else 0.001
        ratio_tag = args.ratio.replace(":", "")
        return f"ro_{ratio_tag}_family_{param_min}-{param_max}-{step_size}_{ts}"


def main() -> None:
    """RO 轨道族生成入口。"""
    config = FamilyGeneratorConfig(
        family_type="ro",
        output_subdir="ro",
        summary_title="  Earth-Moon RO 轨道族：配置、统计与代表性轨道",
        summary_columns=[],
        n_milestones=5,
    )
    gen = RoFamilyGenerator(config)
    args = gen.parse_args()
    setup_logging(args.log_level)
    gen.run(args)


if __name__ == "__main__":
    inject_debug_args(
        sys.argv,
        [
            "--ratio", "3:1",
            "--param-min", "-0.8905",
            "--param-max", "-0.8305",
            "--step-size", "0.001",
        ],
    )
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ro',
    name='generate_ro_family',
    description='生成共振轨道族',
    script_path='tod/generates/cr3bp/ro/generate_ro_family.py',
    output_dir='output/ro',
    group_label='生成',
    cli_params=[
        CliParam('--ratio', '共振比例', 'select', '3:1', choices=('3:1', '3:2'), help='共振比例（3:1/3:2），默认 3:1。'),
        CliParam('--x0', '初始 x 坐标', 'float', '', help='初始 x 坐标（无量纲），默认值由共振比例决定。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '', help='初始 y 方向速度（无量纲），默认值由共振比例决定。', unit_group='velocity'),
        CliParam('--period', '轨道周期', 'float', '', help='轨道周期（天），默认值由共振比例决定。', unit_group='time', default_unit='days'),
        CliParam('--param-min', '延拓下限', 'float', '', help='延拓参数范围下限（x0），默认值由共振比例决定。', unit_group='distance', default_unit='DU'),
        CliParam('--param-max', '延拓上限', 'float', '', help='延拓参数范围上限（x0），默认值由共振比例决定。', unit_group='distance', default_unit='DU'),
        CliParam('--step-size', '延拓步长', 'float', '', help='延拓步长，默认值由共振比例决定。'),
    ],
)
