"""plot_dro_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dro',
    name='plot_dro_family',
    description='绘制轨道族',
    script_path='tod/plot/dro/plot_dro_family.py',
    output_dir='output/dro',
    group_label='绘图',
    cli_params=[
        CliParam('--json-file', '轨道族文件', 'str', '', help='轨道族 JSON 文件路径。', file_category='dro', name_pattern='*_family_*.json'),
        CliParam('--start', '起始索引', 'int', '-1', help='起始轨道索引，-1 表示从第一条，默认 -1。'),
        CliParam('--end', '结束索引', 'int', '-1', help='结束轨道索引（含），-1 表示到最后一条，默认 -1。'),
        CliParam('--step', '绘制间隔', 'int', '1', help='每隔 N 条轨道绘制 1 条，1 表示绘制全部，默认 1。'),
        CliParam('--plot-global-2d', '全局 2D 视图（XY 平面）', 'bool', '', help='绘制 DRO 轨道族在 XY 平面的全局 2D 视图，勾选后启用。'),
        CliParam('--plot-global-3d', '全局 3D 视图', 'bool', '', help='绘制 DRO 轨道族在 3D 空间的全局视图，勾选后启用。'),
        CliParam('--plot-center', '绘图中心', 'str', '月球', help='3D 视图的绘图中心，默认 月球。', choices=('月球', '地球', '地月质心'), choice_values={'月球': 'moon', '地球': 'earth', '地月质心': 'emb'}, hidden_when='--plot-global-3d'),
        CliParam('--plot-elev', '仰角（度）', 'float', '20', help='3D 视图仰角（度），默认 20。', hidden_when='--plot-global-3d'),
        CliParam('--plot-azim', '方位角（度）', 'float', '-60', help='3D 视图方位角（度），默认 -60。', hidden_when='--plot-global-3d'),
        CliParam('--plot-jacobi-stability', 'Jacobi 常数-周期-稳定性关系图', 'bool', '', help='绘制 Jacobi 常数与轨道周期、稳定性的关系曲线，勾选后启用。'),
    ],
)
