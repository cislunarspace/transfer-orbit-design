from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from src.model.artifact import Artifact

# Precompiled patterns for filename classification
# 单条 orbit 落盘布局（persistence.save_artifact）：output/<type>/<type>_<ts>.json，
# 目录名与文件前缀均为轨道类型小写。DRO 恰为 dro_<14位时间戳>，与旧布局兼容。
_DRO_FAMILY_RE = re.compile(r"^dro_.*_family_.*\.json$")
_EPHEMERIS_RE = re.compile(r"^orbit_ephemeris_.*\.json$")
_TRANSFER_CORRECTED_RE = re.compile(r"^corrected_transfer_.*\.json$")
_TRANSFER_OPTIMIZATION_RE = re.compile(r"^optimization_.*\.json$")

#: 单条轨道落盘的子目录 -> 轨道类型（与 persistence 的目录命名约定一致）。
#: 轨道类型即子目录名的小写首字母大写；DRO 特例：目录名 dro 对应 "DRO"。
_ORBIT_TYPE_BY_DIR: dict[str, str] = {
    "dro": "DRO",
    "halo": "Halo",
    "nrho": "NRHO",
    "lissajous": "Lissajous",
    "l4": "L4",
    "l5": "L5",
    "axial": "Axial",
}

#: 任意类型单条 orbit 文件：``<type>_<后缀>.json``（persistence 落盘为
#: ``<type>_<14位时间戳>.json``；兼容旧手工命名如 ``halo_north_L1.json``）。
_ORBIT_ORBIT_RE = re.compile(r"^(?P<prefix>[a-z0-9]+)_\w+\.json$")


def _classify_file(path: Path) -> dict | None:
    """Classify a JSON file into artifact metadata, or None if not recognized."""
    name = path.name
    parent = path.parent.name

    # 遗留：旧 GUI 的 DRO 族输出（dro_*_family_*.json）
    if parent == "dro" and _DRO_FAMILY_RE.match(name):
        return {"artifact_type": "family", "orbit_type": "DRO"}

    # 单条轨道：目录名 = 轨道类型小写，文件名 = <type>_<ts>.json
    orbit_type = _ORBIT_TYPE_BY_DIR.get(parent)
    m = _ORBIT_ORBIT_RE.match(name) if orbit_type is not None else None
    if m is not None and m.group("prefix") == parent:
        return {"artifact_type": "orbit", "orbit_type": orbit_type}

    if parent == "ephemeris" and _EPHEMERIS_RE.match(name):
        return {"artifact_type": "ephemeris", "orbit_type": ""}

    if parent == "transfer":
        if _TRANSFER_CORRECTED_RE.match(name):
            return {"artifact_type": "transfer", "orbit_type": ""}
        if _TRANSFER_OPTIMIZATION_RE.match(name):
            return {"artifact_type": "transfer", "orbit_type": ""}

    return None


def _load_json_or_none(path: Path) -> dict | None:
    """Try to load JSON from a file, returning None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def discover_artifacts(output_dir: Path) -> list[Artifact]:
    """Scan an output directory and return classified Artifact instances.

    Subdirectory layout expected:
        output/dro/       dro_*.json
        output/halo/      halo_*.json
        output/ephemeris/ orbit_ephemeris_*.json
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

        # Extract orbit_type from JSON content if available
        orbit_type = data.get("orbit_type", meta["orbit_type"])

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

        # source_tool 从 meta.artifact_type 推断（路径是产物来源的 ground truth）。
        # design_orbit 落 output/dro|halo/，control_orbit 落 output/ephemeris/。
        # 画布数据契约（#359）按 source_tool 区分初猜/星历槽位，必须正确。
        at = meta["artifact_type"]
        inferred_source = (
            "design_orbit" if at == "orbit" else "control_orbit" if at == "ephemeris" else ""
        )

        artifacts.append(
            Artifact(
                artifact_type=at,
                label=json_file.stem,
                orbit_type=orbit_type or "",
                source_tool=inferred_source,
                output_path=json_file,
                state_data=state_data,
                times=times,
                extra=data if isinstance(data, dict) else {},
                created_at=mtime,
            )
        )

    return artifacts
