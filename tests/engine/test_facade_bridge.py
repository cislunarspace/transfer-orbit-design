"""tests for src.engine.facade_bridge -- DTO + TOOL_REGISTRY + design_orbit。"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from e2m2e.data.templates.seed import EARTH_MOON_MU

from src.engine.facade_bridge import (
    TOOL_REGISTRY,
    FacadeBridge,
    OrbitDesignResultData,
    ToolSpec,
)
from tests.engine.conftest import _FakeDesignResult


class TestOrbitDesignResultData:
    def test_dto_has_no_e2m2e_reference(self):
        """DTO 不应包含 e2m2e Orbit 对象引用。"""
        field_names = {f.name for f in OrbitDesignResultData.__dataclass_fields__.values()}
        assert "cr3bp_orbit" not in field_names, (
            "DTO 不应包含 cr3bp_orbit 字段（e2m2e Orbit 对象引用）"
        )

    def test_dto_numpy_fields(self, mock_design_orbit, catalog_bridge):
        """states/times 应为 numpy ndarray。"""
        data = catalog_bridge.design_orbit(orbit_type="DRO")
        assert isinstance(data.states, np.ndarray)
        assert isinstance(data.times, np.ndarray)

    def test_dto_field_count(self):
        """DTO 字段数稳定（防止意外增减）。"""
        assert len(OrbitDesignResultData.__dataclass_fields__) == 12

    def test_dto_has_mu_field(self):
        """DTO 应包含 mu 字段（issue #339 地月月标注数据流）。"""
        assert "mu" in OrbitDesignResultData.__dataclass_fields__

    def test_dto_has_record_id_field(self):
        """DTO 应包含 record_id 字段（issue #375 产物入库回执）。"""
        assert "record_id" in OrbitDesignResultData.__dataclass_fields__


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
    def test_returns_dto(self, mock_design_orbit, catalog_bridge):
        data = catalog_bridge.design_orbit(orbit_type="DRO")
        assert isinstance(data, OrbitDesignResultData)

    def test_mu_extracted_from_orbit_system(self, monkeypatch, catalog_bridge):
        """mu 应从 cr3bp_orbit.system.mu 提取（issue #339 实测路径）。"""
        result = _FakeDesignResult(system=SimpleNamespace(mu=EARTH_MOON_MU))

        monkeypatch.setattr(
            "e2m2e.algorithm.design.design_orbit",
            lambda request, *, spice=None, kernel_dir=None, verbose=False: result,
            raising=False,
        )
        data = catalog_bridge.design_orbit(orbit_type="DRO")
        assert data.mu == pytest.approx(EARTH_MOON_MU)

    def test_mu_is_none_when_orbit_has_no_system(self, mock_design_orbit, catalog_bridge):
        """system 缺失（旧 fake / 无上下文）时 mu 为 None，不崩溃。"""
        data = catalog_bridge.design_orbit(orbit_type="DRO")
        assert data.mu is None

    def test_states_shape(self, mock_design_orbit, catalog_bridge, fake_design_result):
        data = catalog_bridge.design_orbit(orbit_type="DRO")
        assert data.states.shape == fake_design_result.cr3bp_orbit.states.shape

    def test_kernel_dir_forwarded(self, monkeypatch, tmp_path):
        """kernel_dir 经 Config 注入 Facade，转发到算法层调用。"""
        captured: dict = {}

        def _capture(request, *, spice=None, kernel_dir=None, verbose=False):
            captured["kernel_dir"] = kernel_dir
            return _FakeDesignResult(states=np.random.randn(10, 6),
                                     times=np.linspace(0, 1, 10))

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _capture, raising=False)
        bridge = FacadeBridge(kernel_dir="/tmp/kernels", catalog_dir=str(tmp_path / "c"))
        bridge.design_orbit(orbit_type="DRO")
        # 守住接缝：kernel_dir 经 Config 注入（非 request 字段），算法层收到
        assert captured.get("kernel_dir") == "/tmp/kernels"

    def test_duration_converts_years_to_seconds(self, monkeypatch, catalog_bridge):
        """GUI duration 单位年，e2m2e duration 单位秒；facade 做换算。"""

        captured: dict = {}

        def _capture(request, *, spice=None, kernel_dir=None, verbose=False):
            captured["duration"] = request.duration
            return _FakeDesignResult(states=np.random.randn(10, 6),
                                     times=np.linspace(0, 1, 10))

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _capture, raising=False)
        # 1 年（GUI 标准单位）应被换算成 1 年的秒数
        catalog_bridge.design_orbit(orbit_type="DRO", duration=1.0)
        from src.commons.units import SECONDS_PER_YEAR

        assert captured["duration"] == pytest.approx(SECONDS_PER_YEAR)
        # 0.5 年 -> 半年秒数
        catalog_bridge.design_orbit(orbit_type="DRO", duration=0.5)
        assert captured["duration"] == pytest.approx(0.5 * SECONDS_PER_YEAR)

    @pytest.mark.parametrize(
        ("orbit_type", "correction_method", "expected_method"),
        [
            ("Lissajous", "two_level", "segmented"),
            ("LISSAJOUS", "standard", "segmented"),
            ("DRO", "two_level", "two_level"),
            ("DPO", "two_level", "two_level"),
        ],
    )
    def test_lissajous_uses_segmented_correction(
        self, monkeypatch, catalog_bridge, orbit_type, correction_method, expected_method
    ):
        """Lissajous 不得走一圈修正后自由外推的常规修正路径。"""
        captured: dict = {}

        def _capture(request, *, spice=None, kernel_dir=None, verbose=False):
            captured["correction_method"] = request.correction_method
            return _FakeDesignResult(orbit_type=orbit_type,
                                     states=np.zeros((2, 6)),
                                     times=np.array([0.0, 1.0]))

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _capture, raising=False)

        catalog_bridge.design_orbit(
            orbit_type=orbit_type,
            correction_method=correction_method,
        )

        assert captured["correction_method"] == expected_method

    def test_orbit_error_translated(self, monkeypatch, catalog_bridge):
        """e2m2e 异常应被翻译为 OrbitError。"""
        from src.engine.exceptions import OrbitError

        def _fail(request, *, spice=None, kernel_dir=None, verbose=False):
            raise ValueError("bad amplitude")

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _fail, raising=False)
        with pytest.raises(OrbitError) as exc_info:
            # amplitude=50 < DRO 下限 1737 km，触发 model_validator ValueError
            catalog_bridge.design_orbit(orbit_type="DRO", amplitude=50.0)
        assert exc_info.value.code == "INVALID_PARAMS"

    def test_nrho_uses_full_design_orbit_pipeline(self, monkeypatch, tmp_path):
        """e2m2e 5.7.3 起 NRHO 走完整 design_orbit（不再旁路只交 CR3BP）。"""
        captured: dict = {}

        def _capture(request, *, spice=None, kernel_dir=None, verbose=False):
            captured["orbit_type"] = request.orbit_type
            captured["kernel_dir"] = kernel_dir
            return _FakeDesignResult(
                orbit_type="NRHO",
                states=np.zeros((4, 6)),
                times=np.linspace(0.0, 1.0, 4),
                system=SimpleNamespace(mu=0.01215),
                iterations=5,
                duration_day=30.0,
            )

        monkeypatch.setattr("e2m2e.algorithm.design.design_orbit", _capture, raising=True)

        bridge = FacadeBridge(kernel_dir="/tmp/kernels", catalog_dir=str(tmp_path / "c"))
        data = bridge.design_orbit(
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


class TestDesignOrbitCatalogIngest:
    """issue #375 US8：design_orbit 经 Facade 调用且产物自动入库。"""

    def test_computation_leaves_record_in_catalog(self, mock_design_orbit, catalog_bridge):
        """计算成功后库中出现对应记录（record_id 即主键）。"""
        data = catalog_bridge.design_orbit(orbit_type="DRO")
        assert data.record_id is not None
        records = catalog_bridge.catalog_query()
        assert [r.record_id for r in records] == [data.record_id]
        assert records[0].source_tool == "design_orbit"

    def test_query_filters_by_family(self, mock_design_orbit, catalog_bridge):
        """catalog_query 多维过滤生效（族维度）。"""
        catalog_bridge.design_orbit(orbit_type="DRO")
        assert catalog_bridge.catalog_query(orbit_family="dro")
        assert not catalog_bridge.catalog_query(orbit_family="halo")

    def test_catalog_get_returns_arrays(self, mock_design_orbit, catalog_bridge):
        """catalog_get 返回完整记录（含 CR3BP 段数组）。"""
        data = catalog_bridge.design_orbit(orbit_type="DRO")
        record = catalog_bridge.catalog_get(data.record_id)
        assert record.arrays["cr3bp/states"].shape[0] == data.states.shape[0]

    def test_export_package_contains_records_and_manifest(
        self, mock_design_orbit, catalog_bridge, tmp_path
    ):
        """教学案例包内容：records/<id>.json/.npz + manifest.json（Testing Decisions）。"""
        import json
        import zipfile

        data = catalog_bridge.design_orbit(orbit_type="DRO")
        dest = tmp_path / "cases.zip"
        count = catalog_bridge.catalog_export(dest=str(dest), orbit_family="dro")
        assert count == 1
        with zipfile.ZipFile(dest) as bundle:
            names = bundle.namelist()
            assert f"records/{data.record_id}.json" in names
            assert f"records/{data.record_id}.npz" in names
            manifest = json.loads(bundle.read("manifest.json"))
        assert manifest == {
            "schema_version": 1,
            "record_ids": [data.record_id],
            "exported_count": 1,
        }
