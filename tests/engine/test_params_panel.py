"""tests for src.view.params_panel -- Pydantic 模型 -> Qt 控件生成。"""

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


class TestBuildParamsFromModel:
    def test_field_count(self, qapp):
        """控件数 = 模型字段数。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        expected_count = len(DesignOrbitRequest.model_fields)
        assert len(widgets) == expected_count, (
            f"控件数 {len(widgets)} != 字段数 {expected_count}"
        )

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

    def test_amplitude_is_float(self, qapp):
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        params = collect_params(widgets, DesignOrbitRequest)
        assert isinstance(params["amplitude"], float)
