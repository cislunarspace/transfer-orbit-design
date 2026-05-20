from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "inspection",
    "plot_interactive_orbit_inspector",
    "交互式轨道检查器（逐步遍历轨道族）",
    "tod/plot/inspection/plot_interactive_orbit_inspector.py",
    group_label="交互式检查",
    cli_params=[
        CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径"),
        CliParam("--plane", "投影平面", "str", "xy", "投影平面: xy, xz, yz"),
        CliParam("--show-3d", "显示 3D 视图", "bool", help="同时显示 3D 视图"),
        CliParam("--fig-size", "图形大小", "str", "10 8", "图形大小 (宽 高)"),
    ],
)
