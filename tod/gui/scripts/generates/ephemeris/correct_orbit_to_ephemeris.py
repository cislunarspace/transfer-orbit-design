"""correct_orbit_to_ephemeris 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam、CliChipParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""

from tod.gui.script_registry import CliChipParam, CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ephemeris',
    name='correct_orbit_to_ephemeris',
    description='修正单条轨道（支持多方法、多容差选择）',
    script_path='tod/generates/ephemeris/correct_orbit_to_ephemeris.py',
    output_dir='output/ephemeris',
    needs_spice=True,
    group_label='星历转换',
    cli_chip_params=[
        CliChipParam(
            '--method',
            '星历转换方法',
            options={
                '标准法': 'standard',
                '双重': 'two_level',
                '同伦法': 'homotopy',
            },
            default='标准法,双重,同伦法',
            help='选择要运行的星历转换方法（可多选）',
        ),
        CliChipParam(
            '--position-tol',
            '位置容差',
            options={
                '标准 (1e-3 km)': '1e-3',
                '严格 (1e-6 km)': '1e-6',
            },
            default='标准 (1e-3 km),严格 (1e-6 km)',
            help='选择位置容差（可多选）',
        ),
    ],
    cli_params=[
        CliParam('--input-file', '星历转换输入文件', 'str', '', help='单条轨道或轨道族 JSON 文件路径。'),
        CliParam('--reference-epoch', '参考历元', 'str', '', help='UTC 参考历元。', required=True),
        CliParam('--orbit-type', '轨道类型', 'str', 'dro', help='轨道类型：dro 或 halo。', choices=('dro', 'halo')),
        CliParam('--orbit-index', '轨道索引', 'int', '', help='从轨道族文件中选择单条轨道。'),
        CliParam('--patch-points', '拼接点数量', 'int', '10', help='拼接点数量，用于轨迹连续性修正。', advanced=True),
        CliParam('--velocity-tol', '速度容差', 'float', '1e-6', help='速度连续性容差（km/s），默认 1e-6。', advanced=True),
        CliParam('--max-iter', '最大迭代次数', 'int', '50', help='单次修正最大迭代次数，默认 50。', advanced=True),
        CliParam('--spice-kernel-dir', 'SPICE 内核目录', 'str', '', help='SPICE 内核目录。', advanced=True),
        CliParam('--bodies', '天体集合', 'str', 'EARTH,MOON,SUN', help='逗号分隔的天体集合，默认 EARTH,MOON,SUN。', advanced=True),
        CliParam('--output-prefix', '输出前缀', 'str', '', help='输出文件名前缀，实际文件为 {prefix}_{method}_tol{tol}.json。', advanced=True, kind='file_output'),
        CliParam('--per-orbit-workers', '单轨 worker 数', 'int', '1', help='单条轨道修正并行 worker 数，默认 1。', advanced=True),
        CliParam('--include-full-trajectory', '包含完整轨迹', 'bool', 'true', help='输出包含传播后的完整轨迹。', advanced=True),
    ],
)
