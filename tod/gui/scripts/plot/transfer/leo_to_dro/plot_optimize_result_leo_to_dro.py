"""plot_optimize_result_leo_to_dro 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_optimize_result_leo_to_dro',
    description='绘制优化结果',
    script_path='tod/plot/transfer/leo_to_dro/plot_optimize_result_leo_to_dro.py',
    output_dir='output/transfer',
    group_label='LEO→DRO',
    cli_params=[
        CliParam('--file', '优化结果文件', 'str', '', help='优化结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--auto-latest', '按 mtime 选最新（显式 opt-in）', 'bool', '', help='显式 opt-in：按 mtime 选最新 optimization_leo_dro_*.json；与 --file 互斥。', advanced=True),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图，勾选后启用。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='转移时间 vs Δv 散点图，勾选后启用。'),
        CliParam('--interactive', '逐条浏览模式', 'bool', '', help='按转移时间排序逐条浏览，勾选后启用。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', 'best:5', help='all / best / best:N / random / 序号，默认 best:5。'),
        CliParam('--max-pos-err', '最大位置误差 (km)', 'float', '100.0', help='过滤：位置误差超过此值的结果不显示，默认 100.0。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大绘制轨道数', 'int', '200', help='--idx all 时最多绘制条数，默认 200。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '42', help='子采样随机种子，默认 42。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率，默认 150。', advanced=True),
    ],
)
