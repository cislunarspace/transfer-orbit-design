"""plot_search_results_geo_to_dro 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_search_results_geo_to_dro',
    description='绘制搜索结果',
    script_path='tod/plot/transfer/geo_to_dro/plot_search_results_geo_to_dro.py',
    output_dir='output/transfer',
    group_label='GEO→DRO',
    cli_params=[
        CliParam('--file', '搜索结果文件', 'str', '', help='搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--auto-latest', '按 mtime 选最新搜索结果（显式 opt-in）', 'bool', '', help='显式 opt-in：按 mtime 选最新 search_geo_dro_*.json；与 --file 互斥。', advanced=True),
        CliParam('--dro-file', 'DRO 轨道文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--auto-latest-dro', '按 mtime 选最新 DRO（显式 opt-in）', 'bool', '', help='显式 opt-in：按 mtime 选最新 dro_<digits>.json；与 --dro-file 互斥。', advanced=True),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图，勾选后启用。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='绘制转移时间 vs Δv 散点图，勾选后启用。'),
        CliParam('--interactive', '逐条浏览模式', 'bool', '', help='按转移时间排序逐条浏览，勾选后启用。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', 'best:10', help='all / best / best:N / random / 序号，默认 best:10。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大散点数', 'int', '50000', help='散点子采样上限，避免过多点导致卡顿，默认 50000。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子，默认 0。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率，默认 150。', advanced=True),
    ],
)
