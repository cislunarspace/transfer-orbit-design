"""plot_optimize_result_dro_to_ro 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='plot_optimize_result_dro_to_ro',
    description='可视化 plot optimize result dro to ro 相关结果，帮助检查轨道几何、稳定性、搜索候选或优化质量。脚本读取 GUI 选择的 JSON 文件，并根据勾选项绘制 2D/3D、散点、统计或交互浏览视图。未填写保存路径时弹出 Matplotlib 窗口；填写保存路径时生成图片文件。',
    script_path='tod/plot/transfer/dro_to_ro/plot_optimize_result_dro_to_ro.py',
    output_dir='output/transfer',
    group_label='DRO→RO',
    cli_params=[
        CliParam('--file', '优化结果文件', 'str', '', help='优化结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--orbit', '转移轨道图（3D）', 'bool', '', help='重新积分并绘制转移轨道 3D 示意图，勾选后启用。'),
        CliParam('--time-dv', '转移时间-Δv 散点图', 'bool', '', help='转移时间 vs Δv 散点图，勾选后启用。'),
        CliParam('--idx', '选中轨道（--orbit 模式）', 'str', 'best', help='整数索引 / best / best:N / random / all，默认 best。'),
        CliParam('--save', '保存图片路径', 'str', '', help='不填则弹窗显示。'),
        CliParam('--max-points', '最大绘制轨道数', 'int', '500', help='--idx all 时最多绘制条数，默认 500。', advanced=True),
        CliParam('--seed', '随机种子', 'int', '0', help='子采样随机种子，默认 0。', advanced=True),
        CliParam('--dpi', '图片 DPI', 'int', '150', help='保存图片的分辨率，默认 150。', advanced=True),
    ],
)
