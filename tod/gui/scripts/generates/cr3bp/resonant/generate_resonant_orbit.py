"""generate_resonant_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='resonant',
    name='generate_resonant_orbit',
    description='在地月 CR3BP 中生成 Resonant 单条轨道，用于后续转移搜索、轨道分析或任务设计。脚本读取 GUI 中填写的初始状态、周期猜测等参数。结果保存到 output/resonant，通常包含带时间戳的轨道 JSON 和 latest 副本。',
    script_path='tod/generates/cr3bp/resonant/generate_resonant_orbit.py',
    output_dir='output/resonant',
    group_label='生成',
    cli_params=[
        CliParam('--ratio', '共振比例', 'select', '3:1', choices=('3:1', '3:2', '2:1'), help='共振比例（3:1/3:2/2:1），默认 3:1。'),
        CliParam('--z0', '初始 z 位置', 'float', '0.0', help='种子轨道初始 z 坐标（无量纲），默认 0.0。'),
        CliParam('--vy0', '初始 y 方向速度', 'float', '0.0', help='种子轨道初始 vy 速度（无量纲），默认 0.0。'),
        CliParam('--period-guess', '周期猜测值', 'float', '3.0', help='初始周期猜测（无量纲 TU），默认 3.0。'),
        CliParam('--libration-point', '平动点', 'select', 'secondary', choices=('L1', 'L2', 'L3', 'L4', 'L5'), help='平动点选择（secondary/L1/L2），默认 secondary 表示次要天体附近。'),
    ],
)
