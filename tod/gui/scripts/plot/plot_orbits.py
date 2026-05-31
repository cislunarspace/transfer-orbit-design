"""plot_orbits 的 GUI 参数注册。

统一入口，支持 DRO / RO / Halo 轨道族和单条轨道的绘图。
用户可混合选择不同类型文件叠加绘制在同一张图上。
每个文件可在表格中独立配置绘制范围（起始索引、结束索引、绘制间隔）。
"""

from tod.gui.script_registry import CliParam, MultiCliParam, PerFileField, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='plot',
    name='plot_orbits',
    description='绘制轨道族 / 单条轨道（DRO / RO / Halo）',
    script_path='tod/plot/plot_orbits.py',
    output_dir='output/plot',
    group_label='绘图',
    multi_cli_params=[
        MultiCliParam(
            flag='--json-file',
            label='轨道文件',
            file_category='orbit',
            name_pattern='*.json',
            help='支持多文件：点击"添加文件"选择多个 JSON 文件（家族或单条轨道），'
                 '每个文件可在表格中独立配置绘制范围',
            per_file_fields=[
                PerFileField(
                    key='start',
                    label='起始索引',
                    field_type='int',
                    default='-1',
                    help='起始轨道索引，-1 表示从第一条',
                ),
                PerFileField(
                    key='end',
                    label='结束索引',
                    field_type='int',
                    default='-1',
                    help='结束轨道索引（含），-1 表示到最后一条',
                ),
                PerFileField(
                    key='step',
                    label='绘制间隔',
                    field_type='int',
                    default='1',
                    help='每隔 N 条轨道绘制 1 条，1 表示绘制全部',
                    min_value=1,
                ),
            ],
        ),
    ],
    cli_params=[
        CliParam('--plane', '投影平面', 'str', '', help='覆盖自动检测的投影平面（留空=自动）', advanced=True),
        CliParam('--view-2d', '2D 视图', 'bool', '', help='绘制轨道在选定平面的 2D 视图，勾选后启用。'),
        CliParam('--view-3d', '3D 视图', 'bool', '', help='绘制轨道的 3D 示意图，勾选后启用。'),
        CliParam('--plot-center', '绘图中心', 'str', 'moon', help='3D 视图的绘图中心', choices=('月球', '地球', '地月质心'), choice_values={'月球': 'moon', '地球': 'earth', '地月质心': 'emb'}, hidden_when='--plot-global-3d'),
        CliParam('--plot-elev', '仰角（度）', 'float', '20', help='3D 视图仰角（度）', hidden_when='--plot-global-3d'),
        CliParam('--plot-azim', '方位角（度）', 'float', '-60', help='3D 视图方位角（度）', hidden_when='--plot-global-3d'),
        CliParam('--jacobi-period-stability', 'Jacobi-周期-稳定性图', 'bool', '', help='绘制 Jacobi 常数-周期-稳定性联合图，勾选后启用。'),
    ],
)
