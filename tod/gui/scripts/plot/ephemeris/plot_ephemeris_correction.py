from tod.gui.script_registry import CliParam, EnvParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    "ephemeris",
    "plot_ephemeris_correction",
    "绘制 DRO 星历修正前后对比图",
    "tod/plot/ephemeris/plot_ephemeris_correction.py",
    output_dir="output/ephemeris",
    needs_spice=True,
    group_label="绘图",
    cli_params=[
        CliParam("--dro-file", "DRO 文件", "str", help="DRO 轨道 JSON 文件路径", file_category="dro"),
        CliParam("--ephemeris-file", "星历修正文件", "str", help="星历修正 JSON 文件路径", file_category="ephemeris"),
    ],
)
