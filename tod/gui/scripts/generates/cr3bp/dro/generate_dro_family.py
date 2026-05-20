"""Params definition for generate_dro_family.py."""

from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module="dro",
    name="generate_dro_family",
    description="生成 DRO 轨道族（微分修正 + 自然延拓）",
    script_path="tod/generates/cr3bp/dro/generate_dro_family.py",
    output_dir="output/dro",
    group_label="生成",
    cli_params=[
        CliParam(
            "--x0",
            "初始 x 坐标",
            "float",
            "0.79188556619742",
            "种子轨道初始 x 坐标（无量纲）",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--vy0",
            "初始 vy 速度",
            "float",
            "0.53682",
            "种子轨道初始 vy 速度（无量纲）",
            unit_group="velocity",
        ),
        CliParam(
            "--period",
            "初始周期",
            "float",
            "3.472526005624708",
            "初始周期猜测（无量纲）",
            unit_group="time",
            default_unit="days",
        ),
        CliParam(
            "--param-min",
            "延拓下限",
            "float",
            "0.141886",
            "延拓参数范围下限（x0 最小值）",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--param-max",
            "延拓上限",
            "float",
            "0.9",
            "延拓参数范围上限（x0 最大值）",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--step-size",
            "延拓步长",
            "float",
            "0.005",
            "延拓步长",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--verbose",
            "详细输出",
            "bool",
            help="勾选后显示详细延拓过程（每步迭代、收敛进度等）",
        ),
    ],
)
