"""tests for FacadeBridge.generate_family / analyze_stability（轨道族生成 + 稳定性分析）。

mock 测试验证 DTO 装配与参数透传；末尾两个真路径测试用真实 e2m2e 算法层
（纯 CR3BP，不需要 SPICE 内核），守住"族延拓真能跑"的底线。
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
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
    def test_defaults(self):
        req = FamilyGenerationRequest()
        assert req.libration_point == 2
        assert req.max_amplitude_km == 30000.0
        assert req.n_orbits == 20

    def test_constraints(self):
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(libration_point=3)  # le=2
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(libration_point=0)  # ge=1
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(max_amplitude_km=100.0)  # ge=1000
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(max_amplitude_km=100000.0)  # le=57000
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(n_orbits=1)  # ge=2

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            FamilyGenerationRequest(orbit_type="HALO")  # 未知字段


# ---------------------------------------------------------------------------
# generate_family mock 测试
# ---------------------------------------------------------------------------


class _FakeSystem:
    """Fake CR3BP_System（earth_moon_system 的替身）。"""

    mu = 0.012150585350562453
    characteristic_length = 384400.0


class _FakeContinuation:
    """Fake Continuation（generate_halo_seed_orbit / generate_halo_family 替身）。"""

    def __init__(self, corrector=None) -> None:
        self.calls: dict = {}

    def generate_halo_seed_orbit(self, *args, **kwargs) -> object:
        self.calls["seed"] = (args, kwargs)
        return SimpleNamespace(
            states=np.random.randn(100, 6),
            times=np.linspace(0, 1, 100),
        )

    def generate_halo_family(self, seed, **kwargs) -> list[object]:
        self.calls["family"] = kwargs
        n = kwargs.get("n_orbits", 3)
        return [
            SimpleNamespace(
                states=np.random.randn(100, 6),
                times=np.linspace(0, 1, 100),
            )
            for _ in range(n)
        ]


@pytest.fixture()
def mock_family_stack(monkeypatch):
    """把 generate_family 的算法调用全部桩掉，返回可断言调用的 fake。"""
    fake_cont = _FakeContinuation()

    monkeypatch.setattr(
        "e2m2e.algorithm.family.cr3bp_orbits.earth_moon_system",
        lambda: _FakeSystem(),
        raising=False,
    )
    monkeypatch.setattr(
        "e2m2e.algorithm.dynamics.CR3BP_Dynamics",
        lambda system: object(),
        raising=False,
    )
    monkeypatch.setattr(
        "e2m2e.algorithm.solver.differential_correction.DifferentialCorrection",
        lambda dynamics: object(),
        raising=False,
    )
    monkeypatch.setattr(
        "e2m2e.algorithm.solver.continuation.Continuation",
        lambda corrector: fake_cont,
        raising=False,
    )
    return fake_cont


class TestGenerateFamily:
    def test_returns_dto(self, mock_family_stack):
        data = FacadeBridge().generate_family(
            libration_point=2, max_amplitude_km=20000.0, n_orbits=5
        )
        assert isinstance(data, FamilyResultData)
        assert data.orbit_type == "Halo"
        assert data.n_orbits == 5
        assert data.states.shape == (5, 100, 6)
        assert data.times.shape == (5, 100)
        assert data.z0s.shape == (5,)
        assert data.mu == pytest.approx(0.012150585350562453)

    def test_seed_uses_small_amplitude(self, mock_family_stack):
        """种子振幅必须取 0.001 DU（Richardson 收敛域），不得透传用户振幅。"""
        FacadeBridge().generate_family(libration_point=1, max_amplitude_km=10000.0, n_orbits=3)
        _, seed_kwargs = mock_family_stack.calls["seed"]
        assert seed_kwargs["amplitude_z"] == pytest.approx(0.001)
        assert seed_kwargs["halo_class"] == 0

    def test_z_range_derived_from_km(self, mock_family_stack):
        """max_amplitude_km 应换算为无量纲 z_range，且含种子端点。"""
        FacadeBridge().generate_family(libration_point=2, max_amplitude_km=38440.0, n_orbits=4)
        kwargs = mock_family_stack.calls["family"]
        z_min, z_max = kwargs["z_range"]
        assert z_min == pytest.approx(0.001)
        assert z_max == pytest.approx(0.1)  # 38440 / 384400
        assert kwargs["direction"] == "positive"
        assert kwargs["n_orbits"] == 4

    def test_invalid_params_translated(self, mock_family_stack):
        """非法参数经 FamilyGenerationRequest 校验 → OrbitError(INVALID_PARAMS)。"""
        from src.engine.exceptions import OrbitError

        with pytest.raises(OrbitError) as exc_info:
            FacadeBridge().generate_family(libration_point=9, max_amplitude_km=20000.0, n_orbits=5)
        assert exc_info.value.code == "INVALID_PARAMS"


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
        from e2m2e.data.templates.seed import EARTH_MOON_MU

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
