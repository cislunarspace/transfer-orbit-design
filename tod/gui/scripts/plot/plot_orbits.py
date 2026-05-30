"""plot_orbits 的 GUI 参数注册。

统一入口，支持 DRO / RO / Halo 轨道族和单条轨道的绘图。
用户可混合选择不同类型文件叠加绘制在同一张图上。
"""

from tod.gui.script_registry import CliParam, MultiCliParam, ScriptEntry

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
            file_category=None,
            name_pattern='*.json',
            help='支持多文件：点击"添加文件"选择多个 JSON 文件（家族或单条轨道），每个文件可单独配置绘制范围',
        ),
    ],
    cli_params=[
        CliParam('--start', '起始轨道索引', 'int', '-1', help='起始轨道索引，-1 表示从第一条（仅单文件模式有效）', advanced=True),
        CliParam('--end', '结束轨道索引', 'int', '-1', help='结束轨道索引（含），-1 表示到最后一条（仅单文件模式有效）', advanced=True),
        CliParam('--step', '绘制步长', 'int', '1', help='绘制轨道的间隔步长，1 表示绘制全部（仅单文件模式有效）', advanced=True),
        CliParam('--plane', '投影平面', 'str', '', help='覆盖自动检测的投影平面（xy / xz / yz）', choices=('自动', 'XY 平面', 'XZ 平面', 'YZ 平面'), choice_values={'自动': '', 'XY 平面': 'xy', 'XZ 平面': 'xz', 'YZ 平面': 'yz'}, advanced=True),
        CliParam('--view-2d', '2D 视图', 'bool', '', help='绘制轨道在选定平面的 2D 视图，勾选后启用。'),
        CliParam('--view-3d', '3D 视图', 'bool', '', help='绘制轨道的 3D 示意图，勾选后启用。'),
        CliParam('--jacobi-period-stability', 'Jacobi-周期-稳定性图', 'bool', '', help='绘制 Jacobi 常数-周期-稳定性联合图，勾选后启用。'),
    ],
)
