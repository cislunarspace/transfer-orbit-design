"""generate_ro_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ro',
    name='generate_ro_orbit',
    description='生成共振轨道',
    script_path='tod/generates/cr3bp/ro/generate_ro_orbit.py',
    output_dir='output/ro',
    group_label='生成',
    cli_params=[
        CliParam('--ratio', '共振比例', 'select', '3:1', choices=('3:1', '3:2'), help='共振比例（3:1/3:2），默认 3:1。'),
        CliParam('--x0', '初始 x 坐标', 'float', '', help='初始 x 坐标（无量纲），默认值由共振比例决定。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '', help='初始 y 方向速度（无量纲），默认值由共振比例决定。', unit_group='velocity'),
        CliParam('--period', '目标周期', 'float', '', help='目标周期（天），默认值由共振比例决定。', unit_group='time', default_unit='days'),
    ],
)
