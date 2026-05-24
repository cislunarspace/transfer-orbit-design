"""generate_dpo_orbit 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='dpo',
    name='generate_dpo_orbit',
    description='在地月 CR3BP 中生成单条 DPO 轨道。',
    script_path='tod/generates/cr3bp/dpo/generate_dpo_orbit.py',
    output_dir='output/dpo',
    group_label='生成',
    cli_params=[
        CliParam('--x0', '初始 x 位置', 'float', '1.1'),
        CliParam('--vy0', '初始 y 方向速度', 'float', '0.0'),
        CliParam('--period-guess', '周期猜测值', 'float', '3.0'),
    ],
)
