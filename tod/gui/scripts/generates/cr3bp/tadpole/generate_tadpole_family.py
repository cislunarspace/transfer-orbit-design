"""generate_tadpole_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='tadpole',
    name='generate_tadpole_family',
    description='在地月 CR3BP 中生成 Tadpole 轨道族。',
    script_path='tod/generates/cr3bp/tadpole/generate_tadpole_family.py',
    output_dir='output/tadpole',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L4', choices=('L4', 'L5')),
        CliParam('--leading-trailing', '领先/滞后', 'select', 'leading', choices=('leading', 'trailing')),
        CliParam('--amplitude-min', '最小振幅', 'float', '0.01'),
        CliParam('--amplitude-max', '最大振幅', 'float', '0.5'),
        CliParam('--step-size', '步长', 'float', '0.01'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50'),
    ],
)
