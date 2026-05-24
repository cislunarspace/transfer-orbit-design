"""generate_lyapunov_family 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。
"""

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='lyapunov',
    name='generate_lyapunov_family',
    description='在地月 CR3BP 中生成 Lyapunov 轨道族。',
    script_path='tod/generates/cr3bp/lyapunov/generate_lyapunov_family.py',
    output_dir='output/lyapunov',
    group_label='生成',
    cli_params=[
        CliParam('--libration-point', '平动点', 'select', 'L1', choices=('L1', 'L2', 'L3')),
        CliParam('--method', '延拓方法', 'select', 'natural', choices=('natural', 'pseudo_arclength')),
        CliParam('--amplitude-x-min', 'x 方向最小振幅', 'float', '0.01'),
        CliParam('--amplitude-x-max', 'x 方向最大振幅', 'float', '0.5'),
        CliParam('--step-size', '步长', 'float', '0.01'),
        CliParam('--n-orbits', '生成轨道数量', 'int', '50'),
    ],
)
