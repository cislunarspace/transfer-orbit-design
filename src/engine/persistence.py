r"""结果持久化 -- 将 DTO 写入 output/ 目录。

双文件方案（ADR 对齐），按轨道类型分目录：
- output/dro/   dro_<YYYYMMDDHHMMSS>.json/npz   -- DRO 轨道
- output/halo/  halo_<YYYYMMDDHHMMSS>.json/npz   -- Halo 轨道
- output/nrho/  nrho_<YYYYMMDDHHMMSS>.json/npz   -- NRHO 轨道
- output/<type>/ <type>_<ts>.json/npz            -- 其余轨道类型（Lissajous/L4/L5/Axial 等）

目录名与文件名前缀均由 ``orbit_type`` 归一化派生（小写），与 discovery.py
按「目录 + 前缀」分类的约定一致。曾无条件写 ``output/dro/dro_<ts>``，导致
Halo 等非 DRO 轨道落盘成 DRO 文件、被 discovery 误分类（回归测试
``TestSaveArtifactOrbitTypeNaming``）。轨道保持结果写入 output/ephemeris/，
命名 ``orbit_ephemeris_<ts>``。
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from src.engine.facade_bridge import (
        ControlResultData,
        FamilyResultData,
        OrbitDesignResultData,
        StabilityResultData,
    )
    from src.model.artifact import Artifact


def _timestamp() -> str:
    """生成 UTC 时间戳字符串 ``YYYYMMDDHHMMSS``。"""
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


def _extract_mu(result_data: OrbitDesignResultData) -> float | None:
    """从结果 DTO 提取 CR3BP 质量比 mu。

    兼容新旧结果数据：新版 DTO 带 ``mu`` 字段；旧版（无 mu 字段）返回 None，
    画布据此跳过地月/L 点标注而非崩溃。
    """
    return getattr(result_data, "mu", None)


def _orbit_type_dirname(orbit_type: str) -> str:
    """轨道类型 → 输出子目录名（小写）。

    GUI 可选类型为 DRO/Halo/NRHO/Lissajous/L4/L5（e2m2e
    ``DesignOrbitRequest.orbit_type`` description），归一化为小写即目录名
    （dro/halo/nrho/lissajous/l4/l5）。算法层返回的 orbit_type 为全大写
    （HALO），统一转小写兜底。
    """
    return orbit_type.lower()


def _orbit_type_stem(orbit_type: str) -> str:
    """轨道类型 → 文件名前缀（小写），DRO 兼容旧布局 ``dro_<ts>``。"""
    return orbit_type.lower()


def save_artifact(
    result_data: OrbitDesignResultData,
    output_dir: Path,
) -> tuple[Path, Path]:
    """将计算结果写入 output/<type>/ 目录，返回 ``(json_path, npz_path)`` 元组。

    目录与文件名前缀由 ``result_data.orbit_type`` 派生（见
    ``_orbit_type_dirname`` / ``_orbit_type_stem``）。DRO 保持既有布局
    ``output/dro/dro_<14位时间戳>``，与 discovery 正则兼容。
    NPZ 文件名由 persistence 单一来源生成，避免调用方重复推导。

    Returns:
        ``(json_path, npz_path)`` 元组。调用方应使用 ``npz_path.name``
        作为 ``arrays_file`` 元数据键，避免再次 ``with_suffix(".npz").name``。
    """
    output_dir = Path(output_dir)
    type_dir = output_dir / _orbit_type_dirname(result_data.orbit_type)
    type_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    stem = f"{_orbit_type_stem(result_data.orbit_type)}_{ts}"
    json_path = type_dir / f"{stem}.json"
    npz_path = type_dir / f"{stem}.npz"

    npz_payload: dict[str, np.ndarray] = {
        "states": result_data.states,
        "times": result_data.times,
    }
    if result_data.ephemeris is not None:
        for k, v in result_data.ephemeris.items():
            if v is not None:
                npz_payload[f"eph_{k}"] = v
    np.savez_compressed(npz_path, **npz_payload)  # type: ignore[call-arg]

    meta = {
        "orbit_type": result_data.orbit_type,
        "epoch_utc": result_data.epoch_utc,
        "duration_day": result_data.duration_day,
        "cr3bp_jacobi": result_data.cr3bp_jacobi,
        "mu": _extract_mu(result_data),
        "correction_converged": result_data.correction_converged,
        "correction_iterations": result_data.correction_iterations,
        "initial_state": result_data.initial_state.tolist(),
        "states_shape": list(result_data.states.shape),
        "times_count": int(result_data.times.size),
        "arrays_file": npz_path.name,
        "has_ephemeris": result_data.ephemeris is not None,
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return json_path, npz_path


def load_artifact_arrays(artifact: Artifact) -> bool:
    """从 ``artifact.output_path`` 伴随的 NPZ 文件加载 states/times。

    使用 ``with np.load(...)`` 上下文管理器保证文件句柄关闭。
    失败时不抛出异常，仅返回 ``False``，调用方决定如何降级。

    注意：直接修改 ``artifact.state_data`` 和 ``artifact.times``，
    这是性能取舍（Qt-bound model 不希望不可变更新触发复杂刷新）。
    见 ``Artifact`` dataclass 注释。

    Returns:
        加载成功返回 ``True``，否则 ``False``（无 metadata / 文件缺失 / 加载失败）。
    """
    if artifact.output_path is None:
        return False
    npz_name = artifact.extra.get("arrays_file")
    if not npz_name:
        return False
    npz_path = artifact.output_path.parent / npz_name
    if not npz_path.exists():
        return False
    try:
        with np.load(npz_path) as data:
            artifact.state_data = data["states"]
            artifact.times = data["times"]
            eph_keys = (
                "year",
                "month",
                "day",
                "hour",
                "minute",
                "second",
                "position_km",
                "velocity_mps",
                "synodic_position",
                "times_jd_tdb",
                "times_et",
            )
            eph: dict = {}
            for k in eph_keys:
                arr_key = f"eph_{k}"
                if arr_key in data:
                    eph[k] = data[arr_key]
            if eph:
                artifact.extra.setdefault("ephemeris", eph)
            # control_orbit 的 NPZ 存了顶层 position_km/times_et（不带 eph_ 前缀，
            # 因它们不是 EphemerisTable 字段，而是 control_orbit 特有产物），
            # 单独读回 extra。
            for key in ("position_km", "times_et"):
                if key in data:
                    artifact.extra[key] = data[key]
            # family 的 z0s（各族成员面外振幅）与 states 同源，读回 extra 供展示
            if "z0s" in data:
                artifact.extra["z0s"] = data["z0s"]
    except (KeyError, OSError, ValueError):
        return False
    return True


def save_control_result(
    result_data: ControlResultData,
    output_dir: Path,
) -> tuple[Path, Path]:
    """将轨道保持结果写入 output/ephemeris/，返回 ``(json_path, npz_path)``。

    文件名 ``orbit_ephemeris_<ts>``，与 ``discovery._EPHEMERIS_RE`` 兼容。
    全失败（``controlled_states is None``）时不写 NPZ，仅写 JSON 元数据。
    """
    output_dir = Path(output_dir)
    eph_dir = output_dir / "ephemeris"
    eph_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    stem = f"orbit_ephemeris_{ts}"
    json_path = eph_dir / f"{stem}.json"
    npz_path = eph_dir / f"{stem}.npz"

    total_dv = float(np.sum(result_data.maneuvers_delta_v_mps))
    if result_data.controlled_states is not None:
        # position_km/times_et 与 controlled_states 同源（来自 controlled_ephemeris），
        # 故同时存在；与现有"全失败不写 NPZ"语义一致。
        npz_payload: dict[str, np.ndarray] = {
            "states": result_data.controlled_states,
            "times": result_data.controlled_times,
        }
        if result_data.position_km is not None:
            npz_payload["position_km"] = result_data.position_km
        if result_data.times_et is not None:
            npz_payload["times_et"] = result_data.times_et
        np.savez_compressed(npz_path, **npz_payload)  # type: ignore[call-arg]

    meta = {
        "artifact_type": "ephemeris",
        "source_tool": "control_orbit",
        "num_failed": result_data.num_failed,
        "total_delta_v_mps": total_dv,
        "n_maneuvers": int(len(result_data.maneuvers_mjd_tdb)),
        "mu": result_data.mu,
        "states_shape": list(result_data.controlled_states.shape)
        if result_data.controlled_states is not None
        else None,
        "arrays_file": npz_path.name if result_data.controlled_states is not None else None,
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path, npz_path


def save_family_result(
    result_data: FamilyResultData,
    output_dir: Path,
) -> tuple[Path, Path]:
    """将轨道族生成结果写入 output/family/，返回 ``(json_path, npz_path)``。

    文件名 ``family_<ts>``，与 discovery 的 family 识别约定兼容。
    NPZ 存各族成员的三维数组：``states (m,n,6)`` / ``times (m,n)`` /
    ``z0s (m,)``。
    """
    output_dir = Path(output_dir)
    family_dir = output_dir / "family"
    family_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    stem = f"family_{ts}"
    json_path = family_dir / f"{stem}.json"
    npz_path = family_dir / f"{stem}.npz"

    np.savez_compressed(
        npz_path,  # type: ignore[call-arg]
        states=result_data.states,
        times=result_data.times,
        z0s=result_data.z0s,
    )

    meta = {
        "artifact_type": "family",
        "source_tool": "orbit_family_generation",
        "orbit_type": result_data.orbit_type,
        "libration_point": result_data.libration_point,
        "n_orbits": result_data.n_orbits,
        "mu": result_data.mu,
        "states_shape": list(result_data.states.shape),
        "arrays_file": npz_path.name,
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path, npz_path


def save_stability_result(
    result_data: StabilityResultData,
    output_dir: Path,
    *,
    orbit_label: str,
) -> Path:
    """将稳定性分析结果写入 output/stability/，返回 json_path。

    结果只落盘 JSON（不进项目树/画布，见 main_window 对话框）；数组字段
    tolist 序列化。文件名 ``<orbit_label>_stability_<ts>``（orbit_label 清洗
    为安全文件名字符）。
    """
    output_dir = Path(output_dir)
    stab_dir = output_dir / "stability"
    stab_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    safe_label = re.sub(r"[^\w\-]+", "_", orbit_label).strip("_") or "orbit"
    json_path = stab_dir / f"{safe_label}_stability_{ts}.json"

    def _ser(v: Any) -> Any:
        from enum import Enum

        if isinstance(v, Enum):
            return v.value
        if isinstance(v, np.ndarray):
            return _ser(v.tolist())
        if isinstance(v, complex):
            # json 无 complex 原生表示 → [real, imag]
            return [v.real, v.imag]
        if isinstance(v, dict):
            return {k: _ser(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_ser(x) for x in v]
        return v

    meta = {
        "source_tool": "orbit_stability",
        "orbit_label": orbit_label,
        "monodromy_matrix": _ser(result_data.monodromy_matrix),
        "eigenvalues": _ser(result_data.eigenvalues),
        "stability_indices": result_data.stability_indices,
        "classification": _ser(result_data.classification),
        "bifurcation": _ser(result_data.bifurcation),
        "numerical_errors": result_data.numerical_errors,
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path
