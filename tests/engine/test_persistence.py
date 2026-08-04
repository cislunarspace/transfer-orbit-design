"""tests for src.engine.persistence -- save_artifact / discover 兼容性。"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from src.engine.facade_bridge import OrbitDesignResultData
from src.engine.persistence import save_artifact
from src.model.discovery import discover_artifacts


def _make_dto() -> OrbitDesignResultData:
    n = 100
    return OrbitDesignResultData(
        orbit_type="DRO",
        epoch_utc="2024-01-01T00:00:00",
        duration_day=365.25,
        initial_state=np.array([1.0, 2.0, 3.0, 0.1, 0.2, 0.3]),
        cr3bp_jacobi=3.0058,
        states=np.random.randn(n, 6),
        times=np.linspace(0, 365.25, n),
        correction_converged=True,
        correction_iterations=3,
    )


class TestSaveArtifact:
    def test_creates_json_and_npz(self, tmp_path):
        json_path = save_artifact(_make_dto(), tmp_path)
        assert json_path.exists()
        npz_path = json_path.with_suffix(".npz")
        assert npz_path.exists()

    def test_json_is_valid(self, tmp_path):
        json_path = save_artifact(_make_dto(), tmp_path)
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        assert meta["orbit_type"] == "DRO"
        assert meta["cr3bp_jacobi"] == pytest.approx(3.0058)
        assert meta["correction_converged"] is True
        assert meta["states_shape"] == [100, 6]
        assert meta["times_count"] == 100
        assert meta["arrays_file"] == json_path.with_suffix(".npz").name

    def test_npz_arrays(self, tmp_path):
        dto = _make_dto()
        json_path = save_artifact(dto, tmp_path)
        npz_path = json_path.with_suffix(".npz")
        data = np.load(npz_path)
        np.testing.assert_array_equal(data["states"], dto.states)
        np.testing.assert_array_equal(data["times"], dto.times)

    def test_json_filename_matches_discovery_regex(self, tmp_path):
        json_path = save_artifact(_make_dto(), tmp_path)
        assert re.match(r"^dro_\d+\.json$", json_path.name), (
            f"文件名 {json_path.name} 与 _DRO_ORBIT_RE 不兼容"
        )

    def test_discover_roundtrip(self, tmp_path):
        """save_artifact -> discover_artifacts 互操作。"""
        save_artifact(_make_dto(), tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        assert a.artifact_type == "orbit"
        assert a.orbit_type == "DRO"
        assert a.output_path is not None
        assert a.output_path.exists()


class TestLazyLoadRoundtrip:
    def test_discover_then_lazy_load(self, tmp_path):
        """save_artifact -> discover -> 模拟懒加载 -> state_data 恢复。"""
        dto = _make_dto()
        save_artifact(dto, tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        # Discovery 不加载数组
        assert a.state_data is None
        # 模拟懒加载
        npz_path = a.output_path.parent / a.extra["arrays_file"]
        data = np.load(npz_path)
        np.testing.assert_array_equal(data["states"], dto.states)
        np.testing.assert_array_equal(data["times"], dto.times)
