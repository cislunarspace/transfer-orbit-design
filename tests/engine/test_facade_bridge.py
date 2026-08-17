"""tests for src.engine.facade_bridge -- DTO + TOOL_REGISTRY + design_orbit。"""

from __future__ import annotations

import numpy as np
import pytest
from e2m2e.data.templates import ConvergenceState
from e2m2e.data.templates.seed import EARTH_MOON_MU

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
        assert len(OrbitDesignResultData.__dataclass_fields__) == 11

    def test_dto_has_mu_field(self):
        """DTO 应包含 mu 字段（issue #339 地月标注数据流）。"""
        assert "mu" in OrbitDesignResultData.__dataclass_fields__


class TestToolSpec:
    def test_frozen(self):
        spec = ToolSpec(
            request_model=None, facade_method="m", label="L", description="D", enabled=True
        )
        with pytest.raises(AttributeError):
            spec.label = "X"  # type: ignore[misc]


class TestToolRegistry:
    def test_completeness(self):
        """TOOL_REGISTRY 与 e2m2e facade 工具清单（mcp_tools）对齐。"""
        from e2m2e.api import Facade, mcp_tools

        facade_names = set(mcp_tools(Facade()))
        assert set(TOOL_REGISTRY.keys()) == facade_names

    def test_enabled_subset(self):
        """仅 GUI 已接入的工具 enabled，其余灰显。"""
        assert set(TOOL_REGISTRY) - {
            "design_orbit",
            "control_orbit",
            "orbit_family_generation",
        } == {n for n, s in TOOL_REGISTRY.items() if not s.enabled}

    def test_design_orbit_enabled(self):
        assert TOOL_REGISTRY["design_orbit"].enabled is True

    def test_control_orbit_enabled(self):
        """issue #348: control_orbit 已激活。"""
        assert TOOL_REGISTRY["control_orbit"].enabled is True

    def test_family_generation_enabled(self):
        """issue #340: orbit_family_generation 已激活（e2m2e 族延拓接入）。"""
        assert TOOL_REGISTRY["orbit_family_generation"].enabled is True
        assert TOOL_REGISTRY["orbit_family_generation"].request_model is not None

    def test_stability_disabled_in_tool_combo(self):
        """orbit_stability 无参数面板，工具下拉保持灰显（右键菜单入口）。"""
        assert TOOL_REGISTRY["orbit_stability"].enabled is False

    def test_first_enabled_tool_is_design_orbit(self):
        """默认工具 = 第一个 enabled（工具下拉初始选中，须为轨道设计）。"""
        for name, spec in TOOL_REGISTRY.items():
            if spec.enabled:
                assert name == "design_orbit"
                return
        pytest.fail("无 enabled 工具")

    def test_facade_method_matches_tool_key(self):
        """facade_method 是 e2m2e facade 方法名（== 工具 key，与 mcp_tools 对齐）。"""
        for name, spec in TOOL_REGISTRY.items():
            assert spec.facade_method == name, f"{name}.facade_method != 工具 key"

    def test_labels_non_empty(self):
        for name, spec in TOOL_REGISTRY.items():
            assert spec.label, f"{name}.label 为空"

    def test_descriptions_non_empty(self):
        """每个工具都应有工具说明（面板顶部展示）。"""
        for name, spec in TOOL_REGISTRY.items():
            assert spec.description, f"{name}.description 为空"

    def test_disabled_tool_descriptions_follow_inventory_status(self):
        """非 GUI 工具的“已实现/占位”说明以 e2m2e 清单为准。"""
        from e2m2e.api import Facade, tool_inventory

        status_notes = {
            "implemented": "e2m2e 已实现，GUI 尚未接入",
            "placeholder": "e2m2e 占位，未实现",
        }
        inventory = {info.name: info for info in tool_inventory(Facade())}
        gui_integrated = {
            "design_orbit",
            "control_orbit",
            "orbit_family_generation",
            "orbit_stability",
        }
        for name, info in inventory.items():
            if name in gui_integrated:
                continue
            assert status_notes[info.status] in TOOL_REGISTRY[name].description


class TestFacadeBridgeDesignOrbit:
    def test_returns_dto(self, mock_design_orbit):
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert isinstance(data, OrbitDesignResultData)

    def test_mu_extracted_from_orbit_system(self, monkeypatch):
        """mu 应从 cr3bp_orbit.system.mu 提取（issue #339 实测路径）。"""
        from types import SimpleNamespace

        n = 10
        orbit = SimpleNamespace(
            states=np.random.randn(n, 6),
            times=np.linspace(0, 1, n),
            system=SimpleNamespace(mu=EARTH_MOON_MU),
        )
        correction = SimpleNamespace(status=ConvergenceState.CONVERGED, iterations=1)
        result = SimpleNamespace(
            orbit_type="DRO",
            epoch_utc="2024-01-01T00:00:00",
            duration_day=1.0,
            initial_state=np.zeros(6),
            cr3bp_jacobi=3.0,
            cr3bp_orbit=orbit,
            correction=correction,
        )

        def _fake_design_orbit(request, *, spice=None, kernel_dir=None, verbose=False):
            return result

        monkeypatch.setattr(
            "e2m2e.algorithm.design.design_orbit",
            _fake_design_orbit,
            raising=False,
        )
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert data.mu == pytest.approx(EARTH_MOON_MU)

    def test_mu_is_none_when_orbit_has_no_system(self, mock_design_orbit):
        """system 缺失（旧 fake / 无上下文）时 mu 为 None，不崩溃。"""
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert data.mu is None

    def test_states_shape(self, mock_design_orbit, fake_design_result):
        bridge = FacadeBridge()
        data = bridge.design_orbit(orbit_type="DRO")
        assert data.states.shape == fake_design_result.cr3bp_orbit.states.shape

    def test_kernel_dir_forwarded(self, monkeypatch):
        """kernel_dir 应作为 design_orbit 的关键字参数注入；request 为位置参数。"""
        from e2m2e.api.models import DesignOrbitRequest

        captured: dict = {}

        def _capture(request, *, spice=None, kernel_dir=None, verbose=False):
            captured["request"] = request
            captured["kernel_dir"] = kernel_dir
            from types import SimpleNamespace

            n = 10
            orbit = SimpleNamespace(
                states=np.random.randn(n, 6),
                times=np.linspace(0, 1, n),
            )
            correction = SimpleNamespace(status=ConvergenceState.CONVERGED, iterations=1)
            return SimpleNamespace(
                orbit_type="DRO",
                epoch_utc="2024-01-01T00:00:00",
                duration_day=1.0,
                initial_state=np.zeros(6),
                cr3bp_jacobi=3.0,
                cr3bp_orbit=orbit,
                correction=correction,
            )

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _capture, raising=False)
        bridge = FacadeBridge(kernel_dir="/tmp/kernels")
        bridge.design_orbit(orbit_type="DRO")
        # 守住接缝：facade 必须构造 DesignOrbitRequest 并以位置参传入，
        # kernel_dir 以关键字参传入（非 request 字段）。
        assert isinstance(captured.get("request"), DesignOrbitRequest)
        assert captured["request"].orbit_type == "DRO"
        assert captured.get("kernel_dir") == "/tmp/kernels"

    def test_duration_converts_years_to_seconds(self, monkeypatch):
        """GUI duration 单位年，e2m2e 5.6.5 duration 单位秒；facade 做换算。"""

        captured: dict = {}

        def _capture(request, *, spice=None, kernel_dir=None, verbose=False):
            captured["duration"] = request.duration
            from types import SimpleNamespace

            n = 10
            orbit = SimpleNamespace(
                states=np.random.randn(n, 6),
                times=np.linspace(0, 1, n),
            )
            correction = SimpleNamespace(status=ConvergenceState.CONVERGED, iterations=1)
            return SimpleNamespace(
                orbit_type="DRO",
                epoch_utc="2024-01-01T00:00:00",
                duration_day=1.0,
                initial_state=np.zeros(6),
                cr3bp_jacobi=3.0,
                cr3bp_orbit=orbit,
                correction=correction,
            )

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _capture, raising=False)
        bridge = FacadeBridge()
        # 1 年（GUI 标准单位）应被换算成 1 年的秒数
        bridge.design_orbit(orbit_type="DRO", duration=1.0)
        from src.commons.units import SECONDS_PER_YEAR

        assert captured["duration"] == pytest.approx(SECONDS_PER_YEAR)
        # 0.5 年 -> 半年秒数
        bridge.design_orbit(orbit_type="DRO", duration=0.5)
        assert captured["duration"] == pytest.approx(0.5 * SECONDS_PER_YEAR)

    @pytest.mark.parametrize(
        ("orbit_type", "correction_method", "expected_method"),
        [
            ("Lissajous", "two_level", "segmented"),
            ("LISSAJOUS", "standard", "segmented"),
            ("DRO", "standard", "standard"),
        ],
    )
    def test_lissajous_uses_segmented_correction(
        self, monkeypatch, orbit_type, correction_method, expected_method
    ):
        """Lissajous 不得走一圈修正后自由外推的常规修正路径。"""
        captured: dict = {}

        def _capture(request, *, spice=None, kernel_dir=None, verbose=False):
            captured["correction_method"] = request.correction_method
            from types import SimpleNamespace

            orbit = SimpleNamespace(
                states=np.zeros((2, 6)),
                times=np.array([0.0, 1.0]),
            )
            correction = SimpleNamespace(status=ConvergenceState.CONVERGED, iterations=1)
            return SimpleNamespace(
                orbit_type=orbit_type,
                epoch_utc="2024-01-01T00:00:00",
                duration_day=1.0,
                initial_state=np.zeros(6),
                cr3bp_jacobi=3.0,
                cr3bp_orbit=orbit,
                correction=correction,
            )

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _capture, raising=False)

        FacadeBridge().design_orbit(
            orbit_type=orbit_type,
            correction_method=correction_method,
        )

        assert captured["correction_method"] == expected_method

    def test_orbit_error_translated(self, monkeypatch):
        """e2m2e 异常应被翻译为 OrbitError。"""
        from src.engine.exceptions import OrbitError

        def _fail(request, *, spice=None, kernel_dir=None, verbose=False):
            raise ValueError("bad amplitude")

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _fail, raising=False)
        bridge = FacadeBridge()
        with pytest.raises(OrbitError) as exc_info:
            # amplitude=50 < DRO 下限 1737 km，触发 model_validator ValueError
            bridge.design_orbit(orbit_type="DRO", amplitude=50.0)
        assert exc_info.value.code == "INVALID_PARAMS"

    def test_nrho_uses_full_design_orbit_pipeline(self, monkeypatch):
        """e2m2e 5.7.3 起 NRHO 走完整 design_orbit（不再旁路只交 CR3BP）。"""
        captured: dict = {}

        def _capture(request, *, spice=None, kernel_dir=None, verbose=False):
            captured["orbit_type"] = request.orbit_type
            captured["kernel_dir"] = kernel_dir
            from types import SimpleNamespace

            system = SimpleNamespace(mu=0.01215)
            orbit = SimpleNamespace(
                states=np.zeros((4, 6)),
                times=np.linspace(0.0, 1.0, 4),
                system=system,
            )
            correction = SimpleNamespace(
                status=ConvergenceState.CONVERGED, iterations=5
            )
            return SimpleNamespace(
                orbit_type="NRHO",
                epoch_utc="2024-01-01T00:00:00",
                duration_day=30.0,
                initial_state=np.zeros(6),
                cr3bp_jacobi=3.03,
                cr3bp_orbit=orbit,
                correction=correction,
                ephemeris=None,
            )

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _capture, raising=False)

        data = FacadeBridge(kernel_dir="/tmp/kernels").design_orbit(
            orbit_type="NRHO",
            collinear_point=2,
            north_south=2,
            perilune_height=5000.0,
            phase=0.5,
            duration=1.0 / 12.0,
        )

        assert captured["orbit_type"].upper() == "NRHO"
        assert captured["kernel_dir"] == "/tmp/kernels"
        assert data.orbit_type == "NRHO"
        assert data.correction_converged is True
        assert data.correction_iterations == 5
