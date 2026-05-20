"""Params definition for generate_32_ro_family.py."""

from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module="ro",
    name="generate_32_ro_family",
    description="生成 3:2 共振轨道族（差分修正 + 自然延拓）",
    script_path="tod/generates/cr3bp/ro/generate_32_ro_family.py",
    output_dir="output/ro",
    group_label="生成",
    cli_params=[
        CliParam(
            "--x0",
            "初始 x 坐标",
            "float",
            "-1.1453",
            "初始 x 坐标（无量纲）",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--vy0",
            "初始 vy 速度",
            "float",
            "0.4633",
            "初始 y 方向速度（无量纲）",
            unit_group="velocity",
        ),
        CliParam(
            "--period",
            "轨道周期",
            "float",
            str(round(54.64 / 0.3482, 6)),
            "轨道周期（无量纲）",
            unit_group="time",
            default_unit="days",
        ),
        CliParam(
            "--param-min",
            "延拓下限",
            "float",
            "-1.2",
            "延拓参数范围下限",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--param-max",
            "延拓上限",
            "float",
            "-0.8",
            "延拓参数范围上限",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--step-size",
            "延拓步长",
            "float",
            "0.005",
            "延拓步长",
        ),
    ],
)
