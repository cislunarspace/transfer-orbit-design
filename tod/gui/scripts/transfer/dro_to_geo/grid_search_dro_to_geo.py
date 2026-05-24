"""grid_search_dro_to_geo 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='grid_search_dro_to_geo',
    description='执行 grid search dro to geo 转移设计步骤，用于从基准轨道文件生成候选或优化后的转移方案。脚本读取 GUI 选择的轨道或搜索结果 JSON，并使用网格密度、时间范围、alpha 范围等参数控制计算规模。结果保存到 output/transfer，供后续优化或绘图脚本继续使用。',
    script_path='tod/transfers/dro_to_geo/grid_search_dro_to_geo.py',
    output_dir='output/transfer',
    group_label='DRO→GEO',
    cli_params=[
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro', name_pattern='dro_31_[0-9]*.json'),
        CliParam('--n-departure', '出发点数', 'int', '200', help='出发时间网格数，默认 200。'),
        CliParam('--n-alpha', 'alpha 密度', 'int', '100', help='alpha 网格密度，默认 100。'),
        CliParam('--alpha-min', 'alpha 下界', 'float', '0.5', help='alpha 搜索下界，默认 0.5。'),
        CliParam('--alpha-max', 'alpha 上界', 'float', '2.5', help='alpha 搜索上界，默认 2.5。'),
        CliParam('--max-transfer-time', '最大转移时间', 'float', '22.998482', help='最大转移时间（无量纲），默认 22.998482。', unit_group='time', default_unit='days'),
        CliParam('--intersection-threshold', 'GEO 相交阈值', 'float', '0.00026', help='GEO 相交距离阈值，默认 0.00026，单位 km。', unit_group='distance', default_unit='km'),
        CliParam('--min-distance', '最小距离阈值', 'float', '0.00026', help='候选解最小距离阈值，默认 0.00026，单位 km。', unit_group='distance', default_unit='km'),
        CliParam('--geo-n-points', 'GEO 采样点数', 'int', '1000', help='GEO 轨道采样点数，默认 1000。'),
        CliParam('--earth-radius', '地球半径', 'float', '0.00052', help='地球碰撞检测半径，默认 0.00052，单位 km。', unit_group='distance', default_unit='km'),
        CliParam('--moon-radius', '月球半径', 'float', '0.00026', help='月球碰撞检测半径，默认 0.00026，单位 km。', unit_group='distance', default_unit='km'),
    ],
)
