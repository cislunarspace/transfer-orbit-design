from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "dro",
    "plot_dro_family",
    "绘制 DRO 轨道族",
    "tod/plot/dro/plot_dro_family.py",
    output_dir="output/dro",
    group_label="绘图",
    cli_params=[
        CliParam("--json-file", "轨道族文件", "str", help="轨道族 JSON 文件路径", file_category="dro", name_pattern="*_family_*.json"),
        CliParam("--plot-global-2d", "全局 2D 视图（XY 平面）", "bool", help="绘制 DRO 轨道族在 XY 平面的全局 2D 视图"),
        CliParam("--plot-global-3d", "全局 3D 视图", "bool", help="绘制 DRO 轨道族在 3D 空间的全局视图"),
        CliParam("--plot-center", "绘图中心", "str", "月球",
                 "3D 视图的绘图中心",
                 choices=("月球", "地球", "地月质心"),
                 choice_values={"月球": "moon", "地球": "earth", "地月质心": "emb"},
                 hidden_when="--plot-global-3d"),
        CliParam("--plot-elev", "仰角（度）", "float", "20", "3D 视图仰角（度）",
                 hidden_when="--plot-global-3d"),
        CliParam("--plot-azim", "方位角（度）", "float", "-60", "3D 视图方位角（度）",
                 hidden_when="--plot-global-3d"),
        CliParam("--plot-jacobi-stability", "Jacobi 常数-周期-稳定性关系图", "bool", help="绘制 Jacobi 常数与轨道周期、稳定性的关系曲线"),
    ],
)
