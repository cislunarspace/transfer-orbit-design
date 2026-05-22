from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "ro",
    "plot_aro_family",
    "绘制 ARO 轨道族",
    "tod/plot/ro/plot_aro_family.py",
    output_dir="output/ro",
    group_label="绘图",
    cli_params=[
        CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="ro", name_pattern="*_family_*.json"),
        CliParam("--start", "起始索引", "int", "-1", "起始轨道索引，-1 表示从第一条"),
        CliParam("--end", "结束索引", "int", "-1", "结束轨道索引（含），-1 表示到最后一条"),
        CliParam("--step", "绘制间隔", "int", "1", "每隔 N 条轨道绘制 1 条，1 表示绘制全部"),
        CliParam("--plot-global-2d", "全局 2D 视图（XY 平面）", "bool", help="绘制 ARO 轨道族在 XY 平面的 2D 视图"),
        CliParam("--plot-global-3d", "全局 3D 视图", "bool", help="绘制 ARO 轨道族的 3D 示意图"),
        CliParam("--plot-jacobi-stability", "Jacobi-周期-稳定性图", "bool", help="绘制 Jacobi 常数-周期-稳定性联合图"),
    ],
)
