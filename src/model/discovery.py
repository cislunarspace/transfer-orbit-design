"""目录扫描 -- catalog 分类体系之外的产物（issue #375 / #389）。

轨道 / 轨道族 / 星历产物自 e2m2e 5.8.0 起由轨道库 catalog 管理（清单与
过滤经 Facade ``catalog_query``，见 ``engine.catalog_service``），基于
「子目录名 + 文件名正则」的分类已随本仓 ADR 0008 修订（2026-08-19）删除。

仍在目录扫描的分区：

- transfer：转移轨道产物（e2m2e 对 transfer_design 等产物入库另行立项），
  过渡期沿用，待上游入库后退役。
- propagation：轨道预报星历（issue #389），e2m2e 未提供该工具的产物
  入库，落盘见 ``engine.persistence.save_propagation_result``。

English: directory scanning -- products outside the catalog taxonomy
(issues #375 / #389). Orbit / orbit-family / ephemeris products have
been managed by the orbit catalog since e2m2e 5.8.0 (inventory and
filters via Facade ``catalog_query``, see ``engine.catalog_service``);
the "subdirectory name + filename regex" classification was deleted
with this repo's ADR 0008 revision (2026-08-19). Partitions still
scanned: transfer — transfer-orbit products (e2m2e tracks catalog
ingestion of transfer_design etc. separately); kept transitionally,
retiring once upstream ingests them. propagation — propagation
ephemerides (issue #389); e2m2e provides no ingestion for that tool,
see ``engine.persistence.save_propagation_result`` for persistence.
"""

from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from src.model.artifact import Artifact

_TRANSFER_CORRECTED_RE = re.compile(r"^corrected_transfer_.*\.json$")
_TRANSFER_OPTIMIZATION_RE = re.compile(r"^optimization_.*\.json$")
_TRANSFER_DESIGN_RE = re.compile(r"^transfer_design_.*\.json$")
_PROPAGATION_RE = re.compile(r"^propagation_.*\.json$")


def _classify_file(path: Path) -> dict | None:
    """Classify a JSON file into artifact metadata, or None if not recognized.
    把 JSON 文件分类为产物元数据；无法识别返回 None。"""
    name = path.name
    parent = path.parent.name

    if parent == "transfer":
        if _TRANSFER_CORRECTED_RE.match(name):
            return {"artifact_type": "transfer", "source_tool": ""}
        if _TRANSFER_OPTIMIZATION_RE.match(name):
            return {"artifact_type": "transfer", "source_tool": ""}
        if _TRANSFER_DESIGN_RE.match(name):
            return {"artifact_type": "transfer", "source_tool": "transfer_design"}
    elif parent == "propagation":
        if _PROPAGATION_RE.match(name):
            return {"artifact_type": "ephemeris", "source_tool": "orbit_propagation"}

    return None


def _load_json_or_none(path: Path) -> dict | None:
    """Try to load JSON from a file, returning None on any error.
    尝试从文件加载 JSON，出错返回 None。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def discover_artifacts(output_dir: Path) -> list[Artifact]:
    """Scan an output directory and return non-catalog Artifact instances.
    扫描 output 目录，返回非 catalog 的 Artifact 实例。

    Subdirectory layout expected:
        output/transfer/      corrected_transfer_*.json, optimization_*.json
        output/propagation/   propagation_*.json（轨道预报星历，#389）

    Returns an empty list if output_dir does not exist.
    output_dir 不存在时返回空列表。
    """
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        return []

    artifacts: list[Artifact] = []

    for json_file in sorted(output_dir.rglob("*.json")):
        meta = _classify_file(json_file)
        if meta is None:
            continue  # skip unrecognized files

        data = _load_json_or_none(json_file)
        if data is None:
            continue  # skip unreadable / unparseable files

        # Extract state_data and times if present
        state_data = None
        times = None
        states_raw = data.get("states")
        if states_raw is not None:
            with contextlib.suppress(ValueError, TypeError):
                state_data = np.asarray(states_raw, dtype=np.float64)
        times_raw = data.get("times")
        if times_raw is not None:
            with contextlib.suppress(ValueError, TypeError):
                times = np.asarray(times_raw, dtype=np.float64)

        mtime = datetime.fromtimestamp(json_file.stat().st_mtime, tz=UTC)

        # 轨道预报星历：会合系位置作 state_data（画布星历槽位），ET 秒作时间轴；
        # 其余数组（position_km/velocity_km_s/times_et）进 extra。文件名茎作
        # artifact_id（确定性，运行后可按 id 选中）。transfer 分区保持原行为。
        # Propagation ephemerides: rotating-frame positions become state_data (the canvas
        # ephemeris slot), ET seconds become the timeline; other arrays
        # (position_km/velocity_km_s/times_et) go into extra. The filename stem becomes
        # artifact_id (deterministic, selectable by id after a run). The transfer partition
        # keeps its original behavior.
        artifact_id: str | None = None
        label = json_file.stem
        if meta.get("source_tool") == "orbit_propagation":
            artifact_id = json_file.stem
            label = str(data.get("label") or json_file.stem)
            syn = data.get("synodic_position")
            if syn is not None:
                with contextlib.suppress(ValueError, TypeError):
                    state_data = np.asarray(syn, dtype=np.float64)[:, :3]
                    times = np.asarray(data.get("times_et"), dtype=np.float64)

        artifact_kwargs: dict = {}
        if artifact_id is not None:
            artifact_kwargs["artifact_id"] = artifact_id
        artifacts.append(
            Artifact(
                artifact_type=meta["artifact_type"],
                label=label,
                orbit_type="",
                source_tool=str(meta.get("source_tool", "")),  # 遗留 CLI 产物无来源工具
                output_path=json_file,
                state_data=state_data,
                times=times,
                extra=data if isinstance(data, dict) else {},
                created_at=mtime,
                **artifact_kwargs,
            )
        )

    return artifacts
