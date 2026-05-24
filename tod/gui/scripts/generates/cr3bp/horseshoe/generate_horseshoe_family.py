"""generate_horseshoe_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='horseshoe',
    name='generate_horseshoe_family',
    description='在地月 CR3BP 中生成 Horseshoe 轨道族。',
    script_path='tod/generates/cr3bp/horseshoe/generate_horseshoe_family.py',
    output_dir='output/horseshoe',
    group_label='生成',
    cli_params=[
        CliParam('--amplitude-min', '最小振幅', 'float', '0.01'),
        CliParam('--amplitude-max', '最大振幅', 'float', '0.5'),
        CliParam('--step-size', '步长', 'float', '0.01'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50'),
    ],
)
