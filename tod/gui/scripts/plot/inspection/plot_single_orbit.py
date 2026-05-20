from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "inspection",
    "plot_single_orbit",
    "绘制单条轨道（2D + 3D 视图）",
    "tod/plot/inspection/plot_single_orbit.py",
    group_label="单轨道绘图",
    cli_params=[
        CliParam("--json-file", "轨道文件", "str", help="轨道 JSON 文件路径"),
    ],
)
