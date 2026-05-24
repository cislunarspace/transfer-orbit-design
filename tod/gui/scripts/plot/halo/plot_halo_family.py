"""plot_halo_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按"目的、输入、输出"描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, MultiCliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='halo',
    name='plot_halo_family',
    description='绘制轨道族',
    script_path='tod/plot/halo/plot_halo_family.py',
    output_dir='output/halo',
    group_label='绘图',
    multi_cli_params=[
        MultiCliParam(
            flag='--json-file',
            label='轨道族文件',
            file_category='halo',
            name_pattern='*_family_*.json',
            help='支持多文件：点击"添加文件"选择多个 JSON 文件，每个文件可单独配置绘制范围',
        ),
    ],
    cli_params=[
        CliParam('--view-2d', '2D 视图（XZ 平面）', 'bool', '', help='绘制 Halo 轨道族在 XZ 平面的 2D 视图，勾选后启用。'),
        CliParam('--view-3d', '3D 视图', 'bool', '', help='绘制 Halo 轨道族的 3D 示意图，勾选后启用。'),
        CliParam('--jacobi-period-stability', 'Jacobi-周期-稳定性图', 'bool', '', help='绘制 Jacobi 常数-周期-稳定性联合图，勾选后启用。'),
    ],
)
