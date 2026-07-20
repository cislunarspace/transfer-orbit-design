"""dro/halo 族转换的 GUI 注册入口。

本文件供扫描器发现，导出 SCRIPT_ENTRIES（dro 和 halo 各一个）。
实际逻辑委托给 _conversion.main_family。
"""

from __future__ import annotations

from tod.generates.ephemeris import _conversion
from tod.scripting import CliParam, ScriptEntry


def main(argv: list[str] | None = None):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=("dro", "halo"), required=True)
    args, remaining = parser.parse_known_args(argv)
    return _conversion.main_family(args.family, remaining)


def _make_family_script_entry(family: str) -> ScriptEntry:
    return ScriptEntry(
        module="ephemeris",
        name=f"correct_{family}_family_to_ephemeris",
        description="修正轨道族",
        script_path="tod/generates/ephemeris/family_correction.py",
        output_dir="output/ephemeris",
        needs_spice=True,
        group_label="星历转换",
        cli_params=[
            CliParam("--input-file", "星历转换输入文件", "str", "", help="轨道族 JSON 文件路径。", file_category=family, name_pattern="*_family_*.json"),
            CliParam("--reference-epoch", "参考历元", "str", "", help="UTC 参考历元。", required=True),
            CliParam("--method", "星历转换方法", "str", "two_level", help="星历转换方法。", choices=("standard", "two_level", "homotopy")),
            CliParam("--patch-points", "拼接点数量", "int", "10", help="拼接点数量，用于轨迹连续性修正。", advanced=True),
            CliParam("--position-tol", "位置容差", "float", "1e-3", help="位置连续性容差（km）。", advanced=True),
            CliParam("--velocity-tol", "速度容差", "float", "1e-6", help="速度连续性容差（km/s）。", advanced=True),
            CliParam("--spice-kernel-dir", "SPICE 内核目录", "str", "", help="SPICE 内核目录。", advanced=True),
            CliParam("--bodies", "天体集合", "str", "EARTH,MOON,SUN", help="逗号分隔的天体集合。", advanced=True),
            CliParam("--output-file", "输出文件", "str", "", help="输出 JSON 文件路径。", advanced=True, kind="file_output"),
            CliParam("--per-orbit-workers", "单轨 worker 数", "int", "1", help="单条轨道修正并行 worker 数。", advanced=True),
            CliParam("--family-workers", "轨道族 worker 数", "int", "1", help="轨道族级并行 worker 数。", advanced=True),
            CliParam("--fail-fast", "首次失败即停止", "bool", "", help="轨道族转换遇到失败时立即停止。", advanced=True),
            CliParam("--include-full-trajectory", "包含完整轨迹", "bool", "", help="轨道族输出包含完整轨迹。", advanced=True),
        ],
    )


SCRIPT_ENTRIES = [
    _make_family_script_entry("dro"),
    _make_family_script_entry("halo"),
]
