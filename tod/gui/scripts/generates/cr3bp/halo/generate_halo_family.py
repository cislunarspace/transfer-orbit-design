"""generate_halo_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='halo',
    name='generate_halo_family',
    description='在地月 CR3BP 中生成 Halo 轨道族，用于后续转移搜索、星历转换或绘图分析。脚本读取 GUI 中填写的初始状态、周期猜测、延拓范围等参数；所有物理量按参数单位自动传给 CLI。结果保存到 output/halo，通常包含带时间戳的 JSON/CSV 和 latest 副本。',
    script_path='tod/generates/cr3bp/halo/generate_halo_family.py',
    output_dir='output/halo',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'str', 'L1', help='平动点：L1, L2, L3，默认 L1。', choices=('L1', 'L2', 'L3')),
        CliParam('--halo-class', 'Halo 类型', 'str', '北族', help='Halo 轨道族类型，默认 北族。', choices=('北族', '南族'), choice_values={'北族': '0', '南族': '1'}),
        CliParam('--seed-file', '种子轨道文件', 'str', '', help='已有 Halo 轨道 JSON 文件（提供时跳过种子生成）', file_category='halo', name_pattern='halo_L[123]_[NS]_[0-9]*.json', required=False),
        CliParam('--amplitude-z', 'Z 振幅', 'float', '0.23', help='Z 方向振幅，默认 0.23，单位 DU。', unit_group='distance', default_unit='DU', hidden_when='--seed-file'),
        CliParam('--method', '延拓方法', 'str', 'pseudo_arclength', help='延拓方法：natural 或 pseudo_arclength，默认 pseudo_arclength。', choices=('natural', 'pseudo_arclength'), choice_values={'natural': 'natural', 'pseudo_arclength': 'pseudo_arclength'}),
        CliParam('--direction', '延拓方向', 'str', 'positive', help='自然延拓方向，默认 positive。', choices=('positive', 'negative', 'both'), choice_values={'positive': 'positive', 'negative': 'negative', 'both': 'both'}, hidden_when='--method==pseudo_arclength'),
        CliParam('--z-min', 'z 振幅下限', 'float', '0.001', help='延拓 z 振幅范围下限（正数，南族自动转为负值），默认 0.001，单位 DU。', unit_group='distance', default_unit='DU', hidden_when='--method==pseudo_arclength'),
        CliParam('--z-max', 'z 振幅上限', 'float', '0.5', help='延拓 z 振幅范围上限（正数，南族自动转为负值），默认 0.5，单位 DU。', unit_group='distance', default_unit='DU', hidden_when='--method==pseudo_arclength'),
        CliParam('--step-size', 'z 方向步长', 'float', '0.002', help='自然延拓 z 方向步长，默认 0.002，单位 DU。', unit_group='distance', default_unit='DU', hidden_when='--method==pseudo_arclength'),
        CliParam('--step-size-pal', '弧长步长', 'float', '0.0045', help='伪弧长延拓步长（无量纲），默认 0.0045。', hidden_when='--method==natural'),
        CliParam('--step-size-negative', '负向步长', 'float', '0.009', help='伪弧长延拓负向步长（默认等于正向步长）', hidden_when='--method==natural'),
        CliParam('--n-orbits', '轨道数量', 'int', '20', help='延拓轨道数量（z_range 模式下的最大轨道数安全阀），默认 20。', advanced=True),
    ],
)
