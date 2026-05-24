"""generate_31_ro_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ro',
    name='generate_31_ro_family',
    description='在地月 CR3BP 中生成 3:1 RO 轨道族，用于后续转移搜索、星历转换或绘图分析。脚本读取 GUI 中填写的初始状态、周期猜测、延拓范围等参数；所有物理量按参数单位自动传给 CLI。结果保存到 output/ro，通常包含带时间戳的 JSON/CSV 和 latest 副本。',
    script_path='tod/generates/cr3bp/ro/generate_31_ro_family.py',
    output_dir='output/ro',
    group_label='生成',
    cli_params=[
        CliParam('--x0', '初始 x 坐标', 'float', '-0.8805', help='初始 x 坐标（无量纲），默认 -0.8805。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '0.3921', help='初始 y 方向速度（无量纲），默认 0.3921。', unit_group='velocity'),
        CliParam('--period', '轨道周期', 'float', '78.460655', help='轨道周期（无量纲），默认 78.460655。', unit_group='time', default_unit='days'),
        CliParam('--param-min', '延拓下限', 'float', '-0.8905', help='延拓参数范围下限，默认 -0.8905，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--param-max', '延拓上限', 'float', '-0.8305', help='延拓参数范围上限，默认 -0.8305，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--step-size', '延拓步长', 'float', '0.001', help='延拓步长，默认 0.001。'),
    ],
)
