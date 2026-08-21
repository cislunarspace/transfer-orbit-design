"""tests for src.engine.persistence -- save_stability_result（catalog 之外的落盘）。"""

from __future__ import annotations

import json

import numpy as np

from src.engine.facade_bridge import PropagationResultData, StabilityResultData
from src.engine.persistence import save_propagation_result, save_stability_result
from src.model.discovery import discover_artifacts


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


class TestSavePropagationResult:
    def _propagation_dto(self) -> PropagationResultData:
        return PropagationResultData(
            epoch_utc="2026-01-01T00:00:00.000",
            duration_sec=86400.0,
            n_points=2,
            times_et=np.array([0.0, 3600.0]),
            position_km=np.tile([6793.0, 0.0, 0.0], (2, 1)),
            velocity_km_s=np.tile([0.0, 7.5, 3.0], (2, 1)),
            synodic_position=np.array([[0.01, 0.0, 0.0], [0.01, 0.01, 0.0]]),
            final_state=np.array([6793.0, 0, 0, 0, 7.5, 3.0]),
            mu=0.012150585,
        )

    def test_creates_propagation_json(self, tmp_path):
        json_path = save_propagation_result(self._propagation_dto(), tmp_path)
        assert json_path.parent.name == "propagation"
        assert json_path.name.startswith("propagation_")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["source_tool"] == "orbit_propagation"
        assert payload["label"] == "轨道预报 2026-01-01T00:00:00.000"
        assert payload["times_et"] == [0.0, 3600.0]
        assert len(payload["synodic_position"]) == 2

    def test_roundtrip_through_discovery(self, tmp_path):
        """落盘 → discovery 扫描恢复为 ephemeris Artifact（#389 重启恢复链路）。"""
        json_path = save_propagation_result(self._propagation_dto(), tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        assert artifacts[0].artifact_id == json_path.stem
        np.testing.assert_allclose(
            artifacts[0].state_data,
            np.array([[0.01, 0.0, 0.0], [0.01, 0.01, 0.0]]),
        )
