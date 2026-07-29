# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""_conversion 星历转换脚本。

本模块将 CR3BP 轨道状态映射到真实星历模型，依赖 SPICE kernels（de440.bsp、naif0012.tls）和 UTC 参考历元。输入为 DRO/Halo 单轨道或轨道族 JSON，输出为含修正状态、残差和元数据的星历转换结果。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.ephemeris._conversion --help
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

project_root = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_OUTPUT_DIR = project_root / "output" / "ephemeris"
DEFAULT_SPICE_KERNEL_DIR = Path(
    os.environ.get("SPICE_KERNEL_DIR", str(project_root.parent / "e2m2e" / "kernels"))
)
DEFAULT_BODIES = ("EARTH", "MOON", "SUN")

try:
    from e2m2e.algorithms.ephemeris_correction import (
        EphemerisCorrectionResult,
        correct_ephemeris_patch_points as _e2m2e_correct_ephemeris_patch_points,
    )
except ModuleNotFoundError:
    from typing import Any as EphemerisCorrectionResult

    def _e2m2e_correct_ephemeris_patch_points(*args: Any, **kwargs: Any) -> EphemerisCorrectionResult:
        """报告当前 e2m2e 版本缺少星历修正分发函数。"""
        raise RuntimeError(
            "当前 e2m2e 安装缺少 e2m2e.algorithms.ephemeris_correction；"
            "请更新 e2m2e 或在测试中 patch _e2m2e_correct_ephemeris_patch_points。"
        )

def correct_ephemeris_patch_points(*args, **kwargs) -> EphemerisCorrectionResult:
    """执行 correct_ephemeris_patch_points 对应的处理逻辑。"""
    return cast(EphemerisCorrectionResult, _e2m2e_correct_ephemeris_patch_points(*args, **kwargs))

class EphemerisConversionAdapter:
    """封装星历转换的外部依赖（SPICE、CR3BP 系统），替代闭包工厂。"""

    def __init__(self, spice: Any, cr3bp_system: Any) -> None:
        self._spice = spice
        self._cr3bp_system = cr3bp_system

    def build_orbit(self, payload: dict[str, Any]) -> Any:
        from e2m2e.core import Orbit

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as file:
            json.dump(payload, file)
            temp_path = Path(file.name)
        try:
            return Orbit.load_from_file(filename=temp_path, system=self._cr3bp_system)
        finally:
            temp_path.unlink(missing_ok=True)

    def build_dynamics(self, config: SingleConversionConfig | FamilyConversionConfig) -> Any:
        import spiceypy
        from e2m2e.core.ephemeris_dynamics import EphemerisDynamics
        from e2m2e.core.ephemeris_system import EphemerisSystem
        from e2m2e.mbse.data.enums import ReferenceFrame

        kernel_path = self._spice.find_ephemeris_kernel(str(config.spice_kernel_dir))
        leapseconds_path = config.spice_kernel_dir / "naif0012.tls"
        spiceypy.furnsh(str(leapseconds_path))
        self._spice.load_kernel(kernel_path)
        eph_system = EphemerisSystem(
            bodies=list(config.bodies),
            spice=self._spice,
            origin="EARTH",
            frame=ReferenceFrame.J2000,
        )
        return EphemerisDynamics(system=eph_system)

    def reference_et(self, config: SingleConversionConfig | FamilyConversionConfig) -> float:
        return float(self._spice.utc_to_et(config.reference_epoch))

    def convert_states(self, t_patch_syn: Any, states_syn: Any, reference_et_value: float) -> tuple[Any, Any]:
        from e2m2e.algorithms import convert_to_j2000
        from e2m2e.core import SynodicJ2000System

        import tod.commons.constants as _tod_constants

        transform = SynodicJ2000System(cr3bp_system=self._cr3bp_system, spice=self._spice)
        return convert_to_j2000(t_patch_syn, states_syn, transform, reference_et_value, _tod_constants.TU)

    def correct(
        self,
        config: SingleConversionConfig | FamilyConversionConfig,
        dynamics: Any,
        t_patch_j2000: Any,
        states_j2000: Any,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "tolerance": config.position_tol,
            "max_iter": config.max_iter,
            "verbose": True,
            "n_workers": config.per_orbit_workers,
            "kernel_dir": str(config.spice_kernel_dir),
            "velocity_tolerance": config.velocity_tol,
        }
        if config.method == "homotopy":
            kwargs["base_bodies"] = ["EARTH", "MOON"]
        return correct_ephemeris_patch_points(
            config.method,
            dynamics,
            t_patch_j2000,
            states_j2000,
            **kwargs,
        )

    def sample_patch_points(self, orbit: Any, n_points: int) -> tuple[Any, Any]:
        from e2m2e.algorithms import sample_patch_points

        return sample_patch_points(orbit, n_points)

    def finalize(self) -> None:
        import spiceypy
        spiceypy.kclear()

@dataclass(frozen=True)
class LoadedOrbitPayload:

    payload: dict[str, Any]
    orbit_index: int | None

@dataclass(frozen=True)
class SingleConversionConfig:
    """保存 SingleConversionConfig 的配置字段。

    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    orbit_type: str
    input_file: Path
    reference_epoch: str
    method: str
    patch_points: int
    position_tol: float
    velocity_tol: float
    spice_kernel_dir: Path
    bodies: tuple[str, ...]
    output_file: Path | None
    per_orbit_workers: int
    orbit_index: int | None
    include_full_trajectory: bool = True
    max_iter: int = 50

@dataclass(frozen=True)
class FamilyConversionConfig:
    """保存 FamilyConversionConfig 的配置字段。

    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    orbit_type: str
    input_file: Path
    reference_epoch: str
    method: str
    patch_points: int
    position_tol: float
    velocity_tol: float
    spice_kernel_dir: Path
    bodies: tuple[str, ...]
    output_file: Path | None
    per_orbit_workers: int
    family_workers: int
    fail_fast: bool
    include_full_trajectory: bool
    max_iter: int = 50

def build_single_parser(orbit_type: str) -> argparse.ArgumentParser:
    """构建单轨道转换的命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description=f"Convert one {orbit_type.upper()} orbit from CR3BP to ephemeris model."
    )
    _add_common_arguments(parser)
    parser.add_argument(
        "--orbit-index",
        type=int,
        default=None,
        help="Select one orbit from a family JSON input.",
    )
    return parser

def build_family_parser(orbit_type: str) -> argparse.ArgumentParser:
    """构建轨道族转换的命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description=f"Convert a {orbit_type.upper()} orbit family from CR3BP to ephemeris model."
    )
    _add_common_arguments(parser)
    parser.add_argument(
        "--family-workers",
        type=_positive_int,
        default=1,
        help="Number of family-level workers; defaults to serial processing.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop family conversion on the first failed orbit.",
    )
    parser.add_argument(
        "--include-full-trajectory",
        action="store_true",
        help="Include propagated full trajectories for each converted family member.",
    )
    return parser

def single_config_from_args(
    args: argparse.Namespace, orbit_type: str
) -> SingleConversionConfig:
    """从命令行参数构造单轨道转换配置。"""
    return SingleConversionConfig(
        orbit_type=orbit_type,
        input_file=Path(args.input_file),
        reference_epoch=args.reference_epoch,
        method=args.method,
        patch_points=args.patch_points,
        position_tol=args.position_tol,
        velocity_tol=args.velocity_tol,
        spice_kernel_dir=Path(args.spice_kernel_dir),
        bodies=_parse_bodies(args.bodies),
        output_file=_optional_path(args.output_file),
        per_orbit_workers=args.per_orbit_workers,
        orbit_index=args.orbit_index,
        max_iter=args.max_iter,
    )

def family_config_from_args(
    args: argparse.Namespace, orbit_type: str
) -> FamilyConversionConfig:
    """从命令行参数构造轨道族转换配置。"""
    return FamilyConversionConfig(
        orbit_type=orbit_type,
        input_file=Path(args.input_file),
        reference_epoch=args.reference_epoch,
        method=args.method,
        patch_points=args.patch_points,
        position_tol=args.position_tol,
        velocity_tol=args.velocity_tol,
        spice_kernel_dir=Path(args.spice_kernel_dir),
        bodies=_parse_bodies(args.bodies),
        output_file=_optional_path(args.output_file),
        per_orbit_workers=args.per_orbit_workers,
        family_workers=args.family_workers,
        fail_fast=args.fail_fast,
        include_full_trajectory=args.include_full_trajectory,
        max_iter=args.max_iter,
    )

def load_single_orbit_payload(input_file: Path, orbit_index: int | None) -> LoadedOrbitPayload:
    """读取单条轨道或轨道族中的指定轨道载荷。"""
    data = _load_json_object(input_file)
    if "orbits" not in data:
        return LoadedOrbitPayload(payload=data, orbit_index=None)

    if orbit_index is None:
        raise ValueError("family input requires --orbit-index for single-orbit conversion")

    orbits = data["orbits"]
    if not isinstance(orbits, list):
        raise ValueError("family input field 'orbits' must be a list")
    if orbit_index < 0 or orbit_index >= len(orbits):
        raise IndexError(f"orbit index {orbit_index} out of range")
    orbit_payload = orbits[orbit_index]
    if not isinstance(orbit_payload, dict):
        raise ValueError("family orbit entry must be a JSON object")
    return LoadedOrbitPayload(payload=orbit_payload, orbit_index=orbit_index)

def run_single_conversion(
    config: SingleConversionConfig, adapter: EphemerisConversionAdapter | None = None
) -> dict[str, Any]:
    """运行单轨道星历转换并写入输出文件。"""
    loaded = load_single_orbit_payload(config.input_file, config.orbit_index)
    effective_adapter = adapter or default_adapter()
    conversion_result = convert_orbit(
        loaded.payload,
        config,
        effective_adapter,
        include_full_trajectory=config.include_full_trajectory,
    )
    payload = {
        "metadata": _single_metadata(config, loaded.orbit_index),
        "result": conversion_result,
    }
    _write_output(payload, _resolve_output_file(config.output_file, "single", config.orbit_type))
    effective_adapter.finalize()
    return payload

def run_family_conversion(
    config: FamilyConversionConfig, adapter: EphemerisConversionAdapter | None = None
) -> dict[str, Any]:
    """运行轨道族星历转换并写入输出文件。"""
    payloads = load_family_payloads(config.input_file)
    effective_adapter = adapter
    if effective_adapter is None and (config.family_workers <= 1 or config.fail_fast):
        effective_adapter = default_adapter()

    if adapter is None and config.family_workers > 1 and not config.fail_fast:
        entries = run_default_family_payload_conversion_parallel(
            payloads,
            config,
            include_full_trajectory=config.include_full_trajectory,
            family_workers=config.family_workers,
        )
    else:
        def convert(payload: dict[str, Any], index: int, include_full_trajectory: bool) -> dict[str, Any]:
            """转换单条轨道载荷。"""
            return convert_orbit(payload, config, effective_adapter, include_full_trajectory)

        entries = run_family_payload_conversion(
            payloads,
            convert,
            fail_fast=config.fail_fast,
            include_full_trajectory=config.include_full_trajectory,
            family_workers=config.family_workers,
        )
    payload = {
        "metadata": _family_metadata(config),
        "results": entries,
    }
    _write_output(payload, _resolve_output_file(config.output_file, "family", config.orbit_type))
    if effective_adapter is not None:
        effective_adapter.finalize()
    return payload

def convert_orbit(
    payload: dict[str, Any],
    config: SingleConversionConfig | FamilyConversionConfig,
    adapter: EphemerisConversionAdapter,
    include_full_trajectory: bool,
) -> dict[str, Any]:
    """执行单条轨道的 CR3BP→星历转换流水线。"""
    orbit = adapter.build_orbit(payload)
    if getattr(orbit, "period", None) is None:
        raise ValueError(f"unable to determine {config.orbit_type} orbit period")
    dynamics = adapter.build_dynamics(config)
    reference_et_value = adapter.reference_et(config)
    t_patch_syn, states_syn = adapter.sample_patch_points(orbit, config.patch_points)
    t_patch_j2000, states_j2000 = adapter.convert_states(
        t_patch_syn, states_syn, reference_et_value
    )
    correction = adapter.correct(config, dynamics, t_patch_j2000, states_j2000)
    continuity = _validate_continuity(
        dynamics,
        _to_list(correction.t_patch),
        _to_nested_list(correction.state_patch),
        include_full_trajectory,
    )
    result = {
        **_conversion_result_fields(correction),
        "position_errors_km": continuity["position_errors_km"],
        "source_summary": _orbit_source_summary(payload),
    }
    if include_full_trajectory:
        result.update(
            {
                "full_trajectory_states": continuity["full_trajectory_states"],
                "full_trajectory_times_et": continuity["full_trajectory_times_et"],
            }
        )
    return result

def default_adapter() -> EphemerisConversionAdapter:
    """构造默认的星历转换适配器。"""
    from e2m2e.core import CR3BP_System
    from e2m2e.core.spice import SPICEManager

    import tod.commons.constants as _tod_constants

    spice = SPICEManager()
    cr3bp_system = CR3BP_System(mu=_tod_constants.MU, primary="earth", secondary="moon")
    return EphemerisConversionAdapter(spice=spice, cr3bp_system=cr3bp_system)

def main_single(orbit_type: str, argv: list[str] | None = None) -> dict[str, Any]:
    """单轨道转换的 CLI 入口。"""
    parser = build_single_parser(orbit_type)
    return run_single_conversion(single_config_from_args(parser.parse_args(argv), orbit_type))

def main_family(orbit_type: str, argv: list[str] | None = None) -> dict[str, Any]:
    """轨道族转换的 CLI 入口。"""
    parser = build_family_parser(orbit_type)
    return run_family_conversion(family_config_from_args(parser.parse_args(argv), orbit_type))

def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-file", required=True, help="Ephemeris conversion input JSON file.")
    parser.add_argument("--reference-epoch", required=True, help="UTC reference epoch for CR3BP-to-J2000 mapping.")
    parser.add_argument(
        "--method",
        choices=("standard", "two_level", "homotopy"),
        default="two_level",
        help="Ephemeris correction method.",
    )
    parser.add_argument("--patch-points", type=int, default=10)
    parser.add_argument("--position-tol", type=float, default=1e-3)
    parser.add_argument("--velocity-tol", type=float, default=1e-6)
    parser.add_argument(
        "--spice-kernel-dir",
        default=str(DEFAULT_SPICE_KERNEL_DIR),
        help="Directory containing SPICE kernels.",
    )
    parser.add_argument("--bodies", default=",".join(DEFAULT_BODIES))
    parser.add_argument("--output-file", default=None)
    parser.add_argument("--per-orbit-workers", type=_positive_int, default=1)
    parser.add_argument(
        "--max-iter",
        type=_positive_int,
        default=50,
        help="Maximum correction iterations per run.",
    )

def load_family_payloads(input_file: Path) -> list[dict[str, Any]]:
    """读取轨道族文件中的全部轨道载荷。"""
    data = _load_json_object(input_file)
    orbits = data.get("orbits")
    if not isinstance(orbits, list):
        raise ValueError("family conversion input must contain top-level 'orbits' list")
    for orbit in orbits:
        if not isinstance(orbit, dict):
            raise ValueError("family orbit entries must be JSON objects")
    return list(orbits)

def run_default_family_payload_conversion_parallel(
    payloads: list[dict[str, Any]],
    config: FamilyConversionConfig,
    *,
    include_full_trajectory: bool,
    family_workers: int,
) -> list[dict[str, Any]]:
    """使用默认适配器并行转换轨道族。"""
    entries: list[dict[str, Any] | None] = [None] * len(payloads)
    with ProcessPoolExecutor(max_workers=family_workers) as executor:
        futures = {
            executor.submit(
                _convert_family_payload_with_default_adapter,
                payload,
                index,
                config,
                include_full_trajectory,
            ): (index, payload)
            for index, payload in enumerate(payloads)
        }
        for future in as_completed(futures):
            index, payload = futures[future]
            try:
                conversion_result = future.result()
            except Exception as exc:
                entries[index] = _family_failure_entry(index, payload, exc)
            else:
                entries[index] = _family_entry_from_conversion(index, conversion_result)
    return [entry for entry in entries if entry is not None]

def _convert_family_payload_with_default_adapter(
    payload: dict[str, Any],
    index: int,
    config: FamilyConversionConfig,
    include_full_trajectory: bool,
) -> dict[str, Any]:
    adapter = default_adapter()
    try:
        return convert_orbit(payload, config, adapter, include_full_trajectory)
    finally:
        adapter.finalize()

def run_family_payload_conversion(
    payloads: list[dict[str, Any]],
    convert: Callable[[dict[str, Any], int, bool], dict[str, Any]],
    *,
    fail_fast: bool,
    include_full_trajectory: bool,
    family_workers: int = 1,
) -> list[dict[str, Any]]:
    """使用给定转换函数处理轨道族载荷。"""
    if family_workers <= 1 or fail_fast:
        return _run_family_payload_conversion_serial(
            payloads,
            convert,
            fail_fast=fail_fast,
            include_full_trajectory=include_full_trajectory,
        )

    entries: list[dict[str, Any] | None] = [None] * len(payloads)
    with ThreadPoolExecutor(max_workers=family_workers) as executor:
        futures = {
            executor.submit(convert, payload, index, include_full_trajectory): (index, payload)
            for index, payload in enumerate(payloads)
        }
        for future in as_completed(futures):
            index, payload = futures[future]
            try:
                conversion_result = future.result()
            except Exception as exc:
                entries[index] = _family_failure_entry(index, payload, exc)
            else:
                entries[index] = _family_entry_from_conversion(index, conversion_result)
    return [entry for entry in entries if entry is not None]

def _run_family_payload_conversion_serial(
    payloads: list[dict[str, Any]],
    convert: Callable[[dict[str, Any], int, bool], dict[str, Any]],
    *,
    fail_fast: bool,
    include_full_trajectory: bool,
) -> list[dict[str, Any]]:
    entries = []
    for index, payload in enumerate(payloads):
        try:
            conversion_result = convert(payload, index, include_full_trajectory)
        except Exception as exc:
            entries.append(_family_failure_entry(index, payload, exc))
            if fail_fast:
                break
        else:
            entry = _family_entry_from_conversion(index, conversion_result)
            entries.append(entry)
            if fail_fast and entry["status"] != "success":
                break
    return entries

def _conversion_status(converged: bool) -> str:
    return "success" if converged else "not_converged"

def _conversion_result_fields(correction: Any) -> dict[str, Any]:
    converged = bool(correction.converged)
    return {
        "status": _conversion_status(converged),
        "converged": converged,
        "iterations": int(correction.iterations),
        "max_residual": float(correction.max_residual),
        "velocity_residual": _optional_float(correction.velocity_residual),
        "residual_history": [float(value) for value in correction.residual_history],
        "velocity_residual_history": _optional_float_list(
            correction.velocity_residual_history
        ),
        "corrected_states": _to_nested_list(correction.state_patch),
        "corrected_times_et": _to_list(correction.t_patch),
    }

def _family_success_entry(index: int, conversion_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "orbit_index": index,
        "status": "success",
        "result": conversion_result,
    }

def _family_not_converged_entry(index: int, conversion_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "orbit_index": index,
        "status": "not_converged",
        "result": conversion_result,
    }

def _family_failure_entry(index: int, payload: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "orbit_index": index,
        "status": "failure",
        "error": str(exc),
        "source_summary": _orbit_source_summary(payload),
    }

def _family_entry_from_conversion(index: int, conversion_result: dict[str, Any]) -> dict[str, Any]:
    if conversion_result.get("status") == "not_converged":
        return _family_not_converged_entry(index, conversion_result)
    return _family_success_entry(index, conversion_result)

from tod.generates.ephemeris.validate import (
    optional_float,
    optional_float_list,
    position_error,
    to_list,
    to_nested_list,
    validate_continuity,
)

def _validate_continuity(*args, **kwargs):
    """向后兼容包装：内部调用 validate_continuity。"""
    return validate_continuity(*args, **kwargs)

def _position_error(*args, **kwargs):
    """向后兼容包装。"""
    return position_error(*args, **kwargs)

def _to_list(*args, **kwargs):
    """向后兼容包装。"""
    return to_list(*args, **kwargs)

def _to_nested_list(*args, **kwargs):
    """向后兼容包装。"""
    return to_nested_list(*args, **kwargs)

def _optional_float(*args, **kwargs):
    """向后兼容包装。"""
    return optional_float(*args, **kwargs)

def _optional_float_list(*args, **kwargs):
    """向后兼容包装。"""
    return optional_float_list(*args, **kwargs)

def _single_metadata(
    config: SingleConversionConfig, selected_orbit_index: int | None
) -> dict[str, Any]:
    metadata = _base_metadata(config)
    metadata.update(
        {
            "mode": "single",
            "orbit_index": selected_orbit_index,
            "include_full_trajectory": config.include_full_trajectory,
        }
    )
    return metadata

def _family_metadata(config: FamilyConversionConfig) -> dict[str, Any]:
    metadata = _base_metadata(config)
    metadata.update(
        {
            "mode": "family",
            "family_workers": config.family_workers,
            "fail_fast": config.fail_fast,
            "include_full_trajectory": config.include_full_trajectory,
        }
    )
    return metadata

def _base_metadata(config: SingleConversionConfig | FamilyConversionConfig) -> dict[str, Any]:
    return {
        "source_path": str(config.input_file),
        "orbit_type": config.orbit_type,
        "method": config.method,
        "reference_epoch": config.reference_epoch,
        "body_set": list(config.bodies),
        "patch_point_count": config.patch_points,
        "position_tolerance_km": config.position_tol,
        "velocity_tolerance_km_s": config.velocity_tol,
        "spice_kernel_dir": str(config.spice_kernel_dir),
        "per_orbit_workers": config.per_orbit_workers,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }

def _resolve_output_file(
    output_file: Path | None, mode: str, orbit_type: str
) -> Path:
    if output_file is not None:
        return output_file
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"{orbit_type}_{mode}_ephemeris_conversion_{timestamp}.json"

def _write_output(payload: dict[str, Any], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)

def _summarize_family_orbit(
    payload: dict[str, Any], index: int, include_full_trajectory: bool
) -> dict[str, Any]:
    summary = _orbit_source_summary(payload)
    return {
        "orbit_index": index,
        "source_summary": summary,
        "include_full_trajectory": include_full_trajectory,
    }

def _orbit_source_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in ("period", "x0", "vy0", "z0")
        if key in payload
    }

def _load_json_object(input_file: Path) -> dict[str, Any]:
    with input_file.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("ephemeris conversion input must be a JSON object")
    return data

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

def _optional_path(value: str | None) -> Path | None:
    if value is None:
        return None
    return Path(value)
