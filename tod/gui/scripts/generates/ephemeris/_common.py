"""_common 的 GUI 参数注册。

本模块声明 ScriptEntry、CliParam 和文件选择规则，供 GUI 生成参数控件并调用对应底层脚本。description 按“目的、输入、输出”描述脚本，help 文本说明默认值与单位。
"""


from tod.gui.script_registry import CliParam


def _ephemeris_conversion_cli_params(orbit_type: str, mode: str) -> list[CliParam]:
    """Build CLI params for ephemeris conversion scripts.

    Args:
        orbit_type: "dro" or "halo"
        mode: "single" or "family"
    """
    file_category = "dro" if orbit_type == "dro" else "halo"
    input_help = "轨道族 JSON 文件路径" if mode == "family" else "单条轨道或轨道族 JSON 文件路径"
    input_pattern = "*_family_*.json" if mode == "family" else None
    params = [
        CliParam(
            "--input-file",
            "星历转换输入文件",
            "str",
            help=input_help,
            file_category=file_category,
            name_pattern=input_pattern,
        ),
        CliParam("--reference-epoch", "参考历元", "str", help="UTC 参考历元", required=True),
        CliParam(
            "--method",
            "星历转换方法",
            "str",
            "two_level",
            help="星历转换方法",
            choices=("standard", "two_level", "homotopy"),
        ),
    ]
    if mode == "single":
        params.append(CliParam("--orbit-index", "轨道索引", "int", help="从轨道族文件中选择单条轨道"))
    params.extend(
        [
            CliParam("--patch-points", "分段点数量", "int", "10", help="多重打靶分段点数量", advanced=True),
            CliParam("--position-tol", "位置容差", "float", "1e-3", help="位置连续性容差（km）", advanced=True),
            CliParam("--velocity-tol", "速度容差", "float", "1e-6", help="速度连续性容差（km/s）", advanced=True),
            CliParam("--spice-kernel-dir", "SPICE 内核目录", "str", help="SPICE 内核目录", advanced=True),
            CliParam("--bodies", "天体集合", "str", "EARTH,MOON,SUN", help="逗号分隔的天体集合", advanced=True),
            CliParam("--output-file", "输出文件", "str", help="输出 JSON 文件路径", advanced=True, kind="file_output"),
            CliParam("--per-orbit-workers", "单轨 worker 数", "int", "1", help="单条轨道修正并行 worker 数", advanced=True),
        ]
    )
    if mode == "family":
        params.extend(
            [
                CliParam("--family-workers", "轨道族 worker 数", "int", "1", help="轨道族级并行 worker 数", advanced=True),
                CliParam("--fail-fast", "首次失败即停止", "bool", help="轨道族转换遇到失败时立即停止", advanced=True),
                CliParam("--include-full-trajectory", "包含完整轨迹", "bool", help="轨道族输出包含完整轨迹", advanced=True),
            ]
        )
    return params
