"""correct_dro_family_to_ephemeris 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ephemeris',
    name='correct_dro_family_to_ephemeris',
    description='修正轨道族',
    script_path='tod/generates/ephemeris/correct_dro_family_to_ephemeris.py',
    output_dir='output/ephemeris',
    needs_spice=True,
    group_label='星历转换',
    cli_params=[
        CliParam('--input-file', '星历转换输入文件', 'str', '', help='轨道族 JSON 文件路径。', file_category='dro', name_pattern='*_family_*.json'),
        CliParam('--reference-epoch', '参考历元', 'str', '', help='UTC 参考历元。', required=True),
        CliParam('--method', '星历转换方法', 'str', 'two_level', help='星历转换方法，默认 two_level。', choices=('standard', 'two_level', 'homotopy')),
        CliParam('--patch-points', '拼接点数量', 'int', '10', help='拼接点数量，用于轨迹连续性修正。', advanced=True),
        CliParam('--position-tol', '位置容差', 'float', '1e-3', help='位置连续性容差（km），默认 1e-3。', advanced=True),
        CliParam('--velocity-tol', '速度容差', 'float', '1e-6', help='速度连续性容差（km/s），默认 1e-6。', advanced=True),
        CliParam('--spice-kernel-dir', 'SPICE 内核目录', 'str', '', help='SPICE 内核目录。', advanced=True),
        CliParam('--bodies', '天体集合', 'str', 'EARTH,MOON,SUN', help='逗号分隔的天体集合，默认 EARTH,MOON,SUN。', advanced=True),
        CliParam('--output-file', '输出文件', 'str', '', help='输出 JSON 文件路径。', advanced=True, kind='file_output'),
        CliParam('--per-orbit-workers', '单轨 worker 数', 'int', '1', help='单条轨道修正并行 worker 数，默认 1。', advanced=True),
        CliParam('--family-workers', '轨道族 worker 数', 'int', '1', help='轨道族级并行 worker 数，默认 1。', advanced=True),
        CliParam('--fail-fast', '首次失败即停止', 'bool', '', help='轨道族转换遇到失败时立即停止，勾选后启用。', advanced=True),
        CliParam('--include-full-trajectory', '包含完整轨迹', 'bool', '', help='轨道族输出包含完整轨迹，勾选后启用。', advanced=True),
    ],
)
