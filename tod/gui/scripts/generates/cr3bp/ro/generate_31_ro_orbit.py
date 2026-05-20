"""Params definition for generate_31_ro_orbit.py."""

from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module="ro",
    name="generate_31_ro_orbit",
    description="生成 3:1 RO 轨道（固定周期微分校正）",
    script_path="tod/generates/cr3bp/ro/generate_31_ro_orbit.py",
    output_dir="output/ro",
    group_label="生成",
    cli_params=[
        CliParam(
            "--x0",
            "初始 x 坐标",
            "float",
            "-0.8805",
            "初始 x 坐标（无量纲）",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--vy0",
            "初始 vy 速度",
            "float",
            "0.3921",
            "初始 y 方向速度（无量纲）",
            unit_group="velocity",
        ),
        CliParam(
            "--period",
            "目标周期",
            "float",
            str(round(27.32 / 0.3482, 6)),
            "目标周期（无量纲）",
            unit_group="time",
            default_unit="days",
        ),
    ],
)
