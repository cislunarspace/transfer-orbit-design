"""tests for src.view.params_panel units -- 显示单位切换（km↔DU、年↔TU、秒↔TU）。

参数面板可切换单位字段的换算逻辑。默认显示单位 = 标准单位（km/年/秒），
现有测试不受影响。
"""

from __future__ import annotations

import pytest
from e2m2e.api.models import DesignOrbitRequest


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


# ---------------------------------------------------------------------------
# 纯换算函数
# ---------------------------------------------------------------------------


class TestUnitsConversion:
    def test_du_km_from_e2m2e(self):
        """DU_KM 应对齐 e2m2e.data.templates 的 CHAR_LENGTH_KM。"""
        from e2m2e.data.templates import CHAR_LENGTH_KM

        from src.commons.units import DU_KM

        assert DU_KM == CHAR_LENGTH_KM == 384400.0

    def test_tu_seconds(self):
        """TU_SECONDS = CHAR_PERIOD_SEC / (2π)。"""
        import math

        from e2m2e.data.templates import CHAR_PERIOD_SEC

        from src.commons.units import TU_SECONDS

        assert pytest.approx(CHAR_PERIOD_SEC / (2.0 * math.pi)) == TU_SECONDS

    def test_km_du_roundtrip(self):
        from src.commons.units import du_to_km, km_to_du

        assert km_to_du(du_to_km(10000.0)) == pytest.approx(10000.0)
        assert du_to_km(km_to_du(10000.0)) == pytest.approx(10000.0)

    def test_years_tu_roundtrip(self):
        from src.commons.units import tu_to_years, years_to_tu

        assert years_to_tu(tu_to_years(1.0)) == pytest.approx(1.0)
        assert tu_to_years(years_to_tu(1.0)) == pytest.approx(1.0)

    def test_seconds_tu_roundtrip(self):
        from src.commons.units import seconds_to_tu, tu_to_seconds

        assert seconds_to_tu(tu_to_seconds(3600.0)) == pytest.approx(3600.0)


# ---------------------------------------------------------------------------
# 单位注册表
# ---------------------------------------------------------------------------


class TestFieldUnitOptions:
    def test_registry_fields(self):
        """注册表应覆盖全部可切换字段。"""
        from src.view.params_panel import FIELD_UNIT_OPTIONS

        assert set(FIELD_UNIT_OPTIONS) == {
            "amplitude",
            "perilune_height",
            "amplitude_in",
            "amplitude_out",
            "duration",
            "output_step",
        }

    def test_first_option_is_standard(self):
        """每字段首个选项是标准单位（to_standard == 1.0）。"""
        from src.view.params_panel import FIELD_UNIT_OPTIONS

        for field, options in FIELD_UNIT_OPTIONS.items():
            assert options[0].to_standard == pytest.approx(1.0), field

    def test_amplitude_du_factor(self):
        """amplitude 的 DU 选项 to_standard == DU_KM。"""
        from src.commons.units import DU_KM
        from src.view.params_panel import FIELD_UNIT_OPTIONS

        assert FIELD_UNIT_OPTIONS["amplitude"][1].to_standard == pytest.approx(DU_KM)


# ---------------------------------------------------------------------------
# 控件生成默认单位不破坏现有行为
# ---------------------------------------------------------------------------


class TestWidgetDefaultUnit:
    def test_amplitude_default_unit_km(self, qapp):
        """amplitude 默认显示单位为 km。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        amp = widgets["amplitude"]
        sb = amp.findChild(QDoubleSpinBox)
        assert sb is not None
        assert sb.property("__params_panel_unit") == "km"

    def test_phase_no_unit_property(self, qapp):
        """phase 无量纲，不应有单位属性。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        assert widgets["phase"].property("__params_panel_unit") is None

    def test_default_collect_is_standard(self, qapp):
        """默认（标准单位）下 collect 返回标准单位值。"""
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        params = collect_params(widgets, DesignOrbitRequest)
        assert params["amplitude"] is None  # Optional 未勾选
        assert params["output_step"] == 3600.0
        assert params["duration"] == 1.0


# ---------------------------------------------------------------------------
# set_spinbox_unit 换算与缩放
# ---------------------------------------------------------------------------


class TestSetSpinboxUnit:
    def test_switch_km_to_du(self, qapp):
        """amplitude 10000 km -> DU 应显示 10000/384400。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import (
            build_params_from_model,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["amplitude"].findChild(QDoubleSpinBox)
        assert sb is not None
        sb.setValue(10000.0)
        set_spinbox_unit(sb, "amplitude", "DU")

        from src.commons.units import DU_KM

        assert sb.value() == pytest.approx(10000.0 / DU_KM)
        assert sb.property("__params_panel_unit") == "DU"
        assert sb.decimals() >= 6

    def test_switch_back_restores_value(self, qapp):
        """DU 切回 km 后值近似复原。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import (
            build_params_from_model,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["amplitude"].findChild(QDoubleSpinBox)
        assert sb is not None
        sb.setValue(10000.0)
        set_spinbox_unit(sb, "amplitude", "DU")
        set_spinbox_unit(sb, "amplitude", "km")

        assert sb.value() == pytest.approx(10000.0, rel=1e-4)

    def test_duration_switch_to_tu(self, qapp):
        """duration 1 年 -> TU 应显示 1 年的 TU 数。"""

        from src.view.params_panel import build_params_from_model, set_spinbox_unit

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["duration"]
        sb.setValue(1.0)
        set_spinbox_unit(sb, "duration", "TU")

        from src.commons.units import SECONDS_PER_YEAR, TU_SECONDS

        assert sb.value() == pytest.approx(SECONDS_PER_YEAR / TU_SECONDS)


# ---------------------------------------------------------------------------
# 收集时换算 roundtrip
# ---------------------------------------------------------------------------


class TestCollectWithUnits:
    def test_collect_du_converts_to_km(self, qapp):
        """切 DU 后 setValue(0.026)，collect 应返回 0.026*DU_KM（km）。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.commons.units import DU_KM
        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
            collect_params,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "DRO", DesignOrbitRequest)
        sb = widgets["amplitude"]  # apply 后已解包为 QDoubleSpinBox
        assert isinstance(sb, QDoubleSpinBox)
        set_spinbox_unit(sb, "amplitude", "DU")
        sb.setValue(0.026)

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["amplitude"] == pytest.approx(0.026 * DU_KM)

    def test_apply_respects_current_unit(self, qapp):
        """切 DU 后再次 apply，amplitude 显示 10000/DU，collect 返回 10000 km。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.commons.units import DU_KM
        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
            collect_params,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "DRO", DesignOrbitRequest)
        sb = widgets["amplitude"]
        assert isinstance(sb, QDoubleSpinBox)
        set_spinbox_unit(sb, "amplitude", "DU")

        # 再次 apply DRO 默认值（标准单位 10000 km），应换算为 DU 显示
        apply_orbit_type_defaults(widgets, "DRO", DesignOrbitRequest)
        assert sb.value() == pytest.approx(10000.0 / DU_KM)

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["amplitude"] == pytest.approx(10000.0)
