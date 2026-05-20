"""Params definition for generate_rro_family.py."""

from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module="ro",
    name="generate_rro_family",
    description="生成 RRO 反射共振轨道族（从 3:2 RO 分岔）",
    script_path="tod/generates/cr3bp/ro/generate_rro_family.py",
    output_dir="output/ro",
    group_label="生成",
    cli_params=[
        CliParam(
            "--ro-file",
            "RO 文件",
            "str",
            help="3:2 RO 轨道 JSON 文件路径",
            file_category="ro",
        ),
        CliParam(
            "--target-x0",
            "目标 x0",
            "float",
            "-1.1318",
            "目标 x0 分岔点",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--z-max",
            "最大 z 幅值",
            "float",
            "0.5",
            "最大 z 幅值",
            unit_group="distance",
            default_unit="DU",
        ),
        CliParam(
            "--step-size",
            "延拓步长",
            "float",
            "0.01",
            "延拓步长",
        ),
    ],
)
