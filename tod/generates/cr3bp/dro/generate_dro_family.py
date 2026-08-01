# pyright: reportAttributeAccessIssue=false
"""generate_dro_family 轨道生成脚本。

本模块在地月 CR3BP 中构造 DRO 种子轨道，调用 e2m2e 的微分修正和自然延拓算法
生成 DRO 轨道族。输入为命令行给出的初始状态、周期猜测和延拓配置；
输出为 output/dro/ 下的 JSON/CSV 文件。

本脚本通过 ``FamilyGenerator`` 基类实现，族特有逻辑在子类钩子中声明，
共享流程（系统初始化、保存、CSV 导出、摘要表打印）由基类处理。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.dro.generate_dro_family --help
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import e2m2e
from e2m2e.core import Orbit, OrbitFamily

from tod.generates.cr3bp._family_pipeline import (
    FamilyGenerator,
    FamilyGeneratorConfig,
    ProgressTracker,
    inject_debug_args,
    jacobi_constant,
)

logger = logging.getLogger(__name__)

class DroFamilyGenerator(FamilyGenerator):
    """DRO 轨道族生成器。

    继承 ``FamilyGenerator`` 基类，实现 DRO 特有的种子构造、
    微分修正器配置和自然延拓逻辑。
    """

    @classmethod
    def add_family_args(cls, parser) -> None:
        """声明 DRO 族特有的 CLI 参数。"""
        parser.add_argument(
            "--x0",
            type=float,
            default=0.79188556619742,
            help="种子轨道初始 x 坐标（无量纲）",
        )
        parser.add_argument(
            "--vy0",
            type=float,
            default=0.53682,
            help="种子轨道初始 vy 速度（无量纲）",
        )
        parser.add_argument(
            "--period",
            type=float,
            default=3.472526005624708,
            help="初始周期猜测（无量纲）",
        )
        parser.add_argument(
            "--param-min",
            type=float,
            default=0.141886,
            help="延拓参数范围下限（x0 最小值）",
        )
        parser.add_argument(
            "--param-max",
            type=float,
            default=0.9,
            help="延拓参数范围上限（x0 最大值）",
        )
        parser.add_argument(
            "--step-size",
            type=float,
            default=0.005,
            help="延拓步长",
        )

    # ------------------------------------------------------------------
    # 钩子实现
    # ------------------------------------------------------------------

    def _get_seed_orbit(self, args: Any) -> Orbit:
        """从 CLI 参数构造 DRO 种子轨道。

        DRO 特征：平面内运动（y=z=0），关于 x 轴对称（vx=vz=0）。
        """
        x0 = args.x0
        vy0 = args.vy0
        initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
        seed_state = Orbit(states=[initial_state], times=[0])
        seed_state.period = args.period
        return seed_state

    def _setup_corrector(self, args: Any) -> Any:
        """创建并配置 DRO 微分修正器。

        使用 ``setup_2D_symmetric_x_fixed_x0`` 固定 x0 的 2D 对称修正。
        """
        corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=self.dynamics)
        corrector.setup_2D_symmetric_x_fixed_x0(x0=args.x0)
        return corrector

    def _correct_seed_orbit(
        self, corrector: Any, seed_orbit: Orbit, args: Any
    ) -> Orbit | None:
        """对 DRO 种子轨道执行微分修正。"""
        print("[1/3] 开始种子轨道差分修正...")
        corrected = super()._correct_seed_orbit(corrector, seed_orbit, args)
        if corrected is not None:
            print(f"[1/3] 完成，周期 = {corrected.period:.4f} TU")
        return corrected

    def _run_continuation(
        self, corrector: Any, seed_orbit: Orbit, args: Any
    ) -> OrbitFamily:
        """执行 DRO 自然延拓生成轨道族。"""
        continuation = e2m2e.algorithms.Continuation(corrector=corrector)
        param_min = args.param_min
        param_max = args.param_max
        step_size = args.step_size

        # 估算总步数（正向 + 反向）
        n_forward = int((param_max - param_min) / step_size) + 1
        n_backward = int((param_max - param_min) / step_size) + 1
        est_total = n_forward + n_backward
        print(
            f"[2/3] 开始自然延拓 "
            f"(x0 ∈ [{param_min:.3f}, {param_max:.3f}], 步长 = {step_size}, 预计约 {est_total} 步)..."
        )

        tracker = self._make_progress_tracker(est_total)
        if tracker is not None:
            tracker.start()

        try:
            family_result = continuation.natural_continuation(
                seed_orbit=seed_orbit,
                param_range=(param_min, param_max),
                step_size=step_size,
                verbose=args.verbose,
            )
        finally:
            if tracker is not None:
                tracker.stop()

        orbits = family_result.orbits
        print(f"[2/3] 延拓完成，共 {len(orbits)} 条轨道")
        return family_result

    def _make_progress_tracker(self, total: int) -> ProgressTracker | None:
        """DRO 启用进度跟踪。"""
        return ProgressTracker(total)

    def _build_json_filename(self, args: Any, ts: int) -> str:
        """DRO 文件名包含延拓参数范围，匹配原始输出格式。"""
        return (
            f"dro_31_family_{args.param_min}-{args.param_max}-{args.step_size}_{ts}"
        )

    def _build_csv_filename_parts(self, args: Any, ts: int) -> list[str]:
        """DRO CSV 文件名前缀片段（不含 ts），匹配原始输出格式。

        原始格式：dro_31_family_<param-min>-<param-max>-<step-size>_<ts>.csv
        基类 ``run()`` 会在最后追加 ts。
        """
        return [f"dro_31_family_{args.param_min}-{args.param_max}-{args.step_size}"]

# ------------------------------------------------------------------------------
# 配置与入口
# ------------------------------------------------------------------------------

def _csv_format_row(orbit: Orbit, index: int, is_milestone: bool) -> dict[str, Any]:
    """格式化单条 DRO 轨道的 CSV 行。"""
    assert orbit.period is not None and orbit.periodicity_error is not None
    s = orbit.states[0]
    return {
        "continuation_step": orbit.metadata.get("continuation_step", ""),
        "x0": float(s[0]),
        "y0": float(s[1]),
        "z0": float(s[2]),
        "vx0": float(s[3]),
        "vy0": float(s[4]),
        "vz0": float(s[5]),
        "period": float(orbit.period),
        "x_amp": float(orbit.amplitudes["x"]),
        "y_amp": float(orbit.amplitudes["y"]),
        "z_amp": float(orbit.amplitudes.get("z", 0.0)),
        "c_jacobi": float(jacobi_constant(s)),
        "periodicity_error": float(orbit.periodicity_error),
        "is_milestone": is_milestone,
    }

def _summary_format_row(orbit: Orbit) -> list[str]:
    """格式化 DRO 摘要表的单行。"""
    assert orbit.period is not None
    s = orbit.states[0]
    return [
        f"{float(s[0]):10.6f}",
        f"{float(orbit.period):8.4f}",
        f"{float(orbit.amplitudes['x']):8.5f}",
        f"{float(orbit.amplitudes['y']):8.5f}",
        f"{float(jacobi_constant(s)):10.6f}",
    ]

def _summary_extra_info(args: Any) -> list[str]:
    """DRO 摘要表额外的配置行。"""
    return [
        f"  种子 x0      {args.x0:.8f}",
        f"  种子 vy0     {args.vy0:.5f}",
        f"  种子周期     {args.period:.10f}",
        f"  延拓参数     x0 in [{args.param_min:.6f}, {args.param_max:.6f}]",
        f"  延拓步长     {args.step_size}",
    ]

def main() -> None:
    """DRO 轨道族生成入口。"""
    config = FamilyGeneratorConfig(
        family_type="dro",
        output_subdir="dro",
        summary_title="  Earth-Moon DRO 轨道族：配置、统计与代表性轨道",
        summary_columns=["x0", "Period", "x-amp", "y-amp", "C_Jacobi"],
        csv_format_row=_csv_format_row,
        summary_format_row=_summary_format_row,
        n_milestones=5,
    )
    gen = DroFamilyGenerator(config)
    args = gen.parse_args()

    # 配置日志
    from tod.generates.cr3bp._family_pipeline import setup_logging

    setup_logging(args.log_level)

    # 摘要额外信息需要 args，通过包装器注入
    config.summary_extra_info = lambda: _summary_extra_info(args)

    gen.run(args)

if __name__ == "__main__":
    inject_debug_args(
        sys.argv,
        [
            "--x0", "0.79188556619742",
            "--vy0", "0.53682",
            "--period", "3.472526005624708",
            "--param-min", "0.141886",
            "--param-max", "0.9",
            "--step-size", "0.005",
        ],
    )
    main()

# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dro',
    name='generate_dro_family',
    description='生成轨道族',
    script_path='tod/generates/cr3bp/dro/generate_dro_family.py',
    output_dir='output/dro',
    group_label='生成',
    cli_params=[
        CliParam('--x0', '初始 x 坐标', 'float', '0.79188556619742', help='种子轨道初始 x 坐标（无量纲）。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '0.53682', help='种子轨道初始 vy 速度（无量纲）。', unit_group='velocity'),
        CliParam('--period', '初始周期', 'float', '3.472526005624708', help='初始周期猜测（无量纲）。', unit_group='time', default_unit='days'),
        CliParam('--param-min', '延拓下限', 'float', '0.141886', help='延拓参数范围下限（x0 最小值），单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--param-max', '延拓上限', 'float', '0.9', help='延拓参数范围上限（x0 最大值），单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--step-size', '延拓步长', 'float', '0.005', help='延拓步长，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--verbose', '详细输出', 'bool', '', help='显示详细延拓过程（每步迭代、收敛进度等）'),
    ],
)
