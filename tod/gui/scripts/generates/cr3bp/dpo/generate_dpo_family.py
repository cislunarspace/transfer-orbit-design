"""generate_dpo_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dpo',
    name='generate_dpo_family',
    description='生成轨道族',
    script_path='tod/generates/cr3bp/dpo/generate_dpo_family.py',
    output_dir='output/dpo',
    group_label='生成',
    cli_params=[
        CliParam('--x0', '初始 x 坐标', 'float', '1.03774', help='种子轨道初始 x 坐标（无量纲），默认 1.03774。', unit_group='distance', default_unit='DU'),
        CliParam('--vy0', '初始 vy 速度', 'float', '0.503284', help='种子轨道初始 vy 速度（无量纲），默认 0.503284。', unit_group='velocity'),
        CliParam('--period', '初始周期', 'float', '1.2011', help='初始周期猜测（无量纲），默认 1.2011。', unit_group='time', default_unit='days'),
        CliParam('--param-min', '延拓下限', 'float', '0.997', help='延拓参数范围下限（x0 最小值），默认 0.997，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--param-max', '延拓上限', 'float', '1.046', help='延拓参数范围上限（x0 最大值），默认 1.046，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--step-size', '延拓步长', 'float', '0.001', help='延拓步长，默认 0.001，单位 DU。', unit_group='distance', default_unit='DU'),
        CliParam('--verbose', '详细输出', 'bool', '', help='勾选后显示详细延拓过程（每步迭代、收敛进度等）'),
    ],
)
