"""optimize_dro_to_ro 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='optimize_dro_to_ro',
    description='优化',
    script_path='tod/transfers/dro_to_ro/optimize_dro_to_ro.py',
    output_dir='output/transfer',
    group_label='DRO→RO',
    cli_params=[
        CliParam('--search-file', '搜索结果文件', 'str', '', help='网格搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--ro-file', 'RO 文件', 'str', '', help='RO 轨道 JSON 文件路径。', file_category='ro'),
        CliParam('--alpha-min', 'alpha 下界', 'float', '0.5', help='alpha 搜索下界，默认 0.5。'),
        CliParam('--alpha-max', 'alpha 上界', 'float', '2.5', help='alpha 搜索上界，默认 2.5。'),
        CliParam('--nlp-maxiter', 'NLP 最大迭代', 'int', '100', help='NLP 最大迭代次数，默认 100。'),
        CliParam('--nlp-ftol', 'NLP 函数容差', 'float', '1e-8', help='NLP 函数容差，默认 1e-8。'),
        CliParam('--top-k', '前 K 个可行解', 'int', '', help='取前 K 个可行解优化。'),
        CliParam('--max-cases', '最大案例数', 'int', '', help='最大优化案例数。'),
        CliParam('--n-workers', '并行 worker 数', 'int', '', help='并行 worker 数。'),
        CliParam('--velocity-angle-tol', '速度方向容差', 'float', '0.05', help='速度方向容差（弧度），默认 0.05。', unit_group='angle'),
    ],
)
