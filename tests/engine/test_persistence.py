"""tests for src.engine.persistence -- save_stability_result（catalog 之外的落盘）。"""

from __future__ import annotations

import json

import numpy as np

from src.engine.facade_bridge import StabilityResultData
from src.engine.persistence import save_stability_result


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
