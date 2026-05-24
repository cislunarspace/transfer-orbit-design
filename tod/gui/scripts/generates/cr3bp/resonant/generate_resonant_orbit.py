"""generate_resonant_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='resonant',
    name='generate_resonant_orbit',
    description='在地月 CR3BP 中生成指定 m:n 共振比例的周期轨道。',
    script_path='tod/generates/cr3bp/resonant/generate_resonant_orbit.py',
    output_dir='output/resonant',
    group_label='生成',
    cli_params=[
        CliParam('--ratio', '共振比例', 'select', '3:1', choices=('3:1', '3:2', '2:1')),
        CliParam('--z0', '初始 z 位置', 'float', '0.0'),
        CliParam('--vy0', '初始 y 方向速度', 'float', '0.0'),
        CliParam('--period-guess', '周期猜测值', 'float', '3.0'),
        CliParam('--libration-point', '平动点', 'select', 'secondary', choices=('secondary', 'L1', 'L2')),
    ],
)
