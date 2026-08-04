"""tests for src.engine.persistence -- save_artifact / discover 兼容性。"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from src.engine.facade_bridge import OrbitDesignResultData
from src.engine.persistence import load_artifact_arrays, save_artifact
from src.model.discovery import discover_artifacts

_RNG = np.random.default_rng(seed=42)


def _make_dto() -> OrbitDesignResultData:
    n = 100
    return OrbitDesignResultData(
        orbit_type="DRO",
        epoch_utc="2024-01-01T00:00:00",
        duration_day=365.25,
        initial_state=np.array([1.0, 2.0, 3.0, 0.1, 0.2, 0.3]),
        cr3bp_jacobi=3.0058,
        states=_RNG.standard_normal((n, 6)),
        times=np.linspace(0, 365.25, n),
        correction_converged=True,
        correction_iterations=3,
    )


class TestSaveArtifact:
    def test_creates_json_and_npz(self, tmp_path):
        json_path, npz_path = save_artifact(_make_dto(), tmp_path)
        assert json_path.exists()
        assert npz_path.exists()

    def test_returns_json_and_npz_paths(self, tmp_path):
        """S2: save_artifact 应返回 ``(json_path, npz_path)`` 元组，避免重复推导。"""
        json_path, npz_path = save_artifact(_make_dto(), tmp_path)
        assert json_path.suffix == ".json"
        assert npz_path.suffix == ".npz"
        assert npz_path.name == json_path.with_suffix(".npz").name
        assert npz_path.parent == json_path.parent

    def test_json_is_valid(self, tmp_path):
        json_path, _ = save_artifact(_make_dto(), tmp_path)
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        assert meta["orbit_type"] == "DRO"
        assert meta["cr3bp_jacobi"] == pytest.approx(3.0058)
        assert meta["correction_converged"] is True
        assert meta["states_shape"] == [100, 6]
        assert meta["times_count"] == 100

    def test_npz_arrays(self, tmp_path):
        dto = _make_dto()
        _, npz_path = save_artifact(dto, tmp_path)
        # S1: 用 with 上下文管理器关闭文件句柄
        with np.load(npz_path) as data:
            np.testing.assert_array_equal(data["states"], dto.states)
            np.testing.assert_array_equal(data["times"], dto.times)

    def test_json_filename_matches_discovery_regex(self, tmp_path):
        json_path, _ = save_artifact(_make_dto(), tmp_path)
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
        """save_artifact -> discover -> load_artifact_arrays 懒加载恢复 state_data。"""
        dto = _make_dto()
        save_artifact(dto, tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        # Discovery 不加载数组
        assert a.state_data is None
        # 通过 persistence.load_artifact_arrays 懒加载（覆盖 S1 文件句柄）
        assert load_artifact_arrays(a) is True
        np.testing.assert_array_equal(a.state_data, dto.states)
        np.testing.assert_array_equal(a.times, dto.times)


class TestLoadArtifactArrays:
    """覆盖 load_artifact_arrays 的所有边界条件（False 路径）。"""

    def test_returns_false_when_no_output_path(self):
        from src.model.artifact import Artifact

        a = Artifact(artifact_type="orbit", label="x", output_path=None)
        assert load_artifact_arrays(a) is False

    def test_returns_false_when_no_arrays_file_key(self, tmp_path):
        from src.model.artifact import Artifact

        json_path = tmp_path / "dro_no_arrays.json"
        json_path.write_text("{}", encoding="utf-8")
        a = Artifact(
            artifact_type="orbit", label="x", output_path=json_path, extra={}
        )
        assert load_artifact_arrays(a) is False

    def test_returns_false_when_npz_missing(self, tmp_path):
        from src.model.artifact import Artifact

        json_path = tmp_path / "dro_missing.json"
        json_path.write_text("{}", encoding="utf-8")
        a = Artifact(
            artifact_type="orbit",
            label="x",
            output_path=json_path,
            extra={"arrays_file": "dro_missing.npz"},
        )
        assert load_artifact_arrays(a) is False

    def test_returns_false_on_corrupt_npz(self, tmp_path):
        from src.model.artifact import Artifact

        json_path = tmp_path / "dro_corrupt.json"
        json_path.write_text("{}", encoding="utf-8")
        npz_path = tmp_path / "dro_corrupt.npz"
        npz_path.write_bytes(b"NOT_A_VALID_NPZ")
        a = Artifact(
            artifact_type="orbit",
            label="x",
            output_path=json_path,
            extra={"arrays_file": "dro_corrupt.npz"},
        )
        assert load_artifact_arrays(a) is False
