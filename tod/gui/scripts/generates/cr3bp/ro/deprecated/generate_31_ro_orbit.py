"""generate_31_ro_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ro',
    name='generate_31_ro_orbit',
    description='生成 3:1 轨道',
    script_path='tod/generates/cr3bp/ro/deprecated/generate_31_ro_orbit.py',
    output_dir='output/ro',
    group_label='生成',
    cli_params=[
        CliParam('--x0', '初始 x 坐标', 'float', '-0.8805', help='初始 x 坐标（无量纲），默认 -0.8805。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '0.3921', help='初始 y 方向速度（无量纲），默认 0.3921。', unit_group='velocity'),
        CliParam('--period', '目标周期', 'float', '78.460655', help='目标周期（无量纲），默认 78.460655。', unit_group='time', default_unit='days'),
    ],
)
