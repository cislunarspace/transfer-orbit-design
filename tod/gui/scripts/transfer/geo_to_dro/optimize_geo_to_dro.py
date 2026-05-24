"""optimize_geo_to_dro 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='optimize_geo_to_dro',
    description='执行 optimize geo to dro 转移设计步骤，用于从基准轨道文件生成候选或优化后的转移方案。脚本读取 GUI 选择的轨道或搜索结果 JSON，并使用网格密度、时间范围、alpha 范围等参数控制计算规模。结果保存到 output/transfer，供后续优化或绘图脚本继续使用。',
    script_path='tod/transfers/geo_to_dro/optimize_geo_to_dro.py',
    output_dir='output/transfer',
    group_label='GEO→DRO',
    cli_params=[
        CliParam('--search-file', '搜索结果文件', 'str', '', help='网格搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--alpha-min', 'alpha 下界', 'float', '1.0', help='alpha 搜索下界，默认 1.0。'),
        CliParam('--alpha-max', 'alpha 上界', 'float', '1.5', help='alpha 搜索上界，默认 1.5。'),
        CliParam('--t-min', '转移时间下界', 'float', '5.0', help='转移时间下界（无量纲），默认 5.0。', unit_group='time', default_unit='days'),
        CliParam('--t-max', '转移时间上界', 'float', '60.0', help='转移时间上界（无量纲），默认 60.0。', unit_group='time', default_unit='days'),
        CliParam('--t-ins-min', '插入时间下界', 'float', '0.0', help='DRO 插入时间下界，默认 0.0，单位 days。', unit_group='time', default_unit='days'),
        CliParam('--t-ins-max', '插入时间上界', 'float', '10.0', help='DRO 插入时间上界，默认 10.0，单位 days。', unit_group='time', default_unit='days'),
        CliParam('--velocity-angle-tol', '速度平行性容差', 'float', '', help='速度平行性容差（度）', unit_group='angle'),
        CliParam('--nlp-maxiter', 'NLP 最大迭代', 'int', '100', help='NLP 最大迭代次数，默认 100。'),
        CliParam('--nlp-ftol', 'NLP 函数容差', 'float', '1e-8', help='NLP 函数容差，默认 1e-8。'),
        CliParam('--top-k', '前 K 个可行解', 'int', '', help='取前 K 个可行解优化。'),
        CliParam('--max-cases', '最大案例数', 'int', '', help='最大优化案例数。'),
        CliParam('--n-workers', '并行 worker 数', 'int', '', help='并行 worker 数。'),
    ],
)
