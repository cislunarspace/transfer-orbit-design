"""generate_lpo_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='lpo',
    name='generate_lpo_family',
    description='在地月 CR3BP 中生成 LPO 轨道族。',
    script_path='tod/generates/cr3bp/lpo/generate_lpo_family.py',
    output_dir='output/lpo',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L4', choices=('L4', 'L5')),
        CliParam('--method', '延拓方法', 'select', 'natural', choices=('natural', 'pseudo_arclength')),
        CliParam('--amplitude-min', '最小振幅', 'float', '0.01'),
        CliParam('--amplitude-max', '最大振幅', 'float', '0.5'),
        CliParam('--step-size', '步长', 'float', '0.01'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50'),
    ],
)
