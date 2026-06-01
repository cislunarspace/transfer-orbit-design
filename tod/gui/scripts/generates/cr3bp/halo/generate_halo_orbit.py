"""generate_halo_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='halo',
    name='generate_halo_orbit',
    description='生成轨道',
    script_path='tod/generates/cr3bp/halo/generate_halo_orbit.py',
    output_dir='output/halo',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'str', 'L1', help='平动点：L1, L2，默认 L1。', choices=('L1', 'L2')),
        CliParam('--amplitude-z', 'Z 振幅', 'float', '0.23', help='Z 方向振幅，默认 0.23，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--halo-class', 'Halo 类型', 'str', '北族', help='Halo 轨道族类型，默认 北族。', choices=('北族', '南族'), choice_values={'北族': '0', '南族': '1'}),
        CliParam('--period', '目标周期', 'float', '1.839732', help='目标周期（无量纲），默认 1.839732。', unit_group='time', default_unit='days'),
        CliParam('--x0', '初始 x 坐标', 'float', '0.9305269194214338', help='初始 x 坐标，默认 0.9305269194214338，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '0.10431508546142665', help='初始 y 方向速度，默认 0.10431508546142665。', unit_group='velocity', default_unit='VU'),
        CliParam('--max-iterations', '最大迭代次数', 'int', '150', help='最大迭代次数，默认 150。'),
        CliParam('--tolerance', '修正容差', 'float', '1e-6', help='修正容差，默认 1e-6。'),
    ],
)
