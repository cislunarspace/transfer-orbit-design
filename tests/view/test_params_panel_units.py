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
            # 距离（km/m/DU）
            "amplitude",
            "perilune_height",
            "amplitude_in",
            "amplitude_out",
            "semi_major_axis",
            "max_amplitude_km",
            # 相位（周期份额/度/弧度）
            "phase",
            "phase_in",
            "phase_out",
            # 角度（度/rad）
            "inclination",
            "arg_of_pericenter",
            # 时间
            "duration",
            "output_step",
            "control_interval",
            "feedback_arc",
            "momentum_interval",
            # 长度列表容器（m/DU）
            "srp_offset_m",
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

        opts = {o.label: o for o in FIELD_UNIT_OPTIONS["amplitude"]}
        assert opts["DU"].to_standard == pytest.approx(DU_KM)
        # 国际单位 m：display m * 1e-3 = 标准 km
        assert opts["m"].to_standard == pytest.approx(1e-3)

    def test_duration_month_day_factors(self):
        """duration 含'月'(1/12 年)、'日'(1/DAYS_PER_YEAR 年) 显示单位。"""
        from src.commons.units import DAYS_PER_YEAR
        from src.view.params_panel import FIELD_UNIT_OPTIONS

        opts = {o.label: o for o in FIELD_UNIT_OPTIONS["duration"]}
        assert "月" in opts
        assert opts["月"].to_standard == pytest.approx(1.0 / 12.0)
        assert "日" in opts
        assert opts["日"].to_standard == pytest.approx(1.0 / DAYS_PER_YEAR)

    def test_duration_has_seconds_and_tu(self):
        """duration 含秒（国际单位）与 TU（归一化）选项。"""
        from src.commons.units import SECONDS_PER_YEAR, TU_SECONDS
        from src.view.params_panel import FIELD_UNIT_OPTIONS

        opts = {o.label: o for o in FIELD_UNIT_OPTIONS["duration"]}
        assert opts["秒"].to_standard == pytest.approx(1.0 / SECONDS_PER_YEAR)
        assert opts["TU"].to_standard == pytest.approx(TU_SECONDS / SECONDS_PER_YEAR)

    def test_control_interval_days_seconds_tu(self):
        """control_interval（标准 天）含秒与 TU 选项。"""
        from src.commons.units import TU_SECONDS
        from src.view.params_panel import FIELD_UNIT_OPTIONS

        opts = {o.label: o for o in FIELD_UNIT_OPTIONS["control_interval"]}
        assert opts["天"].to_standard == pytest.approx(1.0)
        assert opts["秒"].to_standard == pytest.approx(1.0 / 86400.0)
        assert opts["TU"].to_standard == pytest.approx(TU_SECONDS / 86400.0)

    def test_angle_fields_have_radian(self):
        """inclination/arg_of_pericenter（标准 度）含 rad 选项。"""
        import math

        from src.view.params_panel import FIELD_UNIT_OPTIONS

        opts = {o.label: o for o in FIELD_UNIT_OPTIONS["inclination"]}
        assert opts["rad"].to_standard == pytest.approx(180.0 / math.pi)


# ---------------------------------------------------------------------------
# 控件生成默认单位不破坏现有行为
# ---------------------------------------------------------------------------


class TestWidgetDefaultUnit:
    def test_amplitude_default_unit_km(self, qapp):
        """amplitude 默认显示单位为 km。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import _UNIT_ATTR, build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        amp = widgets["amplitude"]
        sb = amp.findChild(QDoubleSpinBox)
        assert sb is not None
        assert sb.property(_UNIT_ATTR) == "km"

    def test_phase_has_unit_options(self, qapp):
        """phase 可切单位（周期份额/度/弧度），单位状态存在 spinbox 上。"""
        from src.view.params_panel import _UNIT_ATTR, build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        assert widgets["phase"].property(_UNIT_ATTR) is None  # Optional 包装在容器上

        from src.view.params_panel import apply_orbit_type_defaults

        apply_orbit_type_defaults(widgets, "DRO")
        sb = widgets["phase"]
        from PyQt6.QtWidgets import QDoubleSpinBox

        assert isinstance(sb, QDoubleSpinBox)
        assert sb.property(_UNIT_ATTR) == "周期份额"

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
            _UNIT_ATTR,
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
        assert sb.property(_UNIT_ATTR) == "DU"
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

    def test_duration_switch_to_month(self, qapp):
        """duration 1 年 -> 月 应显示 12 月。"""
        from src.view.params_panel import build_params_from_model, set_spinbox_unit

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["duration"]
        sb.setValue(1.0)
        set_spinbox_unit(sb, "duration", "月")

        assert sb.value() == pytest.approx(12.0)

    def test_duration_switch_to_day(self, qapp):
        """duration 1 年 -> 日 应显示 DAYS_PER_YEAR 日。"""
        from src.commons.units import DAYS_PER_YEAR
        from src.view.params_panel import build_params_from_model, set_spinbox_unit

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["duration"]
        sb.setValue(1.0)
        set_spinbox_unit(sb, "duration", "日")

        assert sb.value() == pytest.approx(DAYS_PER_YEAR)


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
        apply_orbit_type_defaults(widgets, "DRO")
        sb = widgets["amplitude"]  # apply 后已解包为 QDoubleSpinBox
        assert isinstance(sb, QDoubleSpinBox)
        set_spinbox_unit(sb, "amplitude", "DU")
        sb.setValue(0.026)

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["amplitude"] == pytest.approx(0.026 * DU_KM)

    def test_apply_respects_current_unit(self, qapp):
        """切 DU 后再次 apply，amplitude 显示 60000/DU，collect 返回 60000 km。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.commons.units import DU_KM
        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
            collect_params,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "DRO")
        sb = widgets["amplitude"]
        assert isinstance(sb, QDoubleSpinBox)
        set_spinbox_unit(sb, "amplitude", "DU")

        # 再次 apply DRO 默认值（标准单位 60000 km），应换算为 DU 显示
        apply_orbit_type_defaults(widgets, "DRO")
        assert sb.value() == pytest.approx(60000.0 / DU_KM)

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["amplitude"] == pytest.approx(60000.0)

    def test_collect_month_converts_to_years(self, qapp):
        """duration 切月后 setValue(1.0)，collect 返回 1/12 年（标准单位）。"""
        from src.view.params_panel import (
            build_params_from_model,
            collect_params,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["duration"]
        set_spinbox_unit(sb, "duration", "月")
        sb.setValue(1.0)

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["duration"] == pytest.approx(1.0 / 12.0)
