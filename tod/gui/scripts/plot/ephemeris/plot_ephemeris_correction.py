"""plot_ephemeris_correction 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ephemeris',
    name='plot_ephemeris_correction',
    description='可视化 plot ephemeris correction 相关结果，帮助检查轨道几何、稳定性、搜索候选或优化质量。脚本读取 GUI 选择的 JSON 文件，并根据勾选项绘制 2D/3D、散点、统计或交互浏览视图。未填写保存路径时弹出 Matplotlib 窗口；填写保存路径时生成图片文件。',
    script_path='tod/plot/ephemeris/plot_ephemeris_correction.py',
    output_dir='output/ephemeris',
    needs_spice=True,
    group_label='绘图',
    cli_params=[
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--ephemeris-file', '星历修正文件', 'str', '', help='星历修正 JSON 文件路径。', file_category='ephemeris'),
    ],
)
