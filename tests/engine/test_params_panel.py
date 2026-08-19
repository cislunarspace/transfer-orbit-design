"""tests for src.view.params_panel -- Pydantic 模型 -> Qt 控件生成。"""

from __future__ import annotations

import pytest
from e2m2e.api.models import DesignOrbitRequest
from pydantic import BaseModel, Field


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
# 测试模型
# ---------------------------------------------------------------------------


class _TooltipModel(BaseModel):
    """用于 G2 测试：含 description 的字段。"""

    with_desc: float = Field(42.0, description="带描述的字段")
    without_desc: float = Field(0.0)


class _OptionalModel(BaseModel):
    """用于 G7 测试：Optional 字段。"""

    optional_val: float | None = None
    required_val: float = 1.0


class _ListFloatModel(BaseModel):
    """用于 G6 测试：list[float] 字段。"""

    vec3: list[float] = Field(default=[1.0, 2.0, 3.0])
    vec_default_empty: list[float] = Field(default=[0.0, 0.0, 0.0])


# ---------------------------------------------------------------------------
# 现有测试
# ---------------------------------------------------------------------------


class TestBuildParamsFromModel:
    def test_field_count(self, qapp):
        """控件数 = 模型字段数。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        expected_count = len(DesignOrbitRequest.model_fields)
        assert len(widgets) == expected_count, f"控件数 {len(widgets)} != 字段数 {expected_count}"

    def test_all_field_names_present(self, qapp):
        """所有字段名都应有对应控件。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        for name in DesignOrbitRequest.model_fields:
            assert name in widgets, f"字段 {name} 缺少对应控件"

    def test_orbit_type_is_line_edit(self, qapp):
        """orbit_type 为 str（非 Literal），应生成 QLineEdit。"""
        from PyQt6.QtWidgets import QLineEdit

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        assert isinstance(widgets["orbit_type"], QLineEdit)


class TestCollectParams:
    def test_returns_dict(self, qapp):
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        params = collect_params(widgets, DesignOrbitRequest)
        assert isinstance(params, dict)

    def test_optional_none_default_is_none(self, qapp):
        """G7: Optional[T] with default=None 应返回 None（checkbox 未勾选）。"""
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        params = collect_params(widgets, DesignOrbitRequest)
        assert params["amplitude"] is None


# ---------------------------------------------------------------------------
# G2: Field.description -> tooltip
# ---------------------------------------------------------------------------


class TestTooltipFromDescription:
    def test_tooltip_set_when_description_present(self, qapp):
        """字段有 description 时，toolTip 应含描述（数值控件附范围提示）。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(_TooltipModel)
        assert widgets["with_desc"].toolTip().startswith("带描述的字段")
        # 无约束 float：范围提示如实说明无约束，不拿 Qt 兜底值冒充
        assert "无范围约束" in widgets["with_desc"].toolTip()

    def test_no_description_tooltip_is_hint_only(self, qapp):
        """字段无 description 时，toolTip 只有范围提示（不再为空）。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(_TooltipModel)
        assert widgets["without_desc"].toolTip() == "无范围约束"


# ---------------------------------------------------------------------------
# G6: list[float] -> 多个 QDoubleSpinBox
# ---------------------------------------------------------------------------


class TestListFloatField:
    def test_list_float_creates_container(self, qapp):
        """list[float] 字段应生成含 3 个 QDoubleSpinBox 的容器。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(_ListFloatModel)
        container = widgets["vec3"]
        spinboxes = container.findChildren(QDoubleSpinBox)
        assert len(spinboxes) == 3

    def test_list_float_default_values(self, qapp):
        """容器内 QDoubleSpinBox 应有正确的默认值。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(_ListFloatModel)
        container = widgets["vec3"]
        from PyQt6.QtWidgets import QDoubleSpinBox

        spinboxes = container.findChildren(QDoubleSpinBox)
        values = [sb.value() for sb in spinboxes]
        assert values == pytest.approx([1.0, 2.0, 3.0])

    def test_list_float_collect_params(self, qapp):
        """collect_params 应正确读取 list[float] 容器的值。"""
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(_ListFloatModel)
        params = collect_params(widgets, _ListFloatModel)
        assert isinstance(params["vec3"], list)
        assert len(params["vec3"]) == 3
        assert params["vec3"] == pytest.approx([1.0, 2.0, 3.0])

    def test_list_float_collect_params_after_modify(self, qapp):
        """修改 spinbox 值后 collect_params 应返回新值。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(_ListFloatModel)
        container = widgets["vec3"]
        spinboxes = container.findChildren(QDoubleSpinBox)
        spinboxes[0].setValue(10.0)
        spinboxes[2].setValue(-5.0)

        params = collect_params(widgets, _ListFloatModel)
        assert params["vec3"] == pytest.approx([10.0, 2.0, -5.0])


# ---------------------------------------------------------------------------
# G7: Optional[T] -> QCheckBox 包装
# ---------------------------------------------------------------------------


class TestOptionalFieldCheckbox:
    def test_optional_has_checkbox(self, qapp):
        """Optional 字段应包含 QCheckBox。"""
        from PyQt6.QtWidgets import QCheckBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(_OptionalModel)
        cb = widgets["optional_val"].findChild(QCheckBox)
        assert cb is not None

    def test_optional_unchecked_returns_none(self, qapp):
        """Optional 字段 checkbox 未勾选时 collect_params 返回 None。"""
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(_OptionalModel)
        params = collect_params(widgets, _OptionalModel)
        assert params["optional_val"] is None

    def test_optional_checked_returns_value(self, qapp):
        """Optional 字段 checkbox 勾选后 collect_params 返回内部值。"""
        from PyQt6.QtWidgets import QCheckBox

        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(_OptionalModel)
        container = widgets["optional_val"]
        cb = container.findChild(QCheckBox)
        assert cb is not None
        cb.setChecked(True)

        params = collect_params(widgets, _OptionalModel)
        assert isinstance(params["optional_val"], float)

    def test_required_field_not_wrapped(self, qapp):
        """非 Optional 字段不应有 QCheckBox 包装。"""
        from PyQt6.QtWidgets import QCheckBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(_OptionalModel)
        assert widgets["required_val"].findChild(QCheckBox) is None


class TestFamilyGenerationParams:
    """FamilyGenerationRequest → 参数面板控件（轨道族生成工具，5.7.1 起七族字段）。"""

    def test_builds_upstream_model_widgets(self, qapp):
        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(FamilyGenerationRequest)
        assert set(widgets) == {
            "orbit_type",
            "libration_point",
            "n_orbits",
            "max_amplitude_km",
            "min_amplitude_km",
            "north_south",
            "perilune_height_max_km",
            "amplitude_in_km",
            "amplitude_out_km",
            "phase_in",
            "phase_out",
            "continuation_direction",
            "sampling_mode",
            "match_tolerance_km",
        }

    def test_collect_defaults(self, qapp):
        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(FamilyGenerationRequest)
        params = collect_params(widgets, FamilyGenerationRequest)
        assert params == {
            "orbit_type": "",
            "libration_point": 2,
            "max_amplitude_km": 30000.0,
            "n_orbits": 50,
            # 未勾选的 Optional 字段返回 None（桥接层/主窗口负责剔除）
            "min_amplitude_km": None,
            "north_south": None,
            "perilune_height_max_km": None,
            "amplitude_in_km": None,
            "amplitude_out_km": None,
            "phase_in": None,
            "phase_out": None,
            "sampling_mode": None,
            "match_tolerance_km": None,
            # str 枚举下拉无 Optional 包装，始终返回当前选项
            "continuation_direction": "decrease-x0",
        }

    def test_collect_edited_values(self, qapp):

        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(FamilyGenerationRequest)
        widgets["orbit_type"].setText("HALO")
        # libration_point 是整数枚举下拉（itemData 存 int）
        cp = widgets["libration_point"]
        idx = cp.findData(1)
        assert idx >= 0
        cp.setCurrentIndex(idx)
        widgets["max_amplitude_km"].setValue(15000.0)
        widgets["n_orbits"].setValue(30)
        params = collect_params(widgets, FamilyGenerationRequest)
        assert params["orbit_type"] == "HALO"
        assert params["libration_point"] == 1
        assert params["max_amplitude_km"] == 15000.0
        assert params["n_orbits"] == 30

    def test_point_switch_refreshes_out_of_range_default(self, qapp):
        """切平动点后，超出新点合法范围的默认值应刷新为该点默认值。

        回归：Halo 面板默认 max_amplitude_km=30000（L2 默认值），切到 L1
        后超出 L1 折叠点 ±26908 km，提交被上游校验拒绝（INVALID_PARAMS）。
        """
        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import (
            sync_family_point_params,
            apply_family_type_defaults,
            build_params_from_model,
            collect_params,
        )

        widgets = build_params_from_model(FamilyGenerationRequest)
        apply_family_type_defaults(widgets, "Halo")
        assert widgets["max_amplitude_km"].value() == 30000.0
        sync_family_point_params(widgets, "Halo", 1)
        params = collect_params(widgets, FamilyGenerationRequest)
        assert params["max_amplitude_km"] == 25000.0
        # 收集到的参数必须能直接通过上游校验
        FamilyGenerationRequest(
            orbit_type="HALO",
            libration_point=1,
            max_amplitude_km=params["max_amplitude_km"],
            n_orbits=params["n_orbits"],
        )

    def test_point_switch_keeps_in_range_user_value(self, qapp):
        """用户手输的值若仍在新点范围内，切点时不应被覆盖。"""
        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import (
            sync_family_point_params,
            apply_family_type_defaults,
            build_params_from_model,
        )

        widgets = build_params_from_model(FamilyGenerationRequest)
        apply_family_type_defaults(widgets, "Halo")
        widgets["max_amplitude_km"].setValue(20000.0)
        sync_family_point_params(widgets, "Halo", 1)
        assert widgets["max_amplitude_km"].value() == 20000.0

    def test_point_sync_opens_signed_range(self, qapp):
        """同步后 Qt 范围放开负值：南族（负振幅）可输入且通过上游校验。"""
        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import (
            apply_family_type_defaults,
            build_params_from_model,
            collect_params,
            sync_family_point_params,
        )

        widgets = build_params_from_model(FamilyGenerationRequest)
        apply_family_type_defaults(widgets, "Halo")
        sync_family_point_params(widgets, "Halo", 1)
        amp = widgets["max_amplitude_km"]
        assert amp.minimum() < 0.0
        amp.setValue(-20000.0)
        assert amp.value() == -20000.0
        params = collect_params(widgets, FamilyGenerationRequest)
        FamilyGenerationRequest(
            orbit_type="HALO",
            libration_point=1,
            max_amplitude_km=params["max_amplitude_km"],
        )

    def test_point_sync_updates_range_hint(self, qapp):
        """同步后范围提示随平动点更新：L1 Halo 显示 ±26908 km（含排除值 0）。"""
        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import (
            apply_family_type_defaults,
            build_params_from_model,
            sync_family_point_params,
        )

        widgets = build_params_from_model(FamilyGenerationRequest)
        apply_family_type_defaults(widgets, "Halo")
        sync_family_point_params(widgets, "Halo", 1)
        hint = widgets["max_amplitude_km"].lineEdit().placeholderText()
        assert "-26908" in hint and "26908" in hint and "km" in hint
        assert "不含 0" in hint

    def test_point_sync_bounds_follow_unit_switch(self, qapp):
        """同步后的范围随单位切换换算：切到 DU 后上下限按比例缩放。"""
        from src.commons.units import DU_KM
        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import (
            apply_family_type_defaults,
            build_params_from_model,
            set_spinbox_unit,
            sync_family_point_params,
        )

        widgets = build_params_from_model(FamilyGenerationRequest)
        apply_family_type_defaults(widgets, "Halo")
        sync_family_point_params(widgets, "Halo", 1)
        amp = widgets["max_amplitude_km"]
        std_max = amp.maximum()
        set_spinbox_unit(amp, "max_amplitude_km", "DU")
        assert amp.maximum() == pytest.approx(std_max / DU_KM)
        assert amp.minimum() == pytest.approx(-std_max / DU_KM)
        # 当前值也换算且保持有效
        assert amp.value() == pytest.approx(25000.0 / DU_KM)
