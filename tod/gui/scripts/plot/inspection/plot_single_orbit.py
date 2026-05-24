"""plot_single_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='inspection',
    name='plot_single_orbit',
    description='绘制单条轨道',
    script_path='tod/plot/inspection/plot_single_orbit.py',
    group_label='单轨道绘图',
    cli_params=[
        CliParam('--json-file', '轨道文件', 'str', '', help='轨道 JSON 文件路径。'),
    ],
)
