"""generate_tadpole_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='tadpole',
    name='generate_tadpole_orbit',
    description='在地月 CR3BP 中生成 Tadpole 单条轨道，用于后续转移搜索、轨道分析或任务设计。脚本读取 GUI 中填写的初始状态、周期猜测等参数。结果保存到 output/tadpole，通常包含带时间戳的轨道 JSON 和 latest 副本。',
    script_path='tod/generates/cr3bp/tadpole/generate_tadpole_orbit.py',
    output_dir='output/tadpole',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L4', choices=('L4', 'L5'), help='平动点选择（L4/L5），默认 L4。'),
        CliParam('--amplitude', '振幅', 'float', '0.1', help='种子轨道振幅（无量纲），默认 0.1。'),
        CliParam('--leading-trailing', '领先/滞后', 'select', 'leading', choices=('leading', 'trailing'), help='构型选择（leading/trailing），默认 leading。'),
    ],
)
