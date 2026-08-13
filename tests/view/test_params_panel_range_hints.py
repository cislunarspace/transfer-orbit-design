"""tests for 右边栏增强 -- 范围占位提示、整数枚举下拉、单位换算全覆盖。

覆盖本轮右边栏更新：
- 数值控件框内文本清空时显示可填范围（placeholder），切单位后同步刷新；
- 整数枚举字段（collinear_point/control_mode 等）渲染为 QComboBox，值存
  itemData（int），collect 按数据取值；
- 模型外补充字段（control_interval）与 list[float] 容器（srp_offset_m）的
  单位换算；多次切单位的舍入缓存（30 天 → TU → 秒 → 天 精确往返）。
"""

from __future__ import annotations

import pytest
from e2m2e.api.models import ControlOrbitRequest, DesignOrbitRequest


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
# 范围占位提示
# ---------------------------------------------------------------------------


class TestRangePlaceholder:
    def test_spinbox_placeholder_shows_range(self, qapp):
        """数值控件内部 lineEdit 的 placeholder 应含可填范围（当前显示单位）。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["output_step"]
        assert isinstance(sb, QDoubleSpinBox)
        hint = sb.lineEdit().placeholderText()
        assert hint.startswith("可填范围:")
        assert "秒" in hint

    def test_placeholder_updates_on_unit_switch(self, qapp):
        """切单位后 placeholder 范围按新单位刷新。"""
        from src.view.params_panel import build_params_from_model, set_spinbox_unit

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["output_step"]
        set_spinbox_unit(sb, "output_step", "TU")
        hint = sb.lineEdit().placeholderText()
        assert "TU" in hint and "秒" not in hint

    def test_tooltip_contains_description_and_range(self, qapp):
        """tooltip = 字段描述 + 范围提示（spacecraft_mass 模型声明 gt=0，严格下界）。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(ControlOrbitRequest)
        # spacecraft_mass 无单位选项：tooltip = 描述 + 仅下界范围提示（gt 严格 >）
        tip = widgets["spacecraft_mass"].toolTip()
        assert "可填范围: > 0" in tip
        assert "航天器质量" in tip

    def test_optional_wrapped_spinbox_has_placeholder(self, qapp):
        """Optional 包装内部的 spinbox（如 amplitude）也应有范围提示。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["amplitude"].findChild(QDoubleSpinBox)
        assert sb is not None
        hint = sb.lineEdit().placeholderText()
        assert "可填范围" in hint

    def test_lower_bound_only_shows_gt_hint(self, qapp):
        """仅下界约束（如 output_step gt=0）提示 > min（Qt 舍入后 min=0 不误导），不显示无上限。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        sb = widgets["output_step"]
        assert isinstance(sb, QDoubleSpinBox)
        hint = sb.lineEdit().placeholderText()
        assert hint.startswith("可填范围: > ")
        assert "秒" in hint

    def test_unconstrained_int_shows_gui_temporary_range(self, qapp):
        """模型缺上界的 int（num_controls，ge=1 无 le）补 GUI 临时上界并注明。"""
        from PyQt6.QtWidgets import QSpinBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(ControlOrbitRequest)
        sb = widgets["num_controls"]
        assert isinstance(sb, QSpinBox)
        hint = sb.lineEdit().placeholderText()
        assert "可填范围: 1 ~ 10000" in hint  # min 来自模型 ge=1，max 为 GUI 临时
        assert "GUI 临时" in hint

    def test_json_field_placeholder(self, qapp):
        """JSON 文本框（perturbation/engine_layout）为空时给格式示例提示。"""
        from PyQt6.QtWidgets import QLineEdit

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        # perturbation 是 Optional(dict) 包装：内部控件为 QLineEdit
        line = widgets["perturbation"].findChild(QLineEdit)
        assert line is not None
        assert "JSON" in line.placeholderText()

        ctrl = build_params_from_model(ControlOrbitRequest)
        # engine_layout 是 Any（非 Optional 注解），直接渲染为 QLineEdit
        assert isinstance(ctrl["engine_layout"], QLineEdit)
        assert "positions_m" in ctrl["engine_layout"].placeholderText()


# ---------------------------------------------------------------------------
# 整数枚举下拉
# ---------------------------------------------------------------------------


    def test_int_range_override_respects_model_bounds(self, qapp):
        """GUI 临时范围只补缺失边界：模型已有 ge 时不被覆盖。"""
        from pydantic import BaseModel, Field

        from src.view.params_panel import build_params_from_model

        class _Model(BaseModel):
            # 模型声明 ge=5：override 不得把 min 改成 1
            num_controls: int = Field(120, ge=5)

        widgets = build_params_from_model(_Model)
        sb = widgets["num_controls"]
        assert sb.minimum() == 5
        assert sb.maximum() == 10000  # 上界缺失仍补 GUI 临时值
        assert "可填范围: 5 ~ 10000" in sb.lineEdit().placeholderText()


class TestIntCombo:
    def test_collinear_point_is_combo_with_int_data(self, qapp):
        """collinear_point 渲染为 QComboBox，itemData 为 int。

        模型 default=None，未 apply 分支默认值前选中首项（L1）；apply 后
        按分支默认值（NRHO=2）选中。
        """
        from PyQt6.QtWidgets import QComboBox

        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        combo = widgets["collinear_point"].findChild(QComboBox)
        assert combo is not None
        items = [combo.itemText(i) for i in range(combo.count())]
        assert items == ["L1", "L2", "L3"]
        assert combo.currentData() == 1  # 模型无默认，首项 L1

        apply_orbit_type_defaults(widgets, "NRHO")
        combo = widgets["collinear_point"]
        assert isinstance(combo, QComboBox)
        assert combo.currentData() == 2

    def test_control_mode_combo_options(self, qapp):
        """control_mode 下拉含 1-6 带角动量管理语义的选项。"""
        from PyQt6.QtWidgets import QComboBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(ControlOrbitRequest)
        assert isinstance(widgets["control_mode"], QComboBox)
        combo = widgets["control_mode"]
        assert combo.count() == 6
        assert combo.currentData() == 1
        assert "角动量" in combo.itemText(5)

    def test_int_combo_collect_returns_int(self, qapp):
        """collect 按 itemData 返回 int，而非文本。"""
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(ControlOrbitRequest)
        combo = widgets["control_mode"]
        combo.setCurrentIndex(5)  # 6 - 特征点 + 角动量管理

        params = collect_params(widgets, ControlOrbitRequest)
        assert params["control_mode"] == 6
        assert isinstance(params["control_mode"], int)

    def test_int_combo_apply_defaults(self, qapp):
        """apply_orbit_type_defaults 按 itemData 选中断言整数默认值。"""
        from PyQt6.QtWidgets import QComboBox

        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "NRHO")
        combo = widgets["north_south"]
        assert isinstance(combo, QComboBox)
        assert combo.currentData() == 2  # 南族


# ---------------------------------------------------------------------------
# 单位换算全覆盖：模型外补充字段与 list 容器
# ---------------------------------------------------------------------------


class TestSupplementalFieldUnits:
    def _control_widgets(self, qapp):
        """构造 control_orbit 面板控件（含补充字段 control_interval/feedback_arc）。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import attach_unit_state, build_params_from_model

        widgets = build_params_from_model(ControlOrbitRequest)
        for name, default in (("control_interval", 30.0), ("feedback_arc", 28.0)):
            sb = QDoubleSpinBox()
            sb.setRange(1e-3, 1e4)
            sb.setValue(default)
            attach_unit_state(sb, name)
            widgets[name] = sb
        return widgets

    def test_control_interval_unit_switch_roundtrip(self, qapp):
        """补充字段切 天→TU→秒→天 精确往返（舍入缓存）。"""
        from src.view.params_panel import (
            collect_params,
            set_spinbox_unit,
        )

        widgets = self._control_widgets(qapp)
        sb = widgets["control_interval"]
        set_spinbox_unit(sb, "control_interval", "TU")
        set_spinbox_unit(sb, "control_interval", "秒")
        set_spinbox_unit(sb, "control_interval", "天")
        assert sb.value() == pytest.approx(30.0, abs=1e-9)

        params = collect_params(widgets, ControlOrbitRequest)
        assert params["control_interval"] == pytest.approx(30.0, abs=1e-9)

    def test_control_interval_user_edit_converts(self, qapp):
        """用户改显示值后 collect 按当前显示单位换算。"""
        from src.view.params_panel import collect_params, set_spinbox_unit

        widgets = self._control_widgets(qapp)
        sb = widgets["control_interval"]
        set_spinbox_unit(sb, "control_interval", "TU")
        sb.setValue(1.0)  # 1 TU

        params = collect_params(widgets, ControlOrbitRequest)
        from src.commons.units import TU_SECONDS

        assert params["control_interval"] == pytest.approx(TU_SECONDS / 86400.0)

    def test_srp_offset_container_unit_switch(self, qapp):
        """srp_offset_m（Optional list 容器）切 DU 后 collect 返回 m。"""
        from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox

        from src.commons.units import DU_KM
        from src.view.params_panel import (
            build_params_from_model,
            collect_params,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(ControlOrbitRequest)
        wrapper = widgets["srp_offset_m"]
        cb = wrapper.findChild(QCheckBox)
        assert cb is not None
        cb.setChecked(True)
        children = wrapper.findChildren(QDoubleSpinBox)
        children[0].setValue(2.0)

        set_spinbox_unit(wrapper, "srp_offset_m", "DU")
        # 显示 10 位小数，2 m ≈ 5.2e-9 DU（collect 走缓存仍精确返回 2.0 m）
        assert children[0].value() * (DU_KM * 1000.0) == pytest.approx(2.0, rel=1e-3)
        hint = children[0].lineEdit().placeholderText()
        # 容器无模型约束：范围提示如实说明，不拿 Qt 兜底 ±1e12 冒充
        assert "无范围约束" in hint

        params = collect_params(widgets, ControlOrbitRequest)
        assert params["srp_offset_m"] == pytest.approx([2.0, 0.0, 0.0])

    def test_phase_degree_convert(self, qapp):
        """phase 切'度'后 90 度 -> collect 0.25（周期份额）。"""
        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
            collect_params,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "DRO")
        sb = widgets["phase"]
        set_spinbox_unit(sb, "phase", "度")
        sb.setValue(90.0)

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["phase"] == pytest.approx(0.25)

    def test_inclination_radian_convert(self, qapp):
        """inclination 切 rad 后 collect 返回度。"""
        import math

        from src.view.params_panel import (
            apply_orbit_type_defaults,
            build_params_from_model,
            collect_params,
            set_spinbox_unit,
        )

        widgets = build_params_from_model(DesignOrbitRequest)
        apply_orbit_type_defaults(widgets, "ELFO")
        sb = widgets["inclination"]
        set_spinbox_unit(sb, "inclination", "rad")
        sb.setValue(math.pi / 4.0)

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["inclination"] == pytest.approx(45.0, abs=1e-2)  # rad 显示 4 位小数
