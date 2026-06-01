"""generate_dro_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dro',
    name='generate_dro_orbit',
    description='生成 DRO 轨道',
    script_path='tod/generates/cr3bp/dro/generate_dro_orbit.py',
    output_dir='output/dro',
    group_label='生成',
    cli_params=[
        CliParam('--x0', '初始 x 坐标', 'float', '1.1202', help='manual 路径初始 x 坐标（无量纲），默认 1.1202。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '-0.4618', help='manual 路径初始 y 方向速度（无量纲），默认 -0.4618。', unit_group='velocity'),
        CliParam('--period', '目标周期', 'float', '2.095', help='manual 路径目标周期（无量纲），默认 2.095。', unit_group='time', default_unit='days'),
        CliParam('--jacobi', '目标 Jacobi', 'float', '', help='catalog 路径：按目标 Jacobi 值从 normalized DRO catalog 选择 seed。', advanced=True),
        CliParam('--seed-id', 'Seed ID', 'str', '', help='catalog 路径：按 seed/orbit id 从 normalized DRO catalog 选择 seed。', advanced=True),
        CliParam('--jacobi-tolerance', 'Jacobi 容差', 'float', '1e-4', help='Jacobi 最近邻匹配容差。', advanced=True),
        CliParam('--catalog-dir', 'Catalog 目录', 'str', 'data/cr3bp_data/normalized', help='normalized CR3BP catalog 目录。', advanced=True),
        CliParam('--raw-data-dir', 'Raw 数据目录', 'str', 'data/cr3bp_data/raw', help='normalized catalog 缺失时用于自动导入的 raw XLSX 数据目录。', advanced=True),
        CliParam('--no-auto-build-catalog', '禁用自动导入 catalog', 'bool', '', help='normalized catalog 缺失时不自动从 raw 数据生成。', advanced=True),
        CliParam('--verbose', '详细输出', 'bool', '', help='勾选后显示详细迭代过程（残差、收敛进度等）'),
    ],
)
