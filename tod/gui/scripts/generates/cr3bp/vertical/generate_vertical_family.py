"""generate_vertical_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='vertical',
    name='generate_vertical_family',
    description='在地月 CR3BP 中生成 Vertical 轨道族。',
    script_path='tod/generates/cr3bp/vertical/generate_vertical_family.py',
    output_dir='output/vertical',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L1', choices=('L1', 'L2', 'L3')),
        CliParam('--method', '延拓方法', 'select', 'natural', choices=('natural', 'pseudo_arclength')),
        CliParam('--amplitude-y-min', 'y 方向最小振幅', 'float', '0.01'),
        CliParam('--amplitude-y-max', 'y 方向最大振幅', 'float', '0.5'),
        CliParam('--step-size', '步长', 'float', '0.01'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50'),
    ],
)
