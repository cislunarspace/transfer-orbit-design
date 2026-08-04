"""测试 fixtures -- mock e2m2e 算法层调用。"""

from __future__ import annotations

import numpy as np
import pytest


class _FakeCorrection:
    """Fake EphemerisCorrectionResult（只保留 converged/iterations）。"""

    def __init__(self, converged: bool = True, iterations: int = 3) -> None:
        self.converged = converged
        self.iterations = iterations


class _FakeOrbit:
    """Fake Orbit（e2m2e.data.types.orbit.Orbit）。"""

    def __init__(self, states: np.ndarray, times: np.ndarray) -> None:
        self.states = states
        self.times = times


class _FakeDesignResult:
    """Fake OrbitDesignResult（e2m2e.algorithm.design.design_orbit）。"""

    def __init__(
        self,
        orbit_type: str = "DRO",
        epoch_utc: str = "2024-01-01T00:00:00",
        duration_day: float = 365.25,
        initial_state: np.ndarray | None = None,
        cr3bp_jacobi: float = 3.0058,
        states: np.ndarray | None = None,
        times: np.ndarray | None = None,
        converged: bool = True,
        iterations: int = 3,
    ) -> None:
        n = 8761 if states is None else states.shape[0]
        self.orbit_type = orbit_type
        self.epoch_utc = epoch_utc
        self.duration_day = duration_day
        self.initial_state = (
            initial_state if initial_state is not None else np.zeros(6)
        )
        self.cr3bp_jacobi = cr3bp_jacobi
        self.cr3bp_orbit = _FakeOrbit(
            states=states if states is not None else np.random.randn(n, 6),
            times=times if times is not None else np.linspace(0, 1, n),
        )
        self.correction = _FakeCorrection(converged=converged, iterations=iterations)


@pytest.fixture()
def fake_design_result() -> _FakeDesignResult:
    """默认 _FakeDesignResult（DRO, 8761 点）。"""
    return _FakeDesignResult()


@pytest.fixture()
def mock_design_orbit(monkeypatch, fake_design_result):
    """Monkeypatch e2m2e.algorithm.design.design_orbit，返回 fake_design_result。"""

    def _fake_design_orbit(**kwargs):
        return fake_design_result

    monkeypatch.setattr(
        "e2m2e.algorithm.design.design_orbit",
        _fake_design_orbit,
        raising=False,
    )
    return _fake_design_orbit
