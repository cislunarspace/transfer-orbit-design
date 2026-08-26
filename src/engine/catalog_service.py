"""catalog 服务 -- e2m2e 轨道库与 GUI Artifact 模型的接缝（issue #375）。

清单与多维过滤来自 Facade ``catalog_query``（摘要，轻量）；单条产物的完整
内容（含数组段）经 ``catalog_get`` 懒加载进 Artifact，四槽位可视化契约
（ADR 0013）由星历段重建（times_et 不落盘，按 UTC 拆分重建）。谱系读记录
的 ``source_record_id``（重启不断，断链由 Project 标记）；教学标注与子集
导出直通 ``catalog_tag`` / ``catalog_export``。

design_orbit / orbit_family_generation / control_orbit 的产物经 Facade
自动入库（e2m2e 5.8.0，ADR 0031 决策 8），本服务只读不重算。

English: catalog service -- the seam between the e2m2e orbit library and
the GUI Artifact model (issue #375). The inventory and multi-dimensional
filters come from Facade ``catalog_query`` (summaries, lightweight); a
single product's full content (including array segments) is lazily
loaded into an Artifact via ``catalog_get``, with the four-slot
visualization contract (ADR 0013) rebuilt from the ephemeris segment
(times_et is not persisted; rebuilt from the UTC split). Lineage reads
the record's ``source_record_id`` (survives restarts; broken links are
flagged by Project); teaching annotations and subset exports pass
straight through ``catalog_tag`` / ``catalog_export``. Products of
design_orbit / orbit_family_generation / control_orbit auto-ingest via
the Facade (e2m2e 5.8.0, ADR 0031 decision 8); this service only reads,
never recomputes.
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

#: catalog source_tool -> GUI artifact_type（未知的按 orbit 兜底）。
#: catalog source_tool -> GUI artifact_type (unknown tools fall back to "orbit").
_ARTIFACT_TYPE_BY_TOOL = {
    "design_orbit": "orbit",
    "catalog_promote": "orbit",
    "orbit_family_generation": "family",
    "control_orbit": "ephemeris",
}


def _parse_created_at(text: str) -> datetime:
    """解析记录的 ISO 时间戳；坏值回退当前时间（列表序不受影响）。

    Parse the record's ISO timestamp; fall back to the current time on bad
    values (list order unaffected).
    """
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def record_to_artifact(summary: Any) -> Artifact:
    """把 ``CatalogRecordSummary`` 映射为项目树用的 Artifact（不含数组段）。

    ``artifact_id`` 取 ``record_id``（catalog 记录是唯一标识），谱系断链的
    判定因此可直接走 ``Project.get_by_id``。

    Map a ``CatalogRecordSummary`` to a project-tree Artifact (no array
    segments). ``artifact_id`` takes the ``record_id`` (the catalog
    record is the unique identifier), so broken-lineage detection can go
    straight through ``Project.get_by_id``.
    """
    record_id = summary.record_id
    family = summary.orbit_family or ""
    display = _FAMILY_DISPLAY_NAMES.get(family, family)
    tool = summary.source_tool
    atype = _ARTIFACT_TYPE_BY_TOOL.get(tool, "orbit")
    lp = summary.libration_point
    lp_txt = f"L{lp}" if lp else ""
    if atype == "family":
        prefix = f"{lp_txt}, " if lp_txt else ""
        label = f"{display} 族 ({prefix}{summary.member_count} 条)"
    elif atype == "ephemeris":
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
            "orbit_family": family,
            "libration_point": lp,
            "jacobi": summary.jacobi,
            "amplitude": summary.amplitude,
            "has_cr3bp": summary.has_cr3bp,
            "has_ephemeris": summary.has_ephemeris,
            "member_count": summary.member_count,
            "status": getattr(summary.status, "value", str(summary.status)),
            "tags": list(summary.tags),
            "note": summary.note,
        },
    )


def _eph_segment(arrays: dict) -> dict:
    """星历段数组（eph/ 前缀剥离）+ 重建的 times_et（ADR 0013 四槽位数据源）。

    Ephemeris-segment arrays (eph/ prefix stripped) plus the rebuilt times_et
    (the data source of the ADR 0013 four slots).
    """
    eph = {k[len("eph/") :]: np.asarray(v) for k, v in arrays.items() if k.startswith("eph/")}
    eph["times_et"] = _reconstruct_et_from_utc(_ephemeris_table_from_mapping(eph))
    return eph


def _fill_design(artifact: Artifact, response: Any, arrays: dict, scalars: dict) -> None:
    """design_orbit / catalog_promote 记录：CR3BP 段 + 星历段双段懒加载。

    design_orbit / catalog_promote records: both the CR3BP segment and the
    ephemeris segment load lazily.
    """
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


def _fill_family(artifact: Artifact, response: Any, arrays: dict, scalars: dict) -> None:
    """族记录：成员数组堆叠 (m, n, 6)；周期成员按周期重采样（画布契约）。

    Family records: member arrays stacked (m, n, 6); periodic members resampled
    per period (the canvas contract).
    """
    members = response.members or []
    mu = scalars.get("mu")
    dynamics = None
    states_list: list[Any] = []
    times_list: list[Any] = []
    z0s: list[float] = []
    for index, member in enumerate(members):
        raw_states = arrays.get(f"cr3bp/members/{index:04d}/states")
        raw_times = arrays.get(f"cr3bp/members/{index:04d}/times")
        if raw_states is None:
            continue
        states = np.asarray(raw_states, dtype=float)
        times = np.asarray(raw_times, dtype=float)
        z0s.append(float(states[0, 2]))
        period = member.get("period")
        if states.shape[0] == 1 and period:
            if dynamics is None:
                from e2m2e.algorithm.dynamics import CR3BP_Dynamics
                from e2m2e.data.templates.seed import EARTH_MOON_MU

                from src.engine.viz_adapter import build_cr3bp_system

                dynamics = CR3BP_Dynamics(
                    build_cr3bp_system(mu if mu is not None else EARTH_MOON_MU)
                )
            states, times = resample_periodic_member(dynamics, states[0], period)
        states_list.append(states)
        times_list.append(times)
    if states_list:
        artifact.state_data = np.stack(states_list)
        artifact.times = np.stack(times_list)
        if (artifact.extra.get("orbit_family") or "") == "halo":
            artifact.extra["z0s"] = np.array(z0s)
    artifact.extra["members"] = members
    artifact.extra["member_parameters"] = [dict(m.get("parameters") or {}) for m in members]
    artifact.extra["family_type"] = artifact.extra.get("orbit_family") or ""
    artifact.extra["periodicity"] = scalars.get("periodicity", "periodic")


def _fill_control(artifact: Artifact, arrays: dict, scalars: dict) -> None:
    """站保记录：星历段减 μ 对齐画布质心归一；机动统计进 extra。

    Station-keeping records: ephemeris segment shifted by μ to the canvas
    barycenter normalization; maneuver statistics go into extra.
    """
    syn = arrays.get("eph/synodic_position")
    mu = scalars.get("mu")
    if syn is not None:
        artifact.state_data = centroid_normalized_states(syn, mu)
        eph = _eph_segment(arrays)
        artifact.times = eph["times_et"]
        artifact.extra["times_et"] = eph["times_et"]
        artifact.extra["position_km"] = eph.get("position_km")
        # GCRS 速度（km/s）：轨道预报初值预填需要末端速度（#389）；记录里存的是 m/s
        # GCRS velocity (km/s): propagation prefill needs terminal velocity (#389);
        # records store m/s.
        velocity_mps = eph.get("velocity_mps")
        artifact.extra["velocity_km_s"] = (
            np.asarray(velocity_mps, dtype=float) / 1000.0 if velocity_mps is not None else None
        )
    artifact.extra["num_failed"] = scalars.get("num_failed")
    artifact.extra["total_delta_v_mps"] = scalars.get("delta_v_total_mps")
    maneuvers = arrays.get("result/maneuvers_mjd_tdb")
    artifact.extra["n_maneuvers"] = int(np.asarray(maneuvers).size) if maneuvers is not None else 0


def _fill_artifact_from_record(artifact: Artifact, response: Any) -> None:
    """把完整记录（catalog_get 响应）原地填进 Artifact（懒加载契约）。

    Fill the full record (catalog_get response) into the Artifact in place
    (the lazy-loading contract).
    """
    arrays = response.arrays or {}
    scalars = response.scalars or {}
    mu = scalars.get("mu")
    if mu is not None:
        artifact.extra["mu"] = mu
    if response.source_tool == "orbit_family_generation":
        _fill_family(artifact, response, arrays, scalars)
    elif response.source_tool == "control_orbit":
        _fill_control(artifact, arrays, scalars)
    else:  # design_orbit / catalog_promote
        _fill_design(artifact, response, arrays, scalars)


class CatalogService:
    """轨道库的 GUI 语义层：清单查询、记录懒加载、标注 / 提升 / 导出 / 删除。

    The GUI semantic layer over the orbit library: inventory queries, lazy
    record loading, annotation / promotion / export / deletion.
    """

    def __init__(self, bridge: FacadeBridge) -> None:
        self._bridge = bridge

    def query_artifacts(self, filters: dict | None = None) -> list[Artifact]:
        """按多维过滤查询库中记录，返回项目树用的 Artifact 列表。

        Query catalog records with multi-dimensional filters; returns an
        Artifact list for the project tree.
        """
        summaries = self._bridge.catalog_query(**(filters or {}))
        return [record_to_artifact(summary) for summary in summaries]

    def load_arrays(self, artifact: Artifact) -> bool:
        """按 record_id 取完整记录并原地填进 Artifact。

        失败不抛异常（记录被并发删除、文件损坏等），返回 False 由调用方降级。

        Fetch the full record by record_id and fill the Artifact in place.
        Failures do not raise (concurrent deletion, corrupted files,
        etc.); False is returned for the caller to degrade gracefully.
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
        """写教学标注（tags 整体替换；note 为 None 时保留原注释）。

        Write teaching annotations (tags replaced wholesale; note=None keeps the
        existing note).
        """
        self._bridge.catalog_tag(record_id, tags=tags, note=note)

    def delete(self, record_id: str) -> None:
        """删除记录（不可撤销，ADR 0008 既定不做回收站）。

        Delete a record (irreversible; ADR 0008 deliberately ships no recycle bin).
        """
        self._bridge.catalog_delete(record_id)

    def promote_member(self, record_id: str, member_index: int) -> str:
        """把族成员提升为独立记录，返回新记录的 record_id。

        Promote a family member to a standalone record; returns the new record's
        record_id.
        """
        return self._bridge.catalog_promote(record_id, member_index)

    def export(self, filters: dict | None, dest: str) -> int:
        """把过滤子集打包导出（dest 以 .zip 结尾出 zip，否则出目录）。

        Package and export the filtered subset (a .zip dest yields a zip,
        otherwise a directory).
        """
        return self._bridge.catalog_export(dest=dest, **(filters or {}))
