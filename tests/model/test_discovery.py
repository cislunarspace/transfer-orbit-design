"""tests for src.model.discovery -- transfer 遗留分区扫描（issue #375）。

轨道 / 族 / 星历产物的文件名分类正则已随 catalog 接入退役；本模块只剩
transfer 分区（e2m2e catalog 分类体系之外，过渡期目录扫描）。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.model.discovery import discover_artifacts


def _write(tmp_path: Path, rel: str, payload: dict | None = None) -> None:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload or {}), encoding="utf-8")


class TestDiscoverTransferArtifacts:
    def test_corrected_transfer_classified(self, tmp_path: Path) -> None:
        _write(tmp_path, "transfer/corrected_transfer_001.json", {"delta_v": 3.9})
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "transfer"
        assert artifacts[0].label == "corrected_transfer_001"

    def test_optimization_classified(self, tmp_path: Path) -> None:
        _write(tmp_path, "transfer/optimization_001.json")
        artifacts = discover_artifacts(tmp_path)
        assert [a.artifact_type for a in artifacts] == ["transfer"]

    def test_transfer_states_parsed(self, tmp_path: Path) -> None:
        states = [[1.0, 0.0, 0.0, 0.0, 0.1, 0.0], [1.1, 0.0, 0.0, 0.0, 0.1, 0.0]]
        _write(tmp_path, "transfer/corrected_transfer_001.json", {"states": states})
        artifacts = discover_artifacts(tmp_path)
        np.testing.assert_array_equal(artifacts[0].state_data, np.asarray(states))

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        assert discover_artifacts(tmp_path / "nope") == []

    def test_bad_json_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "transfer" / "corrected_transfer_bad.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        assert discover_artifacts(tmp_path) == []


class TestRetiredClassifications:
    """轨道 / 族 / 星历分类正则已删除（ADR 0008 修订）：同类文件不再进清单。"""

    def test_orbit_files_not_classified(self, tmp_path: Path) -> None:
        _write(tmp_path, "dro/dro_20260101000000.json", {"orbit_type": "DRO"})
        _write(tmp_path, "halo/halo_20260101000000.json", {"orbit_type": "Halo"})
        assert discover_artifacts(tmp_path) == []

    def test_family_files_not_classified(self, tmp_path: Path) -> None:
        _write(tmp_path, "family/family_20260101000000.json", {"orbit_type": "Halo"})
        _write(tmp_path, "dro/dro_x_family_001.json")
        assert discover_artifacts(tmp_path) == []

    def test_ephemeris_files_not_classified(self, tmp_path: Path) -> None:
        _write(tmp_path, "ephemeris/orbit_ephemeris_20260101000000.json")
        assert discover_artifacts(tmp_path) == []
