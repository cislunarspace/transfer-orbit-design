from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from src.model.artifact import Artifact

# Precompiled patterns for filename classification
_DRO_ORBIT_RE = re.compile(r"^dro_\d+\.json$")
_DRO_FAMILY_RE = re.compile(r"^dro_.*_family_.*\.json$")
_HALO_ORBIT_RE = re.compile(r"^halo_.*\.json$")
_EPHEMERIS_RE = re.compile(r"^orbit_ephemeris_.*\.json$")
_TRANSFER_CORRECTED_RE = re.compile(r"^corrected_transfer_.*\.json$")
_TRANSFER_OPTIMIZATION_RE = re.compile(r"^optimization_.*\.json$")


def _classify_file(path: Path) -> dict | None:
    """Classify a JSON file into artifact metadata, or None if not recognized."""
    name = path.name
    parent = path.parent.name

    if parent == "dro":
        if _DRO_FAMILY_RE.match(name):
            return {"artifact_type": "family", "orbit_type": "DRO"}
        if _DRO_ORBIT_RE.match(name):
            return {"artifact_type": "orbit", "orbit_type": "DRO"}

    if parent == "halo" and _HALO_ORBIT_RE.match(name):
        return {"artifact_type": "orbit", "orbit_type": "Halo"}

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


def discover_artifacts(output_dir: Path) -> List[Artifact]:
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

    artifacts: List[Artifact] = []

    for json_file in sorted(output_dir.rglob("*.json")):
        meta = _classify_file(json_file)
        if meta is None:
            continue  # skip unrecognized files

        data = _load_json_or_none(json_file)
        if data is None:
            continue  # skip unreadable / unparseable files

        # Extract orbit_type from JSON content if available
        orbit_type = data.get("orbit_type", meta["orbit_type"])

        mtime = datetime.fromtimestamp(json_file.stat().st_mtime, tz=timezone.utc)

        artifacts.append(
            Artifact(
                artifact_type=meta["artifact_type"],
                label=json_file.stem,
                orbit_type=orbit_type or "",
                source_tool="",
                output_path=json_file,
                extra=data if isinstance(data, dict) else {},
                created_at=mtime,
            )
        )

    return artifacts
