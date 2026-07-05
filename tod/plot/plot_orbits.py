# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""统一轨道族绘图入口。

自动检测文件类型（家族 / 单条轨道）和轨道族类型（Halo / DRO / RO 子类型），
根据检测结果应用对应的默认绘图配置，同时支持 CLI 参数覆盖。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.plot_orbits --help
       uv run python -m tod.plot.plot_orbits --json-file output/halo/family.json --view-2d
       uv run python -m tod.plot.plot_orbits --json-file '[{"path": "a.json"}, {"path": "b.json"}]' --view-3d --plane xz
"""

from __future__ import annotations

import argparse
import dataclasses
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
    _parse_json_file_arg,
)
from tod.plot.orbit_config_registry import FALLBACK_CONFIG, detect_orbit_config

logger = logging.getLogger(__name__)


def build_argparser() -> argparse.ArgumentParser:
    """创建统一的轨道族绘图参数解析器。"""
    parser = argparse.ArgumentParser(
        description="统一轨道族绘图（DRO / RO / Halo）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--json-file",
        type=str,
        default=None,
        help="轨道 JSON 文件路径。支持两种格式：\n"
        "1. 单文件：直接传入文件路径\n"
        "2. 多文件：传入 JSON 字符串数组，如 '[{\"path\": \"a.json\", \"start\": 0, \"end\": 10, \"step\": 1}]'",
    )
    parser.add_argument("--start", type=int, default=-1, help="起始轨道索引，-1 表示从第一条（仅单文件模式有效）")
    parser.add_argument("--end", type=int, default=-1, help="结束轨道索引（含），-1 表示到最后一条（仅单文件模式有效）")
    parser.add_argument("--plot-global-2d", "--view-2d", dest="plot_global_2d", action="store_true", help="绘制全局 2D 视图")
    parser.add_argument("--plot-global-3d", "--view-3d", dest="plot_global_3d", action="store_true", help="绘制全局 3D 视图")
    parser.add_argument(
        "--plot-jacobi-stability", "--jacobi-period-stability", dest="plot_jacobi_stability", action="store_true",
        help="绘制 Jacobi 常数与周期、稳定性的关系曲线",
    )
    parser.add_argument(
        "--plane", type=str, default=None,
        help="覆盖自动检测的投影平面（xy / xz / yz），留空表示自动检测",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="覆盖默认输出目录（默认: output/plot/）",
    )
    parser.add_argument(
        "--plot-center", type=str, default="moon", choices=["moon", "earth", "emb"],
        help="3D 视图的绘图中心",
    )
    parser.add_argument("--plot-elev", type=float, default=20.0, help="3D 视图仰角（度）")
    parser.add_argument("--plot-azim", type=float, default=-60.0, help="3D 视图方位角（度）")
    parser.add_argument("--step", type=int, default=None, help="绘制轨道的间隔步长，1 表示绘制全部（仅单文件模式有效）")
    parser.add_argument("--no-show", action="store_true", help="只保存图片，不弹窗显示")
    return parser


def _detect_first_file(args: argparse.Namespace) -> Path | None:
    """从参数中提取第一个文件路径用于类型检测。"""
    single_path, multi_configs = _parse_json_file_arg(args.json_file)
    if single_path:
        return single_path
    if multi_configs:
        return Path(multi_configs[0].path)
    return None


def _resolve_config(args: argparse.Namespace) -> FamilyPlotConfig:
    """合并自动检测配置与 CLI 覆盖。"""
    first_file = _detect_first_file(args)
    if first_file and first_file.exists():
        base_config = detect_orbit_config(first_file)
    else:
        base_config = FALLBACK_CONFIG

    overrides: dict = {}
    if args.plane:
        valid_planes = {"xy", "xz", "yz"}
        if args.plane not in valid_planes:
            raise ValueError(f"--plane 值无效: {args.plane!r}，可选: {valid_planes}")
        overrides["plane"] = args.plane

    if args.output_dir:
        overrides["output_subdir"] = args.output_dir

    return dataclasses.replace(base_config, **overrides)


def main(
    plot1: bool | None = None,
    plot2: bool | None = None,
    plot3: bool | None = None,
) -> None:
    """执行脚本主流程。

    Args:
        plot1: 覆盖 2D 视图开关。
        plot2: 覆盖 3D 视图开关。
        plot3: 覆盖 Jacobi-稳定性图开关。

    Returns:
        None。
    """
    parser = build_argparser()
    args = parser.parse_args()

    if plot1 is not None:
        args.plot_global_2d = plot1
    if plot2 is not None:
        args.plot_global_3d = plot2
    if plot3 is not None:
        args.plot_jacobi_stability = plot3

    config = _resolve_config(args)
    logger.info(f"检测到轨道类型: {config.display_name}, 投影平面: {config.plane}")

    FamilyPlotOrchestrator(config, args).run()


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, MultiCliParam, PerFileField, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='plot',
    name='plot_orbits',
    description='绘制轨道族 / 单条轨道（DRO / RO / Halo）',
    script_path='tod/plot/plot_orbits.py',
    output_dir='output/plot',
    group_label='绘图',
    multi_cli_params=[
        MultiCliParam(
            flag='--json-file',
            label='轨道文件',
            file_category='orbit',
            name_pattern='*.json',
            help='支持多文件：点击"添加文件"选择多个 JSON 文件（家族或单条轨道），'
                 '每个文件可在表格中独立配置绘制范围',
            per_file_fields=[
                PerFileField(
                    key='start',
                    label='起始索引',
                    field_type='int',
                    default='-1',
                    help='起始轨道索引，-1 表示从第一条',
                ),
                PerFileField(
                    key='end',
                    label='结束索引',
                    field_type='int',
                    default='-1',
                    help='结束轨道索引（含），-1 表示到最后一条',
                ),
                PerFileField(
                    key='step',
                    label='绘制间隔',
                    field_type='int',
                    default='1',
                    help='每隔 N 条轨道绘制 1 条，1 表示绘制全部',
                    min_value=1,
                ),
            ],
        ),
    ],
    cli_params=[
        CliParam('--plane', '投影平面', 'str', '', help='覆盖自动检测的投影平面（留空=自动）', advanced=True),
        CliParam('--view-2d', '2D 视图', 'bool', '', help='绘制轨道在选定平面的 2D 视图。'),
        CliParam('--view-3d', '3D 视图', 'bool', '', help='绘制轨道的 3D 示意图。'),
        CliParam('--plot-center', '绘图中心', 'str', 'moon', help='3D 视图的绘图中心', choices=('月球', '地球', '地月质心'), choice_values={'月球': 'moon', '地球': 'earth', '地月质心': 'emb'}),
        CliParam('--plot-elev', '仰角（度）', 'float', '20', help='3D 视图仰角（度）'),
        CliParam('--plot-azim', '方位角（度）', 'float', '-60', help='3D 视图方位角（度）'),
        CliParam('--jacobi-period-stability', 'Jacobi-周期-稳定性图', 'bool', '', help='绘制 Jacobi 常数-周期-稳定性联合图。'),
    ],
)
