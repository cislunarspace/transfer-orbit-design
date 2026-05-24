"""generate_vertical_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='vertical',
    name='generate_vertical_orbit',
    description='在地月 CR3BP 中生成单条 Vertical 轨道。',
    script_path='tod/generates/cr3bp/vertical/generate_vertical_orbit.py',
    output_dir='output/vertical',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L1', choices=('L1', 'L2', 'L3')),
        CliParam('--amplitude-y', 'y 方向振幅', 'float', '0.1'),
        CliParam('--period-guess', '周期猜测值', 'float', '3.0'),
    ],
)
