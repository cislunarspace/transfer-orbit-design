from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "ro",
    "plot_31_ro_family",
    "绘制 3:1 共振轨道族",
    "tod/plot/ro/plot_31_ro_family.py",
    output_dir="output/ro",
    group_label="绘图",
    cli_params=[
        CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="ro", name_pattern="*_family_*.json"),
        CliParam("--start", "起始索引", "int", "-1", "起始轨道索引，-1 表示从第一条"),
        CliParam("--end", "结束索引", "int", "-1", "结束轨道索引（含），-1 表示到最后一条"),
    ],
)
