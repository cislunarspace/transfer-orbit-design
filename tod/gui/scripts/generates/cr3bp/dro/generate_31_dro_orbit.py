"""Params definition for generate_31_dro_orbit.py."""

from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module="dro",
    name="generate_31_dro_orbit",
    description="生成 3:1 DRO 轨道（固定周期微分校正）",
    script_path="tod/generates/cr3bp/dro/generate_31_dro_orbit.py",
    output_dir="output/dro",
    group_label="生成",
    cli_params=[
        CliParam(
            "--x0",
            "初始 x 坐标",
            "float",
            "1.1202",
            "初始 x 坐标（无量纲）",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--vy0",
            "初始 vy 速度",
            "float",
            "-0.4618",
            "初始 y 方向速度（无量纲）",
            unit_group="velocity",
        ),
        CliParam(
            "--period",
            "目标周期",
            "float",
            "2.095",
            "目标周期（无量纲）",
            unit_group="time",
            default_unit="days",
        ),
        CliParam(
            "--verbose",
            "详细输出",
            "bool",
            help="勾选后显示详细迭代过程（残差、收敛进度等）",
        ),
    ],
)
