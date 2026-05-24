"""generate_rro_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ro',
    name='generate_rro_family',
    description='生成 RRO 轨道族',
    script_path='tod/generates/cr3bp/ro/deprecated/generate_rro_family.py',
    output_dir='output/ro',
    group_label='生成',
    cli_params=[
        CliParam('--ro-file', 'RO 文件', 'str', '', help='3:2 RO 轨道 JSON 文件路径。', file_category='ro'),
        CliParam('--target-x0', '目标 x0', 'float', '-1.1318', help='目标 x0 分岔点，默认 -1.1318，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--z-max', '最大 z 幅值', 'float', '0.5', help='最大 z 幅值，默认 0.5，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--step-size', '延拓步长', 'float', '0.01', help='延拓步长，默认 0.01。'),
    ],
)
