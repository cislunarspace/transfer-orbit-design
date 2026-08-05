r"""结果持久化 -- 将 DTO 写入 output/ 目录。

双文件方案（ADR 对齐）：
- dro_<YYYYMMDDHHMMSS>.json -- 标量元数据
- dro_<YYYYMMDDHHMMSS>.npz  -- states + times + ephemeris（numpy 压缩）

文件命名与 discovery.py 的 ``_DRO_ORBIT_RE = r"^dro_\d+\.json$"`` 兼容。
轨道保持结果写入 output/ephemeris/，命名 ``orbit_ephemeris_<ts>``。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.engine.facade_bridge import ControlResultData, OrbitDesignResultData
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


def save_artifact(
    result_data: OrbitDesignResultData,
    output_dir: Path,
) -> tuple[Path, Path]:
    """将计算结果写入 output/dro/ 目录，返回 ``(json_path, npz_path)`` 元组。

    文件名格式 ``dro_<14位时间戳>``，与 discovery 正则兼容。
    NPZ 文件名由 persistence 单一来源生成，避免调用方重复推导。

    Returns:
        ``(json_path, npz_path)`` 元组。调用方应使用 ``npz_path.name``
        作为 ``arrays_file`` 元数据键，避免再次 ``with_suffix(".npz").name``。
    """
    output_dir = Path(output_dir)
    dro_dir = output_dir / "dro"
    dro_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    stem = f"dro_{ts}"
    json_path = dro_dir / f"{stem}.json"
    npz_path = dro_dir / f"{stem}.npz"

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
            )
            eph: dict = {}
            for k in eph_keys:
                arr_key = f"eph_{k}"
                if arr_key in data:
                    eph[k] = data[arr_key]
            if eph:
                artifact.extra.setdefault("ephemeris", eph)
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
        np.savez_compressed(
            npz_path,
            states=result_data.controlled_states,
            times=result_data.controlled_times,
        )

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
