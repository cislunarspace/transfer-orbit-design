"""generate_tadpole_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='tadpole',
    name='generate_tadpole_orbit',
    description='生成轨道',
    script_path='tod/generates/cr3bp/tadpole/generate_tadpole_orbit.py',
    output_dir='output/tadpole',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L4', choices=('L4', 'L5'), help='平动点选择（L4/L5），默认 L4。'),
        CliParam('--amplitude', '振幅', 'float', '0.1', help='种子轨道振幅（无量纲），默认 0.1。'),
        CliParam('--leading-trailing', '领先/滞后', 'select', 'leading', choices=('leading', 'trailing'), help='构型选择（leading/trailing），默认 leading。'),
    ],
)
