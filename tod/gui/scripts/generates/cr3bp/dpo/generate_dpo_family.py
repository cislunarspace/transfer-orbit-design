"""generate_dpo_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dpo',
    name='generate_dpo_family',
    description='在地月 CR3BP 中生成 DPO 轨道族，用于后续转移搜索、轨道分析或任务设计。脚本读取 GUI 中填写的延拓范围、步长和延拓方法等参数。结果保存到 output/dpo，通常包含带时间戳的轨道 JSON 和 latest 副本。',
    script_path='tod/generates/cr3bp/dpo/generate_dpo_family.py',
    output_dir='output/dpo',
    group_label='生成',
    cli_params=[
        CliParam('--method', '延拓方法', 'select', 'natural', choices=('natural', 'pseudo_arclength'), help='延拓方法（natural/pseudo_arclength），默认 natural。'),
        CliParam('--param-min', '参数最小值', 'float', '0.01', help='延拓参数下限（无量纲），默认 0.01。'),
        CliParam('--param-max', '参数最大值', 'float', '0.5', help='延拓参数上限（无量纲），默认 0.5。'),
        CliParam('--step-size', '步长', 'float', '0.01', help='延拓步长（无量纲），默认 0.01。'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50', help='目标生成轨道数，默认 50。'),
    ],
)
