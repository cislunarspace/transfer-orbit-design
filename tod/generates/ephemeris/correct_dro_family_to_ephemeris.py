"""correct_dro_family_to_ephemeris 星历转换脚本。

本模块将 CR3BP 轨道状态映射到真实星历模型，依赖 SPICE kernels（de440.bsp、naif0012.tls）和 UTC 参考历元。输入为 DRO/Halo 单轨道或轨道族 JSON，输出为含修正状态、残差和元数据的星历转换结果。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.ephemeris.correct_dro_family_to_ephemeris --help
"""


from __future__ import annotations

from tod.generates.ephemeris import _conversion


def main(argv: list[str] | None = None):
    """执行脚本主流程。
    
    Args:
        argv: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    return _conversion.main_family("dro", argv)


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ephemeris',
    name='correct_dro_family_to_ephemeris',
    description='修正轨道族',
    script_path='tod/generates/ephemeris/correct_dro_family_to_ephemeris.py',
    output_dir='output/ephemeris',
    needs_spice=True,
    group_label='星历转换',
    cli_params=[
        CliParam('--input-file', '星历转换输入文件', 'str', '', help='轨道族 JSON 文件路径。', file_category='dro', name_pattern='*_family_*.json'),
        CliParam('--reference-epoch', '参考历元', 'str', '', help='UTC 参考历元。', required=True),
        CliParam('--method', '星历转换方法', 'str', 'two_level', help='星历转换方法。', choices=('standard', 'two_level', 'homotopy')),
        CliParam('--patch-points', '拼接点数量', 'int', '10', help='拼接点数量，用于轨迹连续性修正。', advanced=True),
        CliParam('--position-tol', '位置容差', 'float', '1e-3', help='位置连续性容差（km）。', advanced=True),
        CliParam('--velocity-tol', '速度容差', 'float', '1e-6', help='速度连续性容差（km/s）。', advanced=True),
        CliParam('--spice-kernel-dir', 'SPICE 内核目录', 'str', '', help='SPICE 内核目录。', advanced=True),
        CliParam('--bodies', '天体集合', 'str', 'EARTH,MOON,SUN', help='逗号分隔的天体集合。', advanced=True),
        CliParam('--output-file', '输出文件', 'str', '', help='输出 JSON 文件路径。', advanced=True, kind='file_output'),
        CliParam('--per-orbit-workers', '单轨 worker 数', 'int', '1', help='单条轨道修正并行 worker 数。', advanced=True),
        CliParam('--family-workers', '轨道族 worker 数', 'int', '1', help='轨道族级并行 worker 数。', advanced=True),
        CliParam('--fail-fast', '首次失败即停止', 'bool', '', help='轨道族转换遇到失败时立即停止。', advanced=True),
        CliParam('--include-full-trajectory', '包含完整轨迹', 'bool', '', help='轨道族输出包含完整轨迹。', advanced=True),
    ],
)
