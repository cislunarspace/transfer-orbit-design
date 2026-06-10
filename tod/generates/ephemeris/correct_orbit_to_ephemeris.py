"""correct_orbit_to_ephemeris 星历转换脚本。

本模块为 CR3BP 轨道到真实星历模型的统一 CLI 入口，支持 DRO 和 Halo 轨道类型，
支持 standard / two_level / homotopy 三种修正方法。输出文件名按
{prefix}_{method}_tol{position_tol}.json 自动命名，并附加计时与地心距诊断数据。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.ephemeris.correct_orbit_to_ephemeris --help
       uv run python -m tod.generates.ephemeris.correct_orbit_to_ephemeris \
           --input-file output/dro/dro_31.json \
           --reference-epoch 2025-06-21T11:00:06 \
           --orbit-type dro \
           --method two_level \
           --position-tol 1e-3
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from tod.generates.ephemeris import _conversion


project_root = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_OUTPUT_DIR = project_root / "output" / "ephemeris"
DEFAULT_SPICE_KERNEL_DIR = Path(
    os.environ.get("SPICE_KERNEL_DIR", str(project_root.parent / "e2m2e" / "kernels"))
)
DEFAULT_BODIES = ("EARTH", "MOON", "SUN")


def build_parser() -> argparse.ArgumentParser:
    """构建统一 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        description="Convert one CR3BP orbit (DRO or Halo) from CR3BP to ephemeris model."
    )
    parser.add_argument(
        "--input-file", required=True, help="Ephemeris conversion input JSON file."
    )
    parser.add_argument(
        "--reference-epoch",
        required=True,
        help="UTC reference epoch for CR3BP-to-J2000 mapping.",
    )
    parser.add_argument(
        "--orbit-type",
        choices=("dro", "halo"),
        default="dro",
        help="Orbit type: dro or halo.",
    )
    parser.add_argument(
        "--method",
        choices=("standard", "two_level", "homotopy"),
        default="two_level",
        help="Ephemeris correction method.",
    )
    parser.add_argument(
        "--orbit-index",
        type=int,
        default=None,
        help="Select one orbit from a family JSON input.",
    )
    parser.add_argument(
        "--patch-points", type=int, default=10, help="Number of patch points."
    )
    parser.add_argument(
        "--position-tol",
        type=float,
        default=1e-3,
        help="Position continuity tolerance (km).",
    )
    parser.add_argument(
        "--velocity-tol",
        type=float,
        default=None,
        help="Velocity continuity tolerance (km/s). "
             "Defaults to same value as --position-tol.",
    )
    parser.add_argument(
        "--max-iter",
        type=_positive_int,
        default=50,
        help="Maximum correction iterations per run.",
    )
    parser.add_argument(
        "--spice-kernel-dir",
        default=str(DEFAULT_SPICE_KERNEL_DIR),
        help="Directory containing SPICE kernels.",
    )
    parser.add_argument(
        "--bodies", default=",".join(DEFAULT_BODIES), help="Comma-separated body list."
    )
    parser.add_argument(
        "--output-prefix",
        default=str(DEFAULT_OUTPUT_DIR / "orbit_ephemeris"),
        help="Output file prefix; actual file will be {prefix}_{method}_tol{tol}.json",
    )
    parser.add_argument(
        "--per-orbit-workers",
        type=_positive_int,
        default=1,
        help="Per-orbit parallel worker count.",
    )
    parser.add_argument(
        "--include-full-trajectory",
        action="store_true",
        default=True,
        help="Include propagated full trajectories.",
    )
    parser.add_argument(
        "--no-include-full-trajectory",
        action="store_true",
        dest="no_include_full_trajectory",
        help="Exclude propagated full trajectories.",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> _conversion.SingleConversionConfig:
    """从 CLI 参数构造 SingleConversionConfig。"""
    position_tol = args.position_tol
    velocity_tol = args.velocity_tol
    if velocity_tol is None:
        velocity_tol = position_tol

    include_full = args.include_full_trajectory and not getattr(
        args, "no_include_full_trajectory", False
    )

    return _conversion.SingleConversionConfig(
        orbit_type=args.orbit_type,
        input_file=Path(args.input_file),
        reference_epoch=args.reference_epoch,
        method=args.method,
        patch_points=args.patch_points,
        position_tol=position_tol,
        velocity_tol=velocity_tol,
        spice_kernel_dir=Path(args.spice_kernel_dir),
        bodies=_parse_bodies(args.bodies),
        output_file=None,
        per_orbit_workers=args.per_orbit_workers,
        orbit_index=args.orbit_index,
        include_full_trajectory=include_full,
        max_iter=args.max_iter,
    )


def _resolve_output_file(prefix: str, method: str, position_tol: float) -> Path:
    """根据前缀、方法名和容差生成输出文件路径。"""
    safe_tol = _format_tol(position_tol)
    filename = f"{prefix}_{method}_tol{safe_tol}.json"
    return Path(filename)


def _format_tol(value: float) -> str:
    """将容差值格式化为文件名友好的字符串。"""
    if value >= 1 or value == 0:
        return str(value)
    # 1e-3 -> 1e-3, 1e-06 -> 1e-6
    s = f"{value:.0e}"
    # Normalize: 1e-06 -> 1e-6
    if "e-0" in s:
        s = s.replace("e-0", "e-")
    return s


def _compute_geocentric_distance_stats(states: list[list[float]]) -> dict[str, float] | None:
    """从轨迹状态计算平均地心距（km）和标准差。

    Args:
        states: 状态列表，每个状态为 [x, y, z, vx, vy, vz]（单位 km）。

    Returns:
        包含 mean 和 std 的字典，或 None（states 为空）。
    """
    if not states:
        return None

    distances = []
    for state in states:
        x, y, z = float(state[0]), float(state[1]), float(state[2])
        distances.append((x * x + y * y + z * z) ** 0.5)

    n = len(distances)
    mean = sum(distances) / n
    variance = sum((d - mean) ** 2 for d in distances) / n
    std = variance ** 0.5

    return {"mean": mean, "std": std}


def _write_output(payload: dict[str, Any], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def run(argv: list[str] | None = None) -> dict[str, Any]:
    """执行单组星历转换并输出诊断数据。

    Args:
        argv: CLI 参数列表。

    Returns:
        包含转换结果和诊断数据的字典。
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    config = config_from_args(args)

    output_file = _resolve_output_file(args.output_prefix, args.method, config.position_tol)

    start_time = time.perf_counter()
    try:
        result = _conversion.run_single_conversion(config)
        elapsed = time.perf_counter() - start_time

        # Enrich result with diagnostics
        output_payload = {
            **result,
            "timing_seconds": elapsed,
            "status": result.get("result", {}).get("status", "unknown"),
        }

        # Compute geocentric distance stats if full trajectory is available
        full_states = result.get("result", {}).get("full_trajectory_states")
        if full_states:
            stats = _compute_geocentric_distance_stats(full_states)
            if stats:
                output_payload["geocentric_distance_mean_km"] = stats["mean"]
                output_payload["geocentric_distance_std_km"] = stats["std"]

    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        output_payload = {
            "metadata": {
                "source_path": str(config.input_file),
                "orbit_type": config.orbit_type,
                "method": config.method,
                "reference_epoch": config.reference_epoch,
                "body_set": list(config.bodies),
                "patch_point_count": config.patch_points,
                "position_tolerance_km": config.position_tol,
                "velocity_tolerance_km_s": config.velocity_tol,
                "max_iter": config.max_iter,
                "spice_kernel_dir": str(config.spice_kernel_dir),
                "per_orbit_workers": config.per_orbit_workers,
                "generated_at": _conversion.datetime.now(_conversion.UTC)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            },
            "timing_seconds": elapsed,
            "status": "failure",
            "error": str(exc),
        }

    _write_output(output_payload, output_file)
    return output_payload


def main(argv: list[str] | None = None) -> dict[str, Any]:
    """CLI 入口。"""
    return run(argv)


def _parse_bodies(value: str) -> tuple[str, ...]:
    bodies = tuple(body.strip().upper() for body in value.split(",") if body.strip())
    if not bodies:
        raise ValueError("--bodies must contain at least one body")
    return bodies


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


if __name__ == "__main__":
    main()
