"""validate_geo_to_dro 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='validate_geo_to_dro',
    description='验证',
    script_path='tod/transfers/geo_to_dro/validate_geo_to_dro.py',
    output_dir='output/transfer',
    group_label='GEO→DRO',
)
