"""tests for src.engine.facade_bridge -- DTO + TOOL_REGISTRY + design_orbit。"""

from __future__ import annotations

import numpy as np
import pytest

from src.engine.facade_bridge import (
    TOOL_REGISTRY,
    FacadeBridge,
    OrbitDesignResultData,
    ToolSpec,
)


class TestOrbitDesignResultData:
    def test_dto_has_no_e2m2e_reference(self):
        """DTO 不应包含 e2m2e Orbit 对象引用。"""
        field_names = {f.name for f in OrbitDesignResultData.__dataclass_fields__.values()}
        assert "cr3bp_orbit" not in field_names, (
            "DTO 不应包含 cr3bp_orbit 字段（e2m2e Orbit 对象引用）"
        )

    def test_dto_numpy_fields(self, mock_design_orbit):
        """states/times 应为 numpy ndarray。"""
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert isinstance(data.states, np.ndarray)
        assert isinstance(data.times, np.ndarray)

    def test_dto_field_count(self):
        """DTO 字段数稳定（防止意外增减）。"""
        assert len(OrbitDesignResultData.__dataclass_fields__) == 9


class TestToolSpec:
    def test_frozen(self):
        spec = ToolSpec(request_model=None, facade_method="m", label="L", enabled=True)
        with pytest.raises(AttributeError):
            spec.label = "X"  # type: ignore[misc]


class TestToolRegistry:
    def test_completeness(self):
        """TOOL_REGISTRY 包含且仅包含 4 个工具。"""
        expected = {"design_orbit", "control_orbit", "orbit_family_generation", "orbit_stability"}
        assert set(TOOL_REGISTRY.keys()) == expected

    def test_design_orbit_enabled(self):
        assert TOOL_REGISTRY["design_orbit"].enabled is True

    def test_others_disabled(self):
        for name in ("control_orbit", "orbit_family_generation", "orbit_stability"):
            assert TOOL_REGISTRY[name].enabled is False, f"{name} 应为 disabled"

    def test_facade_methods_defined(self):
        """每个注册工具都必须有 facade_method。"""
        for name, spec in TOOL_REGISTRY.items():
            assert spec.facade_method, f"{name}.facade_method 为空"

    def test_labels_non_empty(self):
        for name, spec in TOOL_REGISTRY.items():
            assert spec.label, f"{name}.label 为空"


class TestFacadeBridgeDesignOrbit:
    def test_returns_dto(self, mock_design_orbit):
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert isinstance(data, OrbitDesignResultData)

    def test_states_shape(self, mock_design_orbit, fake_design_result):
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert data.states.shape == fake_design_result.cr3bp_orbit.states.shape

    def test_kernel_dir_forwarded(self, monkeypatch):
        """kernel_dir 参数应被注入到 e2m2e 调用中。"""
        captured: dict = {}

        def _capture(**kwargs):
            captured.update(kwargs)
            from types import SimpleNamespace

            n = 10
            orbit = SimpleNamespace(
                states=np.random.randn(n, 6),
                times=np.linspace(0, 1, n),
            )
            correction = SimpleNamespace(converged=True, iterations=1)
            return SimpleNamespace(
                orbit_type="DRO",
                epoch_utc="2024-01-01T00:00:00",
                duration_day=1.0,
                initial_state=np.zeros(6),
                cr3bp_jacobi=3.0,
                cr3bp_orbit=orbit,
                correction=correction,
            )

        monkeypatch.setattr(
            "e2m2e.algorithm.design.design_orbit", _capture, raising=False
        )
        bridge = FacadeBridge(kernel_dir="/tmp/kernels")
        bridge.design_orbit(orbit_type="DRO")
        assert captured.get("kernel_dir") == "/tmp/kernels"

    def test_orbit_error_translated(self, monkeypatch):
        """e2m2e 异常应被翻译为 OrbitError。"""
        from src.engine.exceptions import OrbitError

        def _fail(**kwargs):
            raise ValueError("bad amplitude")

        monkeypatch.setattr(
            "e2m2e.algorithm.design.design_orbit", _fail, raising=False
        )
        bridge = FacadeBridge()
        with pytest.raises(OrbitError) as exc_info:
            bridge.design_orbit(orbit_type="DRO", amplitude=-1)
        assert exc_info.value.code == "INVALID_PARAMS"
