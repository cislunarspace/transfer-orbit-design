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
    """FamilyGenerationRequest → 参数面板控件（轨道族生成工具）。"""

    def test_builds_upstream_model_widgets(self, qapp):
        from src.engine.facade_bridge import FamilyGenerationRequest
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(FamilyGenerationRequest)
        assert set(widgets) == {"orbit_type", "libration_point", "max_amplitude_km", "n_orbits"}

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
        assert params == {
            "orbit_type": "HALO",
            "libration_point": 1,
            "max_amplitude_km": 15000.0,
            "n_orbits": 30,
        }
