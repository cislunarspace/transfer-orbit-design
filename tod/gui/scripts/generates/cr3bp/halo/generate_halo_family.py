"""generate_halo_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam、CliChipParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliChipParam, CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='halo',
    name='generate_halo_family',
    description='生成 Halo 轨道族',
    script_path='tod/generates/cr3bp/halo/generate_halo_family.py',
    output_dir='output/halo',
    group_label='生成',
    cli_chip_params=[
        CliChipParam(
            flag='--libration-point',
            label='平动点',
            options={'L1': 'L1', 'L2': 'L2', 'L3': 'L3'},
            default='L1',
            help='平动点选择，支持多选以批量生成多个平动点的轨道族',
        ),
        CliChipParam(
            flag='--halo-class',
            label='Halo 类别',
            options={'北族 (Class I)': '0', '南族 (Class II)': '1'},
            default='北族 (Class I)',
            help='Halo 轨道族类型；单选北族或南族时生成单分支，北族+南族同时选择时从共享 Lyapunov 交叉轨道生成两支。',
        ),
    ],
    cli_params=[
        CliParam('--seed-file', '种子轨道文件', 'str', '', help='已有 Halo 轨道 JSON 文件（提供时跳过种子生成）', file_category='halo', name_pattern='halo_L[123]_[NS]_[0-9]*.json', required=False, advanced=True),
        CliParam('--amplitude-z', 'Z 振幅', 'float', '0.23', help='Z 方向振幅，默认 0.23，单位 DU。', unit_group='distance', default_unit='DU', advanced=True, hidden_when='--seed-file'),
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
