from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "transfer",
    "plot_optimize_result_leo_to_dro",
    "绘制 LEO→DRO NLP 优化结果",
    "tod/plot/transfer/leo_to_dro/plot_optimize_result_leo_to_dro.py",
    output_dir="output/transfer",
    group_label="LEO→DRO",
    cli_params=[
        CliParam("--file", "优化结果文件", "str", help="优化结果 JSON 文件路径", file_category="transfer"),
        CliParam("--orbit", "转移轨道图（3D）", "bool", help="重新积分并绘制转移轨道 3D 示意图"),
        CliParam("--time-dv", "转移时间-Δv 散点图", "bool", help="转移时间 vs Δv 散点图"),
        CliParam("--interactive", "逐条浏览模式", "bool", help="按转移时间排序逐条浏览"),
        CliParam("--idx", "选中轨道（--orbit 模式）", "str", "best:5", "all / best / best:N / random / 序号"),
        CliParam("--max-pos-err", "最大位置误差 (km)", "float", "100.0", "过滤：位置误差超过此值的结果不显示"),
        CliParam("--save", "保存图片路径", "str", help="不填则弹窗显示"),
        CliParam("--max-points", "最大绘制轨道数", "int", "200", "--idx all 时最多绘制条数", advanced=True),
        CliParam("--seed", "随机种子", "int", "42", "子采样随机种子", advanced=True),
        CliParam("--dpi", "图片 DPI", "int", "150", "保存图片的分辨率", advanced=True),
    ],
)
