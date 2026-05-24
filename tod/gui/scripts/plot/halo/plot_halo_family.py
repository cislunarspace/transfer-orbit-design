"""plot_halo_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='halo',
    name='plot_halo_family',
    description='绘制轨道族',
    script_path='tod/plot/halo/plot_halo_family.py',
    output_dir='output/halo',
    group_label='绘图',
    cli_params=[
        CliParam('--json-file', '轨道族文件', 'str', '', help='轨道族 JSON 文件路径。', file_category='halo', name_pattern='*_family_*.json'),
        CliParam('--start', '起始索引', 'int', '-1', help='起始轨道索引，-1 表示从第一条，默认 -1。'),
        CliParam('--end', '结束索引', 'int', '-1', help='结束轨道索引（含），-1 表示到最后一条，默认 -1。'),
        CliParam('--step', '绘制间隔', 'int', '1', help='每隔 N 条轨道绘制 1 条，1 表示绘制全部，默认 1。'),
        CliParam('--view-2d', '2D 视图（XZ 平面）', 'bool', '', help='绘制 Halo 轨道族在 XZ 平面的 2D 视图，勾选后启用。'),
        CliParam('--view-3d', '3D 视图', 'bool', '', help='绘制 Halo 轨道族的 3D 示意图，勾选后启用。'),
        CliParam('--jacobi-period-stability', 'Jacobi-周期-稳定性图', 'bool', '', help='绘制 Jacobi 常数-周期-稳定性联合图，勾选后启用。'),
    ],
)
