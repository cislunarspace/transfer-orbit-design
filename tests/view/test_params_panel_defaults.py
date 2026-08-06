"""tests for src.view.params_panel -- per-orbit-type defaults and field filtering.

轨道设计工具按 orbit_type 分支：选 DRO/NRHO/Halo/Lissajous/L4/L5 时，
参数面板只显示该分支相关字段，并把相关字段填上合理默认值
（对齐 e2m2e algorithm/design/design_orbit.py 的 None 兜底默认值）。
"""

from __future__ import annotations

import pytest
from e2m2e.api.models import DesignOrbitRequest

# 与 src/view/params_panel.py 的 ORBIT_TYPE_DEFAULTS / ORBIT_TYPE_FIELDS 对齐的期望值
# （从 e2m2e design_orbit.py 各分支兜底默认值抄录，测试与实现共用同一事实来源）

_EXPECTED_DEFAULTS: dict[str, dict[str, float | int]] = {
    "DRO": {"amplitude": 10000.0, "phase": 0.5001},
    "NRHO": {
        "collinear_point": 2,
        "north_south": 2,
        "perilune_height": 5000.0,
        "phase": 0.5,
    },
    "Halo": {"collinear_point": 2, "amplitude": 30000.0, "phase": 0.0},
    "Lissajous": {
        "collinear_point": 2,
        "amplitude_in": 2500.0,
        "amplitude_out": 7500.0,
        "phase_in": 0.01,
        "phase_out": 0.55,
    },
    "L4": {
        "amplitude_in": 8000.0,
        "amplitude_out": 6000.0,
        "phase_in": 0.0,
        "phase_out": 0.0,
    },
    "L5": {
        "amplitude_in": 8000.0,
        "amplitude_out": 6000.0,
        "phase_in": 0.0,
        "phase_out": 0.0,
    },
}

_EXPECTED_FIELDS: dict[str, set[str]] = {
    "DRO": {"amplitude", "phase"},
    "NRHO": {"collinear_point", "north_south", "perilune_height", "phase"},
    "Halo": {"collinear_point", "amplitude", "phase"},
    "Lissajous": {
        "collinear_point",
        "amplitude_in",
        "amplitude_out",
        "phase_in",
        "phase_out",
    },
    "L4": {"amplitude_in", "amplitude_out", "phase_in", "phase_out"},
    "L5": {"amplitude_in", "amplitude_out", "phase_in", "phase_out"},
}

# 所有类型共享的通用字段（模型自带默认值，不属于任何分支）
_COMMON_FIELDS = {"orbit_type", "epoch", "duration", "output_step", "correction_method"}


@pytest.fixture()
def qapp():
    """确保 QApplication 存在（pytest-qt 自动提供，兜底手动创建）。"""
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


class TestOrbitTypeDefaults:
    def test_defaults_exist_for_all_types(self):
        """每个轨道类型都有默认值表条目。"""
        from src.view.params_panel import ORBIT_TYPE_DEFAULTS

        assert set(ORBIT_TYPE_DEFAULTS) == set(_EXPECTED_DEFAULTS)

    def test_defaults_match_e2m2e_fallback(self):
        """默认值对齐 e2m2e design_orbit 的 None 兜底值。"""
        from src.view.params_panel import ORBIT_TYPE_DEFAULTS

        for orbit_type, expected in _EXPECTED_DEFAULTS.items():
            actual = ORBIT_TYPE_DEFAULTS[orbit_type]
            for field, value in expected.items():
                assert field in actual, f"{orbit_type} 缺字段 {field}"
                assert actual[field] == pytest.approx(value), (
                    f"{orbit_type}.{field} 默认值 {actual[field]} != 期望 {value}"
                )

    def test_defaults_only_contain_model_fields(self):
        """默认值表只应引用 DesignOrbitRequest 的真实字段。"""
        from src.view.params_panel import ORBIT_TYPE_DEFAULTS

        model_fields = set(DesignOrbitRequest.model_fields)
        for orbit_type, defaults in ORBIT_TYPE_DEFAULTS.items():
            for field in defaults:
                assert field in model_fields, f"{orbit_type} 默认值含未知字段 {field}"


class TestOrbitTypeFields:
    def test_fields_exist_for_all_types(self):
        """每个轨道类型都有字段分支映射。"""
        from src.view.params_panel import ORBIT_TYPE_FIELDS

        assert set(ORBIT_TYPE_FIELDS) == set(_EXPECTED_FIELDS)

    def test_fields_match_expected(self):
        """字段分支映射与期望一致。"""
        from src.view.params_panel import ORBIT_TYPE_FIELDS

        for orbit_type, expected in _EXPECTED_FIELDS.items():
            assert set(ORBIT_TYPE_FIELDS[orbit_type]) == expected, (
                f"{orbit_type} 字段分支 {ORBIT_TYPE_FIELDS[orbit_type]} != {expected}"
            )

    def test_fields_only_contain_model_fields(self):
        """字段分支只应引用 DesignOrbitRequest 的真实字段。"""
        from src.view.params_panel import ORBIT_TYPE_FIELDS

        model_fields = set(DesignOrbitRequest.model_fields)
        for orbit_type, fields in ORBIT_TYPE_FIELDS.items():
            for field in fields:
                assert field in model_fields, f"{orbit_type} 字段分支含未知字段 {field}"

    def test_each_branch_defaults_match_fields(self):
        """每个分支的默认值字段 = 该分支显示字段（默认值不应含分支外字段）。"""
        from src.view.params_panel import ORBIT_TYPE_DEFAULTS, ORBIT_TYPE_FIELDS

        for orbit_type in ORBIT_TYPE_DEFAULTS:
            assert set(ORBIT_TYPE_DEFAULTS[orbit_type]) == ORBIT_TYPE_FIELDS[orbit_type], (
                f"{orbit_type} 默认值字段与显示字段不一致"
            )

    def test_all_optional_model_fields_covered(self):
        """所有 Optional 模型字段都应出现在某个分支（否则用户无法设置）。"""
        from src.view.params_panel import ORBIT_TYPE_FIELDS

        covered: set[str] = set()
        for fields in ORBIT_TYPE_FIELDS.values():
            covered |= fields

        optional_fields = {
            name
            for name, field in DesignOrbitRequest.model_fields.items()
            if field.is_required() is False and name not in _COMMON_FIELDS
        }
        for field in optional_fields:
            assert field in covered, f"Optional 字段 {field} 未出现在任何分支"


class TestApplyOrbitTypeDefaults:
    def test_apply_sets_widget_values(self, qapp):
        """apply_orbit_type_defaults 应把分支默认值填入控件。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import (
            ORBIT_TYPE_DEFAULTS,
            apply_orbit_type_defaults,
            build_params_from_model,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "DRO")

        # DRO 分支：amplitude -> QDoubleSpinBox 10000.0
        amp = widgets["amplitude"]
        assert isinstance(amp, QDoubleSpinBox)
        assert amp.value() == pytest.approx(ORBIT_TYPE_DEFAULTS["DRO"]["amplitude"])

    def test_apply_int_field(self, qapp):
        """整数默认值应填入 QSpinBox / QComboBox。"""
        from PyQt6.QtWidgets import QSpinBox

        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "NRHO")

        # collinear_point -> QSpinBox 2
        cp = widgets["collinear_point"]
        assert isinstance(cp, QSpinBox)
        assert cp.value() == 2

        # north_south -> 也是 QSpinBox（int + ge/le）
        ns = widgets["north_south"]
        assert isinstance(ns, QSpinBox)
        assert ns.value() == 2

    def test_apply_collect_params_roundtrip(self, qapp):
        """填默认值后 collect_params 应返回该分支的完整参数集。"""
        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
            collect_params,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "Halo")
        params = collect_params(widgets, DesignOrbitRequest)

        assert params["collinear_point"] == 2
        assert params["amplitude"] == pytest.approx(30000.0)
        assert params["phase"] == pytest.approx(0.0)

    def test_apply_unknown_type_no_crash(self, qapp):
        """未知轨道类型调用 apply 不应崩溃（无分支则保持原样）。"""
        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "UNKNOWN")  # 不应抛异常
