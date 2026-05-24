"""generate_resonant_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='resonant',
    name='generate_resonant_family',
    description='在地月 CR3BP 中生成指定 m:n 共振比例的轨道族延拓。',
    script_path='tod/generates/cr3bp/resonant/generate_resonant_family.py',
    output_dir='output/resonant',
    group_label='生成',
    cli_params=[
        CliParam('--ratio', '共振比例', 'select', '3:1', choices=('3:1', '3:2', '2:1')),
        CliParam('--method', '延拓方法', 'select', 'natural', choices=('natural', 'pseudo_arclength')),
        CliParam('--z-min', 'z 参数最小值', 'float', '0.01'),
        CliParam('--z-max', 'z 参数最大值', 'float', '0.5'),
        CliParam('--step-size', '步长', 'float', '0.01'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50'),
    ],
)
