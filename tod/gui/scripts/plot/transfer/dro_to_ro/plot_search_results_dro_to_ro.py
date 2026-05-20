from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "transfer",
    "plot_search_results_dro_to_ro",
    "绘制 DRO→RO 网格搜索结果",
    "tod/plot/transfer/dro_to_ro/plot_search_results_dro_to_ro.py",
    output_dir="output/transfer",
    group_label="DRO→RO",
    cli_params=[
        CliParam("--file", "搜索结果文件", "str", help="搜索结果 JSON 文件路径", file_category="transfer"),
        CliParam("--orbit", "转移轨道图（3D）", "bool", help="重新积分并绘制转移轨道 3D 示意图"),
        CliParam("--time-dv", "转移时间-Δv 散点图", "bool", help="绘制转移时间 vs Δv 散点图"),
        CliParam("--idx", "选中轨道（--orbit 模式）", "str", "0", "整数索引 / best / best:N / random / all"),
        CliParam("--save", "保存图片路径", "str", help="不填则弹窗显示"),
        CliParam("--max-points", "最大散点数", "int", "50000", "散点子采样上限，避免过多点导致卡顿", advanced=True),
        CliParam("--seed", "随机种子", "int", "0", "子采样随机种子", advanced=True),
        CliParam("--dpi", "图片 DPI", "int", "150", "保存图片的分辨率", advanced=True),
        CliParam("--n-workers", "并行 worker 数", "int", help="并行积分进程数，仅 --orbit 模式", advanced=True),
    ],
)
