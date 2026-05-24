"""generate_spo_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='spo',
    name='generate_spo_orbit',
    description='生成轨道',
    script_path='tod/generates/cr3bp/spo/generate_spo_orbit.py',
    output_dir='output/spo',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L4', choices=('L4', 'L5'), help='平动点选择（L4/L5），默认 L4。'),
        CliParam('--amplitude', '振幅', 'float', '0.1', help='种子轨道振幅（无量纲），默认 0.1。'),
        CliParam('--period-guess', '周期猜测值', 'float', '3.0', help='初始周期猜测（无量纲 TU），默认 3.0。'),
    ],
)
