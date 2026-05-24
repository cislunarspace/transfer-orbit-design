"""generate_horseshoe_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='horseshoe',
    name='generate_horseshoe_family',
    description='在地月 CR3BP 中生成 Horseshoe 轨道族，用于后续转移搜索、轨道分析或任务设计。脚本读取 GUI 中填写的延拓范围、步长和延拓方法等参数。结果保存到 output/horseshoe，通常包含带时间戳的轨道 JSON 和 latest 副本。',
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
