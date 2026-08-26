r"""结果持久化 -- catalog 之外的产物落盘（issue #375）。

    Result persistence -- products written
outside the catalog (issue #375).

e2m2e 5.8.0 起 design_orbit / orbit_family_generation / control_orbit 的
产物经 Facade 自动入轨道库 catalog（手写 JSON+NPZ 落盘已随本仓 ADR 0008
修订退役），本模块只剩 catalog 分类体系之外的产物：

- 稳定性分析（``save_stability_result``）：只落 JSON 到 output/stability/，
  不进项目树/画布。
- 转移轨道设计（``save_transfer_result``）：落 JSON 到 output/transfer/，
  经遗留分区扫描进项目树（e2m2e 对 transfer 产物入库另行立项）。
- 轨道预报（``save_propagation_result``，issue #389）：e2m2e 未提供该工具
  的产物入库，星历落 JSON 到 output/propagation/，重启经 discovery 恢复。

画布与动画录制产生的临时文件不在此列。

English: result persistence -- products written outside the catalog (issue
#375). Since e2m2e 5.8.0, design_orbit / orbit_family_generation /
control_orbit products auto-ingest into the orbit catalog through the
Facade (hand-written JSON+NPZ persistence was retired with the revision
of this repo's ADR 0008); this module retains only products outside the
catalog taxonomy: stability analysis
(``save_stability_result``) — JSON only under output/stability/, never
entering the project tree or canvas; transfer design
(``save_transfer_result``) — JSON under output/transfer/, entering the
project tree via the legacy-partition scan (e2m2e tracks catalog
ingestion for transfer products separately); orbit propagation
(``save_propagation_result``, issue #389) — e2m2e provides no ingestion
for this tool, so the ephemeris lands as JSON under output/propagation/
and is restored by discovery on restart. Temporary files produced by
the canvas and animation recording are out of scope.
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
        PropagationResultData,
        StabilityResultData,
        TransferDesignResultData,
    )


def _timestamp() -> str:
    """生成 UTC 时间戳字符串 ``YYYYMMDDHHMMSS``。

    Generate a UTC timestamp string ``YYYYMMDDHHMMSS``.
    """
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


def save_stability_result(
    result_data: StabilityResultData,
    output_dir: Path,
    *,
    orbit_label: str,
) -> Path:
    """将稳定性分析结果写入 output/stability/，返回 json_path。

    结果只落盘 JSON（不进项目树/画布）；数组字段 tolist 序列化。文件名
    ``<orbit_label>_stability_<ts>``（orbit_label 清洗为安全文件名字符）。

    Write a stability-analysis result to output/stability/ and return the
    json_path. Only JSON is written (not entering the project tree or
    canvas); array fields serialize via tolist. Filename
    ``<orbit_label>_stability_<ts>`` (orbit_label sanitized into safe
    filename characters).
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
            # JSON has no native complex representation -> [real, imag].
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


def save_transfer_result(
    result_data: TransferDesignResultData,
    output_dir: Path,
) -> Path:
    """将转移轨道设计结果写入 output/transfer/，返回 json_path。

    文件名 ``transfer_design_<ts>.json``（遗留分区扫描正则匹配）；轨迹以
    ``states`` 键写入（同目录扫描的既有约定），地心惯性系 km / km/s。

    Write a transfer-design result to output/transfer/ and return the
    json_path. Filename ``transfer_design_<ts>.json`` (matched by the
    legacy-partition scan regex); the trajectory is written under the
    ``states`` key (the existing convention of the same-directory scan),
    Earth-centered inertial km / km/s.
    """
    output_dir = Path(output_dir)
    transfer_dir = output_dir / "transfer"
    transfer_dir.mkdir(parents=True, exist_ok=True)
    json_path = transfer_dir / f"transfer_design_{_timestamp()}.json"

    def _ser(v: Any) -> Any:
        from enum import Enum

        if isinstance(v, Enum):
            return v.value
        if isinstance(v, np.ndarray):
            return _ser(v.tolist())
        if isinstance(v, complex):
            return [v.real, v.imag]
        if isinstance(v, dict):
            return {k: _ser(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_ser(x) for x in v]
        return v

    data = {
        "source_tool": "transfer_design",
        "transfer_type": result_data.transfer_type,
        "delta_v_km_s": result_data.delta_v,
        "converged": result_data.converged,
        "message": result_data.message,
        "states": _ser(result_data.trajectory),
        "details": _ser(result_data.details or {}),
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


def save_propagation_result(
    result_data: PropagationResultData,
    output_dir: Path,
) -> Path:
    """将轨道预报星历写入 output/propagation/，返回 json_path。

    e2m2e 未提供 orbit_propagation 的 catalog 入库，产物落 JSON（数组
    tolist），重启后由 ``model.discovery`` 扫描恢复进项目树。文件名
    ``propagation_<ts>``（同时作为恢复后的 artifact_id，供运行后选中）。

    Write a propagation ephemeris to output/propagation/ and return the
    json_path. e2m2e provides no catalog ingestion for orbit_propagation,
    so the product lands as JSON (arrays tolist) and is restored into the
    project tree by ``model.discovery`` on restart. Filename
    ``propagation_<ts>`` (also serving as the restored artifact_id, so
    the run result can be selected afterwards).
    """
    output_dir = Path(output_dir)
    prop_dir = output_dir / "propagation"
    prop_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    json_path = prop_dir / f"propagation_{ts}.json"
    payload = {
        "source_tool": "orbit_propagation",
        "label": f"轨道预报 {result_data.epoch_utc}",
        "epoch_utc": result_data.epoch_utc,
        "duration_sec": result_data.duration_sec,
        "mu": result_data.mu,
        "times_et": np.asarray(result_data.times_et).tolist(),
        "position_km": np.asarray(result_data.position_km).tolist(),
        "velocity_km_s": np.asarray(result_data.velocity_km_s).tolist(),
        "synodic_position": np.asarray(result_data.synodic_position).tolist(),
        "final_state": np.asarray(result_data.final_state).tolist(),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return json_path
