"""plot_interactive_orbit_inspector 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='inspection',
    name='plot_interactive_orbit_inspector',
    description='交互检查',
    script_path='tod/plot/inspection/plot_interactive_orbit_inspector.py',
    group_label='交互式检查',
    cli_params=[
        CliParam('--json-file', '轨道族文件', 'str', '', help='轨道族 JSON 文件路径。'),
        CliParam('--auto-latest', '按 mtime 选最新（显式 opt-in）', 'bool', '', help='显式 opt-in：按 mtime 选最新 ro_*.json 或 dro_*.json；与 --json-file 互斥。', advanced=True),
        CliParam('--plane', '投影平面', 'str', 'xy', help='投影平面: xy, xz, yz，默认 xy。'),
        CliParam('--show-3d', '显示 3D 视图', 'bool', '', help='同时显示 3D 视图，勾选后启用。'),
        CliParam('--fig-size', '图形大小', 'str', '10 8', help='图形大小 (宽 高)，默认 10 8。'),
    ],
)
