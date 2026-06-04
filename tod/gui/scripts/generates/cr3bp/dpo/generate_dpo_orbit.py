"""generate_dpo_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CatalogSeedSelectorParam, CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dpo',
    name='generate_dpo_orbit',
    description='生成 DPO 轨道',
    script_path='tod/generates/cr3bp/dpo/generate_dpo_orbit.py',
    output_dir='output/dpo',
    group_label='生成',
    catalog_seed_selectors=[
        CatalogSeedSelectorParam(
            key='dpo_catalog_seed',
            label='DPO 参考初值',
            orbit_type='dpo',
            manual_flags=('--x0', '--vy0', '--period'),
        ),
    ],
    cli_params=[
        CliParam('--x0', '初始 x 坐标', 'float', '1.03774', help='manual 路径初始 x 坐标（无量纲），默认 1.03774。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '0.503284', help='manual 路径初始 y 方向速度（无量纲），默认 0.503284。', unit_group='velocity'),
        CliParam('--period', '目标周期', 'float', '1.2011', help='manual 路径目标周期（无量纲），默认 1.2011。', unit_group='time', default_unit='days'),
        CliParam('--jacobi', '目标 Jacobi', 'float', '', help='参考初值路径：按目标 Jacobi 值从参考数据集中匹配参考初值。', advanced=True),
        CliParam('--seed-id', '参考记录编号', 'str', '', help='参考初值路径：按参考记录编号从参考数据集中选择参考初值。', advanced=True),
        CliParam('--jacobi-tolerance', 'Jacobi 容差', 'float', '', help='按 Jacobi 常数匹配模式的硬容差；留空表示不启用硬容差。', advanced=True),
        CliParam('--period-multiplier', '外推周期数', 'float', '1.0', help='参考初值路径外推周期倍数，必须大于 0。', advanced=True),
        CliParam('--num-points', '采样点数', 'int', '1000', help='参考初值路径外推轨迹采样点数，范围 2..100000。', advanced=True),
        CliParam('--catalog-dir', '参考数据集目录', 'str', 'data/cr3bp_data/normalized', help='normalized 参考数据集目录。', advanced=True),
        CliParam('--raw-data-dir', '原始数据目录', 'str', 'data/cr3bp_data/raw', help='normalized 参考数据集缺失时用于自动导入的 raw XLSX 数据目录。', advanced=True),
        CliParam('--no-auto-build-catalog', '禁用自动导入参考数据集', 'bool', '', help='normalized 参考数据集缺失时不自动从 raw 数据生成。', advanced=True),
        CliParam('--verbose', '详细输出', 'bool', '', help='勾选后显示详细迭代过程（残差、收敛进度等）'),
    ],
)
