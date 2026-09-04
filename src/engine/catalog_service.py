"""catalog 服务 -- e2m2e 轨道库与 GUI Artifact 模型的接缝（issue #375）。

清单与多维过滤来自 Catalog ``catalog_query``（摘要，轻量）；单条产物的完整
内容（含数组段）经 ``catalog_get`` 懒加载进 Artifact，四槽位可视化契约
（ADR 0013）由星历段重建（times_et 不落盘，按 UTC 拆分重建）。谱系读记录
的 ``source_record_id``（重启不断，断链由 Project 标记）；教学标注与子集
导出直通 ``catalog_tag`` / ``catalog_export``。

design_orbit / orbit_family_generation / control_orbit 的产物经 Facade
自动入库（e2m2e 5.8.0，ADR 0031 决策 8），本服务只读不重算。e2m2e 5.9.3
起一轨一记录（ADR 0045）：族成员逐条入库，成员记录是单条轨道（顶层
cr3bp/states，周期成员单点初态 + scalars.period），摘要携带 family_id /
member_index；catalog_promote 随之移除（成员本就是独立记录）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np

from src.engine.exceptions import OrbitError
from src.engine.facade_bridge import (
    _FAMILY_DISPLAY_NAMES,
    FacadeBridge,
    _ephemeris_table_from_mapping,
    _reconstruct_et_from_utc,
    centroid_normalized_states,
    resample_periodic_member,
)
from src.model.artifact import Artifact

#: catalog source_tool -> GUI artifact_type（未知的按 orbit 兜底）。5.9.3 起
#: 族成员记录（orbit_family_generation）也是单条轨道，走 orbit 兜底。
_ARTIFACT_TYPE_BY_TOOL = {
    "design_orbit": "orbit",
    "control_orbit": "ephemeris",
}


def _parse_created_at(text: str) -> datetime:
    """解析记录的 ISO 时间戳；坏值回退当前时间（列表序不受影响）。"""
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def record_to_artifact(summary: Any) -> Artifact:
    """把 ``CatalogRecordSummary`` 映射为项目树用的 Artifact（不含数组段）。

    ``artifact_id`` 取 ``record_id``（catalog 记录是唯一标识），谱系断链的
    判定因此可直接走 ``Project.get_by_id``。族维度（family_id /
    member_index）进 extra，供按族分组与整族查询。
    """
    record_id = summary.record_id
    family = summary.orbit_family or ""
    display = _FAMILY_DISPLAY_NAMES.get(family, family)
    tool = summary.source_tool
    atype = _ARTIFACT_TYPE_BY_TOOL.get(tool, "orbit")
    lp = summary.libration_point
    lp_txt = f"L{lp}" if lp else ""
    if atype == "ephemeris":
        scope = f"{display} {lp_txt}" if family and lp_txt else (family or "")
        label = f"受控星历（{scope}）" if scope else "受控星历"
    else:
        prefix = f"{lp_txt}, " if lp_txt else ""
        jacobi = summary.jacobi[0] if summary.jacobi else None
        label = (
            f"{display} ({prefix}C_J={jacobi:.4f})" if jacobi is not None else display or record_id
        )
    return Artifact(
        artifact_id=record_id,
        record_id=record_id,
        artifact_type=atype,
        label=label,
        orbit_type=display,
        source_tool=tool,
        created_at=_parse_created_at(summary.created_at),
        extra={
            "record_id": record_id,
            "source_record_id": summary.source_record_id,
            "family_id": summary.family_id,
            "member_index": summary.member_index,
            "orbit_family": family,
            "libration_point": lp,
            "jacobi": summary.jacobi,
            "amplitude": summary.amplitude,
            "has_cr3bp": summary.has_cr3bp,
            "has_ephemeris": summary.has_ephemeris,
            "status": getattr(summary.status, "value", str(summary.status)),
            "tags": list(summary.tags),
            "note": summary.note,
        },
    )


def _eph_segment(arrays: dict) -> dict:
    """星历段数组（eph/ 前缀剥离）+ 重建的 times_et（ADR 0013 四槽位数据源）。"""
    eph = {k[len("eph/") :]: np.asarray(v) for k, v in arrays.items() if k.startswith("eph/")}
    eph["times_et"] = _reconstruct_et_from_utc(_ephemeris_table_from_mapping(eph))
    return eph


def _fill_design(artifact: Artifact, response: Any, arrays: dict, scalars: dict) -> None:
    """design_orbit 记录：CR3BP 段 + 星历段双段懒加载。"""
    states = arrays.get("cr3bp/states")
    times = arrays.get("cr3bp/times")
    if states is not None and np.asarray(states).size:
        artifact.state_data = np.asarray(states, dtype=float)
        artifact.times = np.asarray(times, dtype=float)
    if "eph/year" in arrays:
        artifact.extra["ephemeris"] = _eph_segment(arrays)
    artifact.extra["epoch_utc"] = scalars.get("epoch_utc")
    if response.jacobi:
        artifact.extra["cr3bp_jacobi"] = response.jacobi[0]


def _fill_family_member(artifact: Artifact, response: Any, arrays: dict, scalars: dict) -> None:
    """族成员记录（一轨一记录，ADR 0045）：顶层 cr3bp/states 即该成员轨迹。

    周期成员只携带单点初态 (1,6) 与 scalars.period，按周期重采样到固定点数
    （画布契约）；自带完整轨迹（Lissajous 拟周期）原样采用。
    """
    states = arrays.get("cr3bp/states")
    if states is None or not np.asarray(states).size:
        return
    states = np.asarray(states, dtype=float)
    times = np.asarray(arrays.get("cr3bp/times"), dtype=float)
    period = scalars.get("period")
    if states.shape[0] == 1 and period:
        from e2m2e.algorithm.dynamics import CR3BP_Dynamics
        from e2m2e.data.templates.seed import EARTH_MOON_MU

        from src.engine.viz_adapter import build_cr3bp_system

        mu = scalars.get("mu")
        dynamics = CR3BP_Dynamics(build_cr3bp_system(mu if mu is not None else EARTH_MOON_MU))
        states, times = resample_periodic_member(dynamics, states[0], period)
    artifact.state_data = states
    artifact.times = times
    if (artifact.extra.get("orbit_family") or "") == "halo":
        artifact.extra["z0"] = float(states[0, 2])
    artifact.extra["family_type"] = artifact.extra.get("orbit_family") or ""
    artifact.extra["periodicity"] = scalars.get("periodicity", "periodic")


def _fill_control(artifact: Artifact, arrays: dict, scalars: dict) -> None:
    """站保记录：星历段减 μ 对齐画布质心归一；机动统计进 extra。"""
    syn = arrays.get("eph/synodic_position")
    mu = scalars.get("mu")
    if syn is not None:
        artifact.state_data = centroid_normalized_states(syn, mu)
        eph = _eph_segment(arrays)
        artifact.times = eph["times_et"]
        artifact.extra["times_et"] = eph["times_et"]
        artifact.extra["position_km"] = eph.get("position_km")
        # GCRS 速度（km/s）：轨道预报初值预填需要末端速度（#389）；记录里存的是 m/s
        velocity_mps = eph.get("velocity_mps")
        artifact.extra["velocity_km_s"] = (
            np.asarray(velocity_mps, dtype=float) / 1000.0 if velocity_mps is not None else None
        )
    artifact.extra["num_failed"] = scalars.get("num_failed")
    artifact.extra["total_delta_v_mps"] = scalars.get("delta_v_total_mps")
    maneuvers = arrays.get("result/maneuvers_mjd_tdb")
    artifact.extra["n_maneuvers"] = int(np.asarray(maneuvers).size) if maneuvers is not None else 0


def _fill_artifact_from_record(artifact: Artifact, response: Any) -> None:
    """把完整记录（catalog_get 响应）原地填进 Artifact（懒加载契约）。"""
    arrays = response.arrays or {}
    scalars = response.scalars or {}
    mu = scalars.get("mu")
    if mu is not None:
        artifact.extra["mu"] = mu
    if response.source_tool == "orbit_family_generation":
        _fill_family_member(artifact, response, arrays, scalars)
    elif response.source_tool == "control_orbit":
        _fill_control(artifact, arrays, scalars)
    else:
        _fill_design(artifact, response, arrays, scalars)


class CatalogService:
    """轨道库的 GUI 语义层：清单查询、记录懒加载、标注 / 导出 / 删除。"""

    def __init__(self, bridge: FacadeBridge) -> None:
        self._bridge = bridge

    def query_artifacts(self, filters: dict | None = None) -> list[Artifact]:
        """按多维过滤查询库中记录，返回项目树用的 Artifact 列表。"""
        summaries = self._bridge.catalog_query(**(filters or {}))
        return [record_to_artifact(summary) for summary in summaries]

    def load_arrays(self, artifact: Artifact) -> bool:
        """按 record_id 取完整记录并原地填进 Artifact。

        失败不抛异常（记录被并发删除、文件损坏等），返回 False 由调用方降级。
        """
        if not artifact.record_id:
            return False
        try:
            response = self._bridge.catalog_get(artifact.record_id)
        except OrbitError:
            return False
        _fill_artifact_from_record(artifact, response)
        return artifact.state_data is not None

    def tag(self, record_id: str, tags: list[str], note: str | None = None) -> None:
        """写教学标注（tags 整体替换；note 为 None 时保留原注释）。"""
        self._bridge.catalog_tag(record_id, tags=tags, note=note)

    def delete(self, record_id: str) -> None:
        """删除记录（不可撤销，ADR 0008 既定不做回收站）。"""
        self._bridge.catalog_delete(record_id)

    def export(self, filters: dict | None, dest: str) -> int:
        """把过滤子集打包导出（dest 以 .zip 结尾出 zip，否则出目录）。"""
        return self._bridge.catalog_export(dest=dest, **(filters or {}))
