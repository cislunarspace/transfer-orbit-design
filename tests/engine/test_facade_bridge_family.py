"""tests for FacadeBridge.generate_family / analyze_stability（轨道族生成 + 稳定性分析）。

mock 测试验证 DTO 装配与参数透传；末尾两个真路径测试用真实 e2m2e 算法层
（纯 CR3BP，不需要 SPICE 内核），守住"族延拓真能跑"的底线。
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from e2m2e.data.templates.seed import EARTH_MOON_MU
from pydantic import ValidationError

from src.engine.facade_bridge import (
    FacadeBridge,
    FamilyGenerationRequest,
    FamilyResultData,
    StabilityResultData,
)

# ---------------------------------------------------------------------------
# FamilyGenerationRequest 模型
# ---------------------------------------------------------------------------


class TestFamilyGenerationRequest:
    def test_halo_defaults(self):
        req = FamilyGenerationRequest(orbit_type="HALO")
        assert req.libration_point == 2
        assert req.max_amplitude_km == 30000.0
        assert req.n_orbits == 50

    def test_constraints(self):
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(orbit_type="HALO", libration_point=3)
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(orbit_type="HALO", max_amplitude_km=0.0)
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(orbit_type="HALO", max_amplitude_km=60000.0)
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(orbit_type="HALO", n_orbits=0)

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(orbit_type="HALO", unexpected=True)


# ---------------------------------------------------------------------------
# generate_family mock 测试
# ---------------------------------------------------------------------------


class _FakeSystem:
    """Fake CR3BP_System。"""

    mu = EARTH_MOON_MU


@pytest.fixture()
def mock_family_design(monkeypatch):
    """桩掉上游 Halo 族生成入口，记录桥接层传参。"""
    calls: dict[str, object] = {}

    def _design_halo_family(libration_point, max_amplitude_km, *, n_orbits=50, dynamics=None):
        calls["args"] = (libration_point, max_amplitude_km)
        calls["n_orbits"] = n_orbits
        return SimpleNamespace(
            system=_FakeSystem(),
            orbits=[
                SimpleNamespace(
                    states=np.full((100, 6), float(index)),
                    times=np.linspace(0, 1, 100),
                )
                for index in range(n_orbits)
            ],
        )

    monkeypatch.setattr(
        "e2m2e.algorithm.family.cr3bp_orbits.design_halo_family",
        _design_halo_family,
        raising=False,
    )
    return calls


class TestGenerateFamily:
    def test_returns_dto_and_delegates_to_upstream(self, mock_family_design):
        data = FacadeBridge().generate_family(
            libration_point=2, max_amplitude_km=20000.0, n_orbits=5
        )
        assert isinstance(data, FamilyResultData)
        assert data.orbit_type == "Halo"
        assert data.n_orbits == 5
        assert data.states.shape == (5, 100, 6)
        assert data.times.shape == (5, 100)
        assert data.z0s.shape == (5,)
        assert data.mu == pytest.approx(EARTH_MOON_MU)
        assert mock_family_design == {"args": (2, 20000.0), "n_orbits": 5}

    def test_defaults_to_halo(self, mock_family_design):
        FacadeBridge().generate_family(libration_point=1, max_amplitude_km=10000.0, n_orbits=3)
        assert mock_family_design["args"] == (1, 10000.0)
        assert mock_family_design["n_orbits"] == 3

    def test_invalid_params_translated(self, mock_family_design):
        """非法参数经 FamilyGenerationRequest 校验 → OrbitError(INVALID_PARAMS)。"""
        from src.engine.exceptions import OrbitError

        with pytest.raises(OrbitError) as exc_info:
            FacadeBridge().generate_family(libration_point=9, max_amplitude_km=20000.0, n_orbits=5)
        assert exc_info.value.code == "INVALID_PARAMS"

    def test_unimplemented_family_translated(self, mock_family_design):
        from src.engine.exceptions import OrbitError

        with pytest.raises(OrbitError) as exc_info:
            FacadeBridge().generate_family(orbit_type="NRHO", libration_point=2)
        assert exc_info.value.code == "NOT_IMPLEMENTED"


# ---------------------------------------------------------------------------
# analyze_stability mock 测试
# ---------------------------------------------------------------------------


class _FakeStabilityAnalysis:
    """Fake StabilityAnalysis：analyze() 返回纯数据结果容器。"""

    instances: list = []

    def __init__(self, orbit=None, dynamics=None) -> None:
        _FakeStabilityAnalysis.instances.append(self)
        self.orbit = orbit
        self.dynamics = dynamics

    def analyze(self) -> SimpleNamespace:
        return SimpleNamespace(
            monodromy_matrix=np.eye(6),
            eigenvalues=np.array([1.0, -1.0, 0.5 + 0.5j, 0.5 - 0.5j, 2.0, 0.5]),
            stability_indices={"nu1": 1.5, "nu2": 0.8, "nu3": 1.1, "broucke": 2.3},
            classification={
                "stability_type": SimpleNamespace(value="hyperbolic"),
                "is_stable": False,
                "is_unstable": True,
                "stability_margin": -1.0,
            },
            bifurcation={
                "bifurcation_type": SimpleNamespace(value="none"),
                "bifurcation_detected": False,
            },
            numerical_errors={"monodromy": None},
        )


@pytest.fixture()
def mock_stability(monkeypatch):
    monkeypatch.setattr(
        "e2m2e.algorithm.stability.StabilityAnalysis",
        _FakeStabilityAnalysis,
        raising=False,
    )
    monkeypatch.setattr(
        "e2m2e.algorithm.dynamics.CR3BP_Dynamics",
        lambda system: object(),
        raising=False,
    )
    return _FakeStabilityAnalysis


class TestAnalyzeStability:
    def test_returns_dto(self, mock_stability):
        n = 1000
        data = FacadeBridge().analyze_stability(
            states=np.random.randn(n, 6),
            times=np.linspace(0, 1, n),
            mu=0.01215,
        )
        assert isinstance(data, StabilityResultData)
        assert data.monodromy_matrix.shape == (6, 6)
        assert data.eigenvalues.shape == (6,)
        assert data.stability_indices["nu1"] == pytest.approx(1.5)
        assert data.classification["stability_type"].value == "hyperbolic"
        assert data.bifurcation["bifurcation_detected"] is False

    def test_receives_orbit_with_system(self, mock_stability):
        """构造的 Orbit 应绑定 system（analyze 内部从 system 取 mu）。"""
        FacadeBridge().analyze_stability(
            states=np.random.randn(10, 6),
            times=np.linspace(0, 1, 10),
            mu=0.01215,
        )
        orbit = mock_stability.instances[-1].orbit
        assert orbit.system is not None
        assert orbit.system.mu == pytest.approx(0.01215)

    def test_mu_none_uses_earth_moon_default(self, mock_stability):
        """mu 缺失（旧 Artifact）时用 e2m2e 地月系统默认质量比，而非硬编码常量。"""
        FacadeBridge().analyze_stability(
            states=np.random.randn(10, 6),
            times=np.linspace(0, 1, 10),
            mu=None,
        )
        orbit = mock_stability.instances[-1].orbit
        assert orbit.system.mu == pytest.approx(EARTH_MOON_MU)


# ---------------------------------------------------------------------------
# 真路径（纯 CR3BP，无需 SPICE）
# ---------------------------------------------------------------------------


def test_generate_family_real_pipeline():
    """真 e2m2e：小 Halo 族应返回等长三维 states。"""
    data = FacadeBridge().generate_family(libration_point=2, max_amplitude_km=5000.0, n_orbits=3)
    assert data.orbit_type == "Halo"
    assert data.n_orbits >= 2
    assert data.states.ndim == 3
    assert data.states.shape[0] == data.n_orbits
    # 北族 z 振幅单调递增（从种子往大振幅延拓）
    assert data.z0s[0] < data.z0s[-1]


def test_analyze_stability_real_pipeline():
    """真 e2m2e：对族成员做稳定性分析应返回完整结果。"""
    data = FacadeBridge().generate_family(libration_point=2, max_amplitude_km=5000.0, n_orbits=3)
    stab = FacadeBridge().analyze_stability(data.states[0], data.times[0], data.mu)
    assert stab.monodromy_matrix.shape == (6, 6)
    assert stab.eigenvalues.shape == (6,)
    assert set(stab.stability_indices) == {"nu1", "nu2", "nu3", "broucke"}
    assert "stability_type" in stab.classification
