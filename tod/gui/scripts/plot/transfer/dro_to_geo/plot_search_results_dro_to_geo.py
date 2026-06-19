"""plot_search_results_dro_to_geo 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_search_results_dro_to_geo',
    description='绘制搜索结果',
    script_path='tod/plot/transfer/dro_to_geo/plot_search_results_dro_to_geo.py',
    output_dir='output/transfer',
    group_label='DRO→GEO',
    cli_params=[
        CliParam('--file', '搜索结果文件', 'str', '', help='搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径；不传则自动取 output/dro 下最新 dro_*.json。', file_category='dro', name_pattern='dro_[0-9]*.json'),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图，勾选后启用。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='绘制转移时间 vs Δv 散点图，勾选后启用。'),
        CliParam('--interactive', '逐条浏览模式', 'bool', '', help='按转移时间排序逐条浏览，勾选后启用。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', '0', help='整数索引 / best / best:N / random / all，默认 0。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大散点数', 'int', '50000', help='散点子采样上限，避免过多点导致卡顿，默认 50000。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子，默认 0。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率，默认 150。', advanced=True),
        CliParam('--n-workers', '并行 worker 数', 'int', '', help='并行积分进程数，仅 --orbit 模式。', advanced=True),
        CliParam('--figsize', '图尺寸(厘米)', 'str', '', help="图尺寸，格式 '宽,高'（厘米），如 '8.5,6'；不填使用默认。", advanced=True),
        CliParam('--color-by', '散点着色量', 'str', 'transfer_time', help='散点颜色映射量，默认转移时间。', choices=('transfer_time', 'total_dv'), choice_values={'转移时间': 'transfer_time', '总 Δv': 'total_dv'}),
        CliParam('--scatter-size', '散点大小', 'float', '10', help='散点大小，默认 10。', advanced=True),
        CliParam('--scatter-alpha', '散点透明度', 'float', '0.7', help='散点透明度，默认 0.7。', advanced=True),
        CliParam('--no-title', '隐藏标题', 'bool', '', help='勾选后不显示图标题，适合论文配图（图注在论文正文中撰写）。', advanced=True),
        CliParam('--caption', '图注', 'str', '', help='图片下方图注文字，如“Δv_departure 由切向速度比 α 计算得到”。', advanced=True),
    ],
)
