"""tests for FacadeBridge.transfer_design + 转移结果落盘/扫描。

桩打在算法层 ``e2m2e.algorithm.transfer.transfer_orbit`` 上：请求校验与
响应翻译仍走真 Facade。
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from e2m2e.data.templates import ConvergenceState, FailureCause

from src.commons.units import DU_KM, TU_SECONDS
from src.engine.facade_bridge import FacadeBridge, TransferDesignResultData
from src.engine.persistence import save_transfer_result


class _FakeTransferResult:
    """Fake TransferDesignResult（transfer_orbit 返回形状）。"""

    def __init__(
        self,
        transfer_type: str = "HMN",
        delta_v: float = 3.9,
        trajectory: np.ndarray | None = None,
        converged: bool = True,
    ) -> None:
        self.transfer_type = transfer_type
        self.delta_v = delta_v
        self.trajectory = trajectory
        self.details = {"tof_sec": 345600.0}
        self.status = (
            ConvergenceState.CONVERGED if converged else ConvergenceState.INFEASIBLE
        )
        self.cause = FailureCause.NONE if converged else FailureCause.CONSTRAINT_VIOLATION
        self.message = "完成" if converged else "无可行候选"


@pytest.fixture
def bridge() -> FacadeBridge:
    return FacadeBridge()


def _patch_transfer_orbit(monkeypatch, result: _FakeTransferResult) -> dict:
    """打桩 transfer_orbit，返回捕获到的调用 kwargs。"""
    captured: dict = {}

    def fake(transfer_type, **kwargs):
        captured["transfer_type"] = transfer_type
        captured["kwargs"] = kwargs
        return result

    monkeypatch.setattr(
        "e2m2e.algorithm.transfer.transfer_orbit", fake, raising=False
    )
    return captured


class TestTransferDesign:
    def test_returns_dto(self, monkeypatch, bridge):
        traj = np.array([[6800.0, 0, 0, 0, 7.7, 0], [380000.0, 0, 0, 0, 1.0, 0]])
        captured = _patch_transfer_orbit(monkeypatch, _FakeTransferResult(trajectory=traj))
        data = bridge.transfer_design(
            transfer_type="HMN", tli_epoch="2025-06-01T00:00:00"
        )
        assert isinstance(data, TransferDesignResultData)
        assert data.converged is True
        assert np.array_equal(data.trajectory, traj)
        assert captured["transfer_type"] == "HMN"

    def test_target_states_converted_to_synodic_physical(self, monkeypatch, bridge):
        """选中工件的 CR3BP 无量纲状态末行应换算为会合系物理态 (1, 6)。"""
        captured = _patch_transfer_orbit(monkeypatch, _FakeTransferResult("LGA"))
        states = np.array([[1.0, 0.0, 0.0, 0.0, 0.5, 0.0], [1.1, 0.1, 0.0, -0.1, 0.4, 0.0]])
        bridge.transfer_design(
            transfer_type="LGA",
            tli_epoch="2025-06-01T00:00:00",
            target_states=states,
        )
        eph = captured["kwargs"]["target_ephemeris"]
        assert eph.shape == (1, 6)
        np.testing.assert_allclose(
            eph[0], np.r_[states[-1][:3] * DU_KM, states[-1][3:] * (DU_KM / TU_SECONDS)]
        )

    def test_tli_epoch_list_to_iso(self, monkeypatch, bridge):
        """epoch 控件产出的 [年,月,日,时,分,秒] 应转 ISO 字符串透传。"""
        captured = _patch_transfer_orbit(monkeypatch, _FakeTransferResult())
        bridge.transfer_design(
            transfer_type="HMN", tli_epoch=[2025, 6, 1, 12, 30, 5.0]
        )
        tli = captured["kwargs"]["tli_params"]
        assert tli.epoch == "2025-06-01T12:30:05"

    def test_lga_default_grid_injected(self, monkeypatch, bridge):
        """LGA 未显式给搜索参数时，桥接层注入加密相位网格（360 点）。"""
        captured = _patch_transfer_orbit(monkeypatch, _FakeTransferResult("LGA"))
        bridge.transfer_design(
            transfer_type="LGA", tli_epoch="2025-06-01T00:00:00"
        )
        sp = captured["kwargs"].get("lga_search_params")
        assert sp is not None and sp.n_departure_phase == 360

    def test_infeasible_maps_to_not_converged(self, monkeypatch, bridge):
        _patch_transfer_orbit(monkeypatch, _FakeTransferResult(converged=False))
        data = bridge.transfer_design(
            transfer_type="HMN", tli_epoch="2025-06-01T00:00:00"
        )
        assert data.converged is False
        assert data.trajectory is None


class TestSaveTransferResult:
    def _dto(self, **kw) -> TransferDesignResultData:
        defaults = dict(
            transfer_type="HMN",
            delta_v=3.94,
            message="霍曼转移完成",
            converged=True,
            trajectory=np.array([[6800.0, 0, 0, 0, 7.7, 0]]),
            details={"tof_sec": 345600.0},
        )
        defaults.update(kw)
        return TransferDesignResultData(**defaults)

    def test_creates_transfer_json(self, tmp_path):
        json_path = save_transfer_result(self._dto(), tmp_path)
        assert json_path.parent.name == "transfer"
        assert json_path.name.startswith("transfer_design_")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["source_tool"] == "transfer_design"
        assert data["delta_v_km_s"] == 3.94
        assert data["states"] == [[6800.0, 0, 0, 0, 7.7, 0]]

    def test_none_trajectory_serializes(self, tmp_path):
        json_path = save_transfer_result(
            self._dto(trajectory=None, converged=False), tmp_path
        )
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["states"] is None
        assert data["converged"] is False

    def test_discovered_by_legacy_scan(self, tmp_path):
        """落盘文件应被遗留分区扫描识别为 transfer 工件。"""
        from src.model.discovery import discover_artifacts

        json_path = save_transfer_result(self._dto(), tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        art = artifacts[0]
        assert art.artifact_type == "transfer"
        assert art.source_tool == "transfer_design"
        assert art.output_path == json_path
        assert art.state_data is not None and art.state_data.shape == (1, 6)
