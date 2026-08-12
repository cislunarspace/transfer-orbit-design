"""tests for src.engine.persistence -- save_artifact / discover 兼容性。"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from src.engine.facade_bridge import FamilyResultData, OrbitDesignResultData, StabilityResultData
from src.engine.persistence import (
    load_artifact_arrays,
    save_artifact,
    save_family_result,
    save_stability_result,
)
from src.model.discovery import discover_artifacts

_RNG = np.random.default_rng(seed=42)


def _make_dto(orbit_type: str = "DRO") -> OrbitDesignResultData:
    n = 100
    return OrbitDesignResultData(
        orbit_type=orbit_type,
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


class TestSaveArtifactOrbitTypeNaming:
    """回归：Halo 等非 DRO 轨道不得落盘为 dro_ 前缀（#359 后画布数据契约）。

    save_artifact 曾无条件写 ``output/dro/dro_<ts>``，导致 Halo/NRHO/Lissajous
    等轨道保存成 DRO 文件；discovery 按目录+前缀分类，读取时被当作 DRO。
    """

    @pytest.mark.parametrize("orbit_type", ["DRO", "Halo", "NRHO", "Lissajous"])
    def test_saves_to_type_subdir(self, tmp_path, orbit_type):
        json_path, _ = save_artifact(_make_dto(orbit_type), tmp_path)
        expected_dir = tmp_path / orbit_type.lower()
        assert json_path.parent == expected_dir, (
            f"{orbit_type} 轨道应写入 output/{orbit_type.lower()}/，实际写入 {json_path.parent}"
        )

    @pytest.mark.parametrize("orbit_type", ["DRO", "Halo", "NRHO", "Lissajous"])
    def test_filename_prefix_matches_type(self, tmp_path, orbit_type):
        json_path, _ = save_artifact(_make_dto(orbit_type), tmp_path)
        assert json_path.stem.startswith(orbit_type.lower() + "_"), (
            f"{orbit_type} 轨道文件名应以 {orbit_type.lower()}_ 开头，实际为 {json_path.stem}"
        )

    @pytest.mark.parametrize("orbit_type", ["DRO", "Halo", "NRHO", "Lissajous"])
    def test_discover_roundtrip_type(self, tmp_path, orbit_type):
        """保存后 discover 能按目录分类回正确的 orbit_type。"""
        save_artifact(_make_dto(orbit_type), tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        assert a.artifact_type == "orbit"
        assert a.orbit_type == orbit_type, f"{orbit_type} 保存后 discover 分类为 {a.orbit_type}"
        assert a.source_tool == "design_orbit"

    def test_dro_backward_compatible_layout(self, tmp_path):
        """DRO 的既有布局（output/dro/dro_<ts>）保持不变。"""
        json_path, _ = save_artifact(_make_dto("DRO"), tmp_path)
        assert json_path.parent == tmp_path / "dro"
        assert re.match(r"^dro_\d+\.json$", json_path.name)

    def test_mixed_types_separated(self, tmp_path):
        """DRO 与 Halo 混存时互不串目录。"""
        save_artifact(_make_dto("DRO"), tmp_path)
        save_artifact(_make_dto("Halo"), tmp_path)
        artifacts = discover_artifacts(tmp_path)
        types = sorted(a.orbit_type for a in artifacts)
        assert types == ["DRO", "Halo"]


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
        a = Artifact(artifact_type="orbit", label="x", output_path=json_path, extra={})
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


class TestSaveFamilyResult:
    def _family_dto(self, m: int = 4, n: int = 100) -> FamilyResultData:
        return FamilyResultData(
            orbit_type="Halo",
            libration_point=2,
            n_orbits=m,
            mu=0.01215,
            states=_RNG.standard_normal((m, n, 6)),
            times=np.tile(np.linspace(0, 1, n), (m, 1)),
            z0s=np.linspace(0.001, 0.05, m),
        )

    def test_creates_family_dir_json_npz(self, tmp_path):
        json_path, npz_path = save_family_result(self._family_dto(), tmp_path)
        assert json_path.parent.name == "family"
        assert json_path.name.startswith("family_")
        assert json_path.exists()
        assert npz_path.exists()

    def test_npz_stores_3d_states(self, tmp_path):
        _, npz_path = save_family_result(self._family_dto(), tmp_path)
        with np.load(npz_path) as data:
            assert data["states"].shape == (4, 100, 6)
            assert data["times"].shape == (4, 100)
            assert data["z0s"].shape == (4,)

    def test_meta_fields(self, tmp_path):
        json_path, _ = save_family_result(self._family_dto(), tmp_path)
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        assert meta["artifact_type"] == "family"
        assert meta["source_tool"] == "orbit_family_generation"
        assert meta["orbit_type"] == "Halo"
        assert meta["n_orbits"] == 4
        assert meta["states_shape"] == [4, 100, 6]

    def test_discover_roundtrip(self, tmp_path):
        json_path, _ = save_family_result(self._family_dto(), tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        assert a.artifact_type == "family"
        assert a.source_tool == "orbit_family_generation"
        assert a.orbit_type == "Halo"


class TestSaveStabilityResult:
    def _stability_dto(self) -> StabilityResultData:
        from e2m2e.algorithm.stability import BifurcationType, StabilityType

        return StabilityResultData(
            monodromy_matrix=np.eye(6),
            eigenvalues=np.array([1.0, -1.0, 0.5 + 0.5j, 0.5 - 0.5j, 2.0, 0.5]),
            stability_indices={"nu1": 1.5, "nu2": 0.8, "nu3": 1.1, "broucke": 2.3},
            classification={
                "stability_type": StabilityType.HYPERBOLIC,
                "is_stable": False,
                "is_unstable": True,
                "stability_margin": -1.0,
            },
            bifurcation={
                "bifurcation_type": BifurcationType.NONE,
                "bifurcation_detected": False,
            },
            numerical_errors={"monodromy": None},
        )

    def test_creates_stability_json(self, tmp_path):
        json_path = save_stability_result(
            self._stability_dto(), tmp_path, orbit_label="Halo L2 (C_J=3.1)"
        )
        assert json_path.parent.name == "stability"
        assert "Halo_L2" in json_path.name
        assert json_path.exists()

    def test_json_serializable(self, tmp_path):
        json_path = save_stability_result(self._stability_dto(), tmp_path, orbit_label="test")
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        # enum/ndarray 均被序列化为普通 JSON
        assert meta["classification"]["stability_type"] == "hyperbolic"
        assert meta["bifurcation"]["bifurcation_type"] == "none"
        assert meta["monodromy_matrix"][0][0] == 1.0
        # complex128 数组 tolist 后全为复数 → [real, imag]
        assert meta["eigenvalues"][0] == [1.0, 0.0]
        assert meta["eigenvalues"][2] == [0.5, 0.5]
