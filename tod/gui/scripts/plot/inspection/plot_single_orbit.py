"""plot_single_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='inspection',
    name='plot_single_orbit',
    description='可视化 plot single orbit 相关结果，帮助检查轨道几何、稳定性、搜索候选或优化质量。脚本读取 GUI 选择的 JSON 文件，并根据勾选项绘制 2D/3D、散点、统计或交互浏览视图。未填写保存路径时弹出 Matplotlib 窗口；填写保存路径时生成图片文件。',
    script_path='tod/plot/inspection/plot_single_orbit.py',
    group_label='单轨道绘图',
    cli_params=[
        CliParam('--json-file', '轨道文件', 'str', '', help='轨道 JSON 文件路径。'),
    ],
)
