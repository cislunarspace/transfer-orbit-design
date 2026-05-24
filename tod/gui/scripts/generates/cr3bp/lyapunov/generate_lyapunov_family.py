"""generate_lyapunov_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='lyapunov',
    name='generate_lyapunov_family',
    description='在地月 CR3BP 中生成 Lyapunov 轨道族，用于后续转移搜索、轨道分析或任务设计。脚本读取 GUI 中填写的延拓范围、步长和延拓方法等参数。结果保存到 output/lyapunov，通常包含带时间戳的轨道 JSON 和 latest 副本。',
    script_path='tod/generates/cr3bp/lyapunov/generate_lyapunov_family.py',
    output_dir='output/lyapunov',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L1', choices=('L1', 'L2', 'L3'), help='平动点选择（L1/L2/L3），默认 L1。'),
        CliParam('--method', '延拓方法', 'select', 'natural', choices=('natural', 'pseudo_arclength'), help='延拓方法（natural/pseudo_arclength），默认 natural。'),
        CliParam('--amplitude-x-min', 'x 方向最小振幅', 'float', '0.01', help='延拓 x 方向振幅下限（无量纲），默认 0.01。'),
        CliParam('--amplitude-x-max', 'x 方向最大振幅', 'float', '0.5', help='延拓 x 方向振幅上限（无量纲），默认 0.5。'),
        CliParam('--step-size', '步长', 'float', '0.01', help='延拓步长（无量纲），默认 0.01。'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50', help='目标生成轨道数，默认 50。'),
    ],
)
