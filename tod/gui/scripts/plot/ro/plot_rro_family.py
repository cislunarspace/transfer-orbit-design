"""plot_rro_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ro',
    name='plot_rro_family',
    description='可视化 plot rro family 相关结果，帮助检查轨道几何、稳定性、搜索候选或优化质量。脚本读取 GUI 选择的 JSON 文件，并根据勾选项绘制 2D/3D、散点、统计或交互浏览视图。未填写保存路径时弹出 Matplotlib 窗口；填写保存路径时生成图片文件。',
    script_path='tod/plot/ro/plot_rro_family.py',
    output_dir='output/ro',
    group_label='绘图',
    cli_params=[
        CliParam('--json-file', '轨道族文件', 'str', '', help='轨道族 JSON 文件路径。', file_category='ro', name_pattern='*_family_*.json'),
        CliParam('--start', '起始索引', 'int', '-1', help='起始轨道索引，-1 表示从第一条，默认 -1。'),
        CliParam('--end', '结束索引', 'int', '-1', help='结束轨道索引（含），-1 表示到最后一条，默认 -1。'),
        CliParam('--step', '绘制间隔', 'int', '1', help='每隔 N 条轨道绘制 1 条，1 表示绘制全部，默认 1。'),
        CliParam('--plot-global-2d', '全局 2D 视图（XY 平面）', 'bool', '', help='绘制 RRO 轨道族在 XY 平面的 2D 视图，勾选后启用。'),
        CliParam('--plot-global-3d', '全局 3D 视图', 'bool', '', help='绘制 RRO 轨道族的 3D 示意图，勾选后启用。'),
        CliParam('--plot-jacobi-stability', 'Jacobi-周期-稳定性图', 'bool', '', help='绘制 Jacobi 常数-周期-稳定性联合图，勾选后启用。'),
    ],
)
