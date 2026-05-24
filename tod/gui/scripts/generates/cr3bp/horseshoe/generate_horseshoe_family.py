"""generate_horseshoe_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='horseshoe',
    name='generate_horseshoe_family',
    description='生成轨道族',
    script_path='tod/generates/cr3bp/horseshoe/generate_horseshoe_family.py',
    output_dir='output/horseshoe',
    group_label='生成',
    cli_params=[
        CliParam('--amplitude-min', '最小振幅', 'float', '0.01', help='延拓振幅下限（无量纲），默认 0.01。'),
        CliParam('--amplitude-max', '最大振幅', 'float', '0.5', help='延拓振幅上限（无量纲），默认 0.5。'),
        CliParam('--step-size', '步长', 'float', '0.01', help='延拓步长（无量纲），默认 0.01。'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50', help='目标生成轨道数，默认 50。'),
    ],
)
