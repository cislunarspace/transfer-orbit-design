"""generate_31_dro_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dro',
    name='generate_31_dro_orbit',
    description='在地月 CR3BP 中生成 3:1 DRO 单轨道，用于后续转移搜索、星历转换或绘图分析。脚本读取 GUI 中填写的初始状态、周期猜测、延拓范围等参数；所有物理量按参数单位自动传给 CLI。结果保存到 output/dro，通常包含带时间戳的 JSON/CSV 和 latest 副本。',
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
