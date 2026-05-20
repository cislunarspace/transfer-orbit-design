"""Params for optimize_dro_to_geo.py."""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "transfer",
    "optimize_dro_to_geo",
    "DRO→GEO 转移 NLP 优化",
    "tod/transfers/dro_to_geo/optimize_dro_to_geo.py",
    output_dir="output/transfer",
    group_label="DRO→GEO",
    cli_params=[
        CliParam("--search-file", "搜索结果文件", "str", help="网格搜索结果 JSON 文件路径", file_category="transfer"),
        CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
        CliParam("--alpha-min", "alpha 下界", "float", "0.5", "alpha 搜索下界"),
        CliParam("--alpha-max", "alpha 上界", "float", "2.5", "alpha 搜索上界"),
        CliParam(
            "--t-min",
            "转移时间下界",
            "float",
            "0.5",
            "转移时间下界（无量纲）",
            unit_group="time",
            default_unit="days",
        ),
        CliParam(
            "--t-max",
            "转移时间上界",
            "float",
            "30.0",
            "转移时间上界（无量纲）",
            unit_group="time",
            default_unit="days",
        ),
        CliParam("--nlp-maxiter", "NLP 最大迭代", "int", "100", "NLP 最大迭代次数"),
        CliParam("--nlp-ftol", "NLP 函数容差", "float", "1e-8", "NLP 函数容差"),
        CliParam("--top-k", "前 K 个可行解", "int", help="取前 K 个可行解优化"),
        CliParam("--max-cases", "最大案例数", "int", help="最大优化案例数"),
        CliParam("--n-workers", "并行 worker 数", "int", help="并行 worker 数"),
    ],
)
