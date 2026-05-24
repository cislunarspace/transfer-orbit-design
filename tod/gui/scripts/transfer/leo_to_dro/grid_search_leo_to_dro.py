"""grid_search_leo_to_dro 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='grid_search_leo_to_dro',
    description='网格搜索',
    script_path='tod/transfers/leo_to_dro/grid_search_leo_to_dro.py',
    output_dir='output/transfer',
    group_label='LEO→DRO',
    cli_params=[
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--n-departure', '出发点数', 'int', '200', help='出发时间网格数，默认 200。'),
        CliParam('--n-alpha', 'alpha 密度', 'int', '100', help='alpha 网格密度，默认 100。'),
        CliParam('--alpha-min', 'alpha 下界', 'float', '1.2', help='alpha 搜索下界，默认 1.2。'),
        CliParam('--alpha-max', 'alpha 上界', 'float', '2.0', help='alpha 搜索上界，默认 2.0。'),
        CliParam('--max-transfer-time', '最大转移时间', 'float', '80.0', help='最大转移时间（无量纲），默认 80.0。', unit_group='time', default_unit='days'),
        CliParam('--intersection-threshold', '相交阈值', 'float', '0.001', help='相交判定距离阈值，默认 0.001，单位 km。', unit_group='distance', default_unit='km'),
        CliParam('--min-distance', '最小距离阈值', 'float', '0.001301', help='候选解最小距离阈值，默认 0.001301，单位 km。', unit_group='distance', default_unit='km'),
        CliParam('--earth-radius', '地球半径', 'float', '0.00052', help='地球碰撞检测半径，默认 0.00052，单位 km。', unit_group='distance', default_unit='km'),
        CliParam('--moon-radius', '月球半径', 'float', '0.00026', help='月球碰撞检测半径，默认 0.00026，单位 km。', unit_group='distance', default_unit='km'),
        CliParam('--leo-n-points', 'LEO 采样点数', 'int', '500', help='LEO 轨道采样点数，默认 500。'),
    ],
)
