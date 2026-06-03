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
from typing import Any


project_root = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_OUTPUT_DIR = project_root / "output" / "ephemeris"
DEFAULT_SPICE_KERNEL_DIR = Path(
    os.environ.get("SPICE_KERNEL_DIR", str(project_root.parent / "e2m2e" / "kernels"))
)
DEFAULT_BODIES = ("EARTH", "MOON", "SUN")


@dataclass(frozen=True)
class ConversionDependencies:
    """表示 ConversionDependencies 相关的数据结构或行为。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    build_orbit: Callable[[dict[str, Any]], Any]
    build_dynamics: Callable[[SingleConversionConfig | FamilyConversionConfig], Any]
    reference_et: Callable[[SingleConversionConfig | FamilyConversionConfig], float]
    sample_patch_points: Callable[[Any, int], tuple[Any, Any]]
    convert_to_j2000: Callable[[Any, Any, float], tuple[Any, Any]]
    correct_patch_points: Callable[
        [SingleConversionConfig | FamilyConversionConfig, Any, Any, Any], Any
    ]
    finalize: Callable[[], None] | None = None


@dataclass(frozen=True)
class LoadedOrbitPayload:
    """表示 LoadedOrbitPayload 相关的数据结构或行为。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
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


def build_single_parser(orbit_type: str) -> argparse.ArgumentParser:
    """构建运行所需对象。
    
    Args:
        orbit_type: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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
    """构建运行所需对象。
    
    Args:
        orbit_type: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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
    """执行 single_config_from_args 对应的处理逻辑。
    
    Args:
        args: 调用方传入的参数值。
        orbit_type: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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
    )


def family_config_from_args(
    args: argparse.Namespace, orbit_type: str
) -> FamilyConversionConfig:
    """执行 family_config_from_args 对应的处理逻辑。
    
    Args:
        args: 调用方传入的参数值。
        orbit_type: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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
    )


def load_single_orbit_payload(input_file: Path, orbit_index: int | None) -> LoadedOrbitPayload:
    """读取单条轨道或轨道族中的轨道载荷。
    
    Args:
        input_file: 调用方传入的参数值。
        orbit_index: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
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
    config: SingleConversionConfig, deps: ConversionDependencies | None = None
) -> dict[str, Any]:
    """运行对应计算流程。
    
    Args:
        config: 调用方传入的参数值。
        deps: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    loaded = load_single_orbit_payload(config.input_file, config.orbit_index)
    dependencies = deps or default_conversion_dependencies()
    conversion_result = convert_orbit(
        loaded.payload,
        config,
        dependencies,
        include_full_trajectory=config.include_full_trajectory,
    )
    payload = {
        "metadata": _single_metadata(config, loaded.orbit_index),
        "result": conversion_result,
    }
    _write_output(payload, _resolve_output_file(config.output_file, "single", config.orbit_type))
    if dependencies.finalize is not None:
        dependencies.finalize()
    return payload


def run_family_conversion(
    config: FamilyConversionConfig, deps: ConversionDependencies | None = None
) -> dict[str, Any]:
    """运行对应计算流程。
    
    Args:
        config: 调用方传入的参数值。
        deps: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    payloads = load_family_payloads(config.input_file)
    dependencies = deps
    if dependencies is None and (config.family_workers <= 1 or config.fail_fast):
        dependencies = default_conversion_dependencies()

    if deps is None and config.family_workers > 1 and not config.fail_fast:
        entries = run_default_family_payload_conversion_parallel(
            payloads,
            config,
            include_full_trajectory=config.include_full_trajectory,
            family_workers=config.family_workers,
        )
    else:
        def convert(payload: dict[str, Any], index: int, include_full_trajectory: bool) -> dict[str, Any]:
            """执行 convert 对应的处理逻辑。
            
            Args:
                payload: 调用方传入的参数值。
                index: 调用方传入的参数值。
                include_full_trajectory: 调用方传入的参数值。
            
            Returns:
                函数执行结果。
            """
            return convert_orbit(payload, config, dependencies, include_full_trajectory)

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
    if dependencies is not None and dependencies.finalize is not None:
        dependencies.finalize()
    return payload


def convert_orbit(
    payload: dict[str, Any],
    config: SingleConversionConfig | FamilyConversionConfig,
    deps: ConversionDependencies,
    include_full_trajectory: bool,
) -> dict[str, Any]:
    """执行单条轨道的星历转换。
    
    Args:
        payload: 调用方传入的参数值。
        config: 调用方传入的参数值。
        deps: 调用方传入的参数值。
        include_full_trajectory: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    orbit = deps.build_orbit(payload)
    if getattr(orbit, "period", None) is None:
        raise ValueError(f"unable to determine {config.orbit_type} orbit period")
    dynamics = deps.build_dynamics(config)
    reference_et = deps.reference_et(config)
    t_patch_syn, states_syn = deps.sample_patch_points(orbit, config.patch_points)
    t_patch_j2000, states_j2000 = deps.convert_to_j2000(
        t_patch_syn, states_syn, reference_et
    )
    correction = deps.correct_patch_points(config, dynamics, t_patch_j2000, states_j2000)
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


def default_conversion_dependencies() -> ConversionDependencies:
    """执行 default_conversion_dependencies 对应的处理逻辑。
    
    Returns:
        函数执行结果。
    """
    from e2m2e.algorithms import convert_to_j2000, sample_patch_points
    from e2m2e.core import (
        CR3BP_System,
        EphemerisDynamics,
        EphemerisSystem,
        Orbit,
        SPICEManager,
        SynodicJ2000Transformation,
    )
    import spiceypy

    from tod.commons.constants import MU, TU
    from tod.generates.ephemeris._corrector import correct_ephemeris_patch_points

    spice = SPICEManager()
    cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    def build_orbit(payload: dict[str, Any]) -> Any:
        """构建运行所需对象。
        
        Args:
            payload: 调用方传入的参数值。
        
        Returns:
            函数执行结果。
        """
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as file:
            json.dump(payload, file)
            temp_path = Path(file.name)
        try:
            return Orbit.load_from_file(filename=temp_path, system=cr3bp_system)
        finally:
            temp_path.unlink(missing_ok=True)

    def build_dynamics(config: SingleConversionConfig | FamilyConversionConfig) -> Any:
        """构建脚本所需的动力学模型。
        
        Args:
            config: 调用方传入的参数值。
        
        Returns:
            函数执行结果。
        """
        kernel_path = spice.find_ephemeris_kernel(str(config.spice_kernel_dir))
        leapseconds_path = config.spice_kernel_dir / "naif0012.tls"
        spiceypy.furnsh(str(leapseconds_path))
        spice.load_kernel(kernel_path)
        eph_system = EphemerisSystem(
            bodies=list(config.bodies),
            spice=spice,
            origin="EARTH",
            frame="J2000",
        )
        return EphemerisDynamics(system=eph_system)

    def reference_et(config: SingleConversionConfig | FamilyConversionConfig) -> float:
        """执行 reference_et 对应的处理逻辑。
        
        Args:
            config: 调用方传入的参数值。
        
        Returns:
            函数执行结果。
        """
        return float(spice.utc_to_et(config.reference_epoch))

    def convert_states(t_patch_syn: Any, states_syn: Any, reference_et_value: float) -> tuple[Any, Any]:
        """执行 convert_states 对应的处理逻辑。
        
        Args:
            t_patch_syn: 调用方传入的参数值。
            states_syn: 调用方传入的参数值。
            reference_et_value: 调用方传入的参数值。
        
        Returns:
            函数执行结果。
        """
        transform = SynodicJ2000Transformation(cr3bp_system=cr3bp_system, spice=spice)
        return convert_to_j2000(t_patch_syn, states_syn, transform, reference_et_value, TU)

    def correct(
        config: SingleConversionConfig | FamilyConversionConfig,
        dynamics: Any,
        t_patch_j2000: Any,
        states_j2000: Any,
    ) -> Any:
        """执行 correct 对应的处理逻辑。
        
        Args:
            config: 调用方传入的参数值。
            dynamics: 调用方传入的参数值。
            t_patch_j2000: 调用方传入的参数值。
            states_j2000: 调用方传入的参数值。
        
        Returns:
            函数执行结果。
        """
        return correct_ephemeris_patch_points(
            config.method,
            dynamics,
            t_patch_j2000,
            states_j2000,
            tolerance=config.position_tol,
            max_iter=50,
            verbose=True,
            n_workers=config.per_orbit_workers,
            kernel_dir=str(config.spice_kernel_dir),
            velocity_tolerance=config.velocity_tol,
        )

    return ConversionDependencies(
        build_orbit=build_orbit,
        build_dynamics=build_dynamics,
        reference_et=reference_et,
        sample_patch_points=sample_patch_points,
        convert_to_j2000=convert_states,
        correct_patch_points=correct,
        finalize=spiceypy.kclear,
    )


def main_single(orbit_type: str, argv: list[str] | None = None) -> dict[str, Any]:
    """执行 main_single 对应的处理逻辑。
    
    Args:
        orbit_type: 调用方传入的参数值。
        argv: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    parser = build_single_parser(orbit_type)
    return run_single_conversion(single_config_from_args(parser.parse_args(argv), orbit_type))


def main_family(orbit_type: str, argv: list[str] | None = None) -> dict[str, Any]:
    """执行 main_family 对应的处理逻辑。
    
    Args:
        orbit_type: 调用方传入的参数值。
        argv: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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


def load_family_payloads(input_file: Path) -> list[dict[str, Any]]:
    """读取轨道族文件中的全部轨道载荷。
    
    Args:
        input_file: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
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
    """运行对应计算流程。
    
    Args:
        payloads: 调用方传入的参数值。
        config: 调用方传入的参数值。
        include_full_trajectory: 调用方传入的参数值。
        family_workers: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    entries: list[dict[str, Any] | None] = [None] * len(payloads)
    with ProcessPoolExecutor(max_workers=family_workers) as executor:
        futures = {
            executor.submit(
                _convert_family_payload_with_default_dependencies,
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


def _convert_family_payload_with_default_dependencies(
    payload: dict[str, Any],
    index: int,
    config: FamilyConversionConfig,
    include_full_trajectory: bool,
) -> dict[str, Any]:
    deps = default_conversion_dependencies()
    try:
        return convert_orbit(payload, config, deps, include_full_trajectory)
    finally:
        if deps.finalize is not None:
            deps.finalize()


def run_family_payload_conversion(
    payloads: list[dict[str, Any]],
    convert: Callable[[dict[str, Any], int, bool], dict[str, Any]],
    *,
    fail_fast: bool,
    include_full_trajectory: bool,
    family_workers: int = 1,
) -> list[dict[str, Any]]:
    """运行对应计算流程。
    
    Args:
        payloads: 调用方传入的参数值。
        convert: 调用方传入的参数值。
        fail_fast: 调用方传入的参数值。
        include_full_trajectory: 调用方传入的参数值。
        family_workers: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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


def _validate_continuity(
    dynamics: Any,
    corrected_times: list[float],
    corrected_states: list[list[float]],
    include_full_trajectory: bool,
) -> dict[str, Any]:
    position_errors = []
    full_states = []
    full_times = []
    for index in range(max(0, len(corrected_states) - 1)):
        propagation = dynamics.propagate(
            corrected_states[index],
            (corrected_times[index], corrected_times[index + 1]),
        )
        propagated_states = _to_nested_list(propagation["states"])
        propagated_times = _to_list(propagation["time"])
        position_errors.append(
            _position_error(propagated_states[-1], corrected_states[index + 1])
        )
        if include_full_trajectory:
            if index > 0:
                propagated_states = propagated_states[1:]
                propagated_times = propagated_times[1:]
            full_states.extend(propagated_states)
            full_times.extend(propagated_times)
    return {
        "position_errors_km": position_errors,
        "full_trajectory_states": full_states,
        "full_trajectory_times_et": full_times,
    }


def _position_error(left_state: list[float], right_state: list[float]) -> float:
    return sum(
        (float(left_state[index]) - float(right_state[index])) ** 2 for index in range(3)
    ) ** 0.5


def _to_list(values: Any) -> list[float]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    return [float(value) for value in values]


def _to_nested_list(values: Any) -> list[list[float]]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    return [[float(item) for item in row] for row in values]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_float_list(values: Any) -> list[float] | None:
    if values is None:
        return None
    return [float(value) for value in values]


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
