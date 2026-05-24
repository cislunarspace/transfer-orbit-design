"""generate_31_dro_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dro',
    name='generate_31_dro_orbit',
    description='生成 3:1 轨道',
    script_path='tod/generates/cr3bp/dro/generate_31_dro_orbit.py',
    output_dir='output/dro',
    group_label='生成',
    cli_params=[
        CliParam('--x0', '初始 x 坐标', 'float', '1.1202', help='初始 x 坐标（无量纲），默认 1.1202。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '-0.4618', help='初始 y 方向速度（无量纲），默认 -0.4618。', unit_group='velocity'),
        CliParam('--period', '目标周期', 'float', '2.095', help='目标周期（无量纲），默认 2.095。', unit_group='time', default_unit='days'),
        CliParam('--verbose', '详细输出', 'bool', '', help='勾选后显示详细迭代过程（残差、收敛进度等）'),
    ],
)
