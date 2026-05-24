"""generate_aro_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ro',
    name='generate_aro_family',
    description='生成 ARO 轨道族',
    script_path='tod/generates/cr3bp/ro/deprecated/generate_aro_family.py',
    output_dir='output/ro',
    group_label='生成',
    cli_params=[
        CliParam('--ro-file', 'RO 文件', 'str', '', help='3:2 RO 轨道 JSON 文件路径。', file_category='ro'),
        CliParam('--target-x0', '目标 x0', 'float', '-1.0878', help='目标 x0 分岔点，默认 -1.0878，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--z0', '固定 z0', 'float', '0.1999', help='固定 z0 坐标（无量纲），默认 0.1999。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '0.4', help='初始 y 方向速度猜测（无量纲），默认 0.4。', unit_group='velocity'),
        CliParam('--period', '初始周期', 'float', '172.314762', help='初始周期猜测（无量纲），默认 172.314762。', unit_group='time', default_unit='days'),
        CliParam('--x-min', 'x 下限', 'float', '-1.2', help='延拓 x0 范围下限，默认 -1.2，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--x-max', 'x 上限', 'float', '-0.9', help='延拓 x0 范围上限，默认 -0.9，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--step-size', '延拓步长', 'float', '0.005', help='延拓步长，默认 0.005。'),
    ],
)
