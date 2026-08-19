"""遗留分区扫描 -- 仅 transfer 产物（issue #375）。

轨道 / 轨道族 / 星历产物自 e2m2e 5.8.0 起由轨道库 catalog 管理（清单与
过滤经 Facade ``catalog_query``，见 ``engine.catalog_service``），基于
「子目录名 + 文件名正则」的分类已随本仓 ADR 0008 修订（2026-08-19）删除。

转移轨道是 catalog 分类体系之外的产物（e2m2e 对 transfer_design 等产物
入库另行立项），过渡期沿用目录扫描，待上游入库后本模块退役。
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


def _classify_file(path: Path) -> dict | None:
    """Classify a JSON file into artifact metadata, or None if not recognized."""
    name = path.name
    parent = path.parent.name

    if parent == "transfer":
        if _TRANSFER_CORRECTED_RE.match(name):
            return {"artifact_type": "transfer"}
        if _TRANSFER_OPTIMIZATION_RE.match(name):
            return {"artifact_type": "transfer"}

    return None


def _load_json_or_none(path: Path) -> dict | None:
    """Try to load JSON from a file, returning None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def discover_artifacts(output_dir: Path) -> list[Artifact]:
    """Scan an output directory and return transfer Artifact instances.

    Subdirectory layout expected:
        output/transfer/  corrected_transfer_*.json, optimization_*.json

    Returns an empty list if output_dir does not exist.
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

        artifacts.append(
            Artifact(
                artifact_type=meta["artifact_type"],
                label=json_file.stem,
                orbit_type="",
                source_tool="",  # 转移产物来源工具未接入 GUI，不臆测
                output_path=json_file,
                state_data=state_data,
                times=times,
                extra=data if isinstance(data, dict) else {},
                created_at=mtime,
            )
        )

    return artifacts
