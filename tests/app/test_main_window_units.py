"""tests for MainWindow 单位下拉集成（设计工具按字段切换显示单位）。"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except ImportError:
        pytest.skip("QApplication 不可用")


def _make_window(qapp):
    """创建 MainWindow，mock 掉 discover_artifacts 避免扫描真实 output/。"""
    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow()


def _build_design_tool(window):
    """切换到 design_orbit 工具，返回工具键与 orbit_type 下拉。"""
    from PyQt6.QtWidgets import QComboBox

    tool_combo = window._tool_combo
    idx = tool_combo.findData("design_orbit")
    assert idx >= 0
    tool_combo.setCurrentIndex(idx)
    orbit_type_widget = window._param_widgets["orbit_type"]
    assert isinstance(orbit_type_widget, QComboBox)
    return orbit_type_widget


class TestDesignOrbitUnitCombo:
    def test_amplitude_row_has_unit_combo(self, qapp):
        """amplitude 行应含单位 QComboBox，phase 行不含。"""
        from PyQt6.QtWidgets import QComboBox

        window = _make_window(qapp)
        _build_design_tool(window)

        amplitude_row = window._param_rows["amplitude"]
        phase_row = window._param_rows["phase"]

        assert isinstance(amplitude_row[2], QComboBox)
        assert amplitude_row[2].count() == 2  # km / DU
        assert amplitude_row[0].text() == "振幅 (km)"
        assert phase_row[2] is None

    def test_switch_unit_updates_label_and_collect(self, qapp):
        """切 amplitude 到 DU 后 label 更新、collect 返回标准单位 km。"""
        from PyQt6.QtWidgets import QDoubleSpinBox

        from src.commons.units import DU_KM
        from src.view.params_panel import collect_params

        window = _make_window(qapp)
        orbit_combo = _build_design_tool(window)

        # 选 DRO 分支（触发默认值填充，amplitude 解包为 QDoubleSpinBox）
        dro_idx = orbit_combo.findText("DRO")
        assert dro_idx >= 0
        orbit_combo.setCurrentIndex(dro_idx)

        label, widget, unit_combo = window._param_rows["amplitude"]
        assert isinstance(widget, QDoubleSpinBox)
        assert widget.value() == pytest.approx(10000.0)  # DRO 默认 10000 km

        # 切单位到 DU
        unit_combo.setCurrentIndex(unit_combo.findText("DU"))
        assert label.text() == "振幅 (DU)"
        assert widget.value() == pytest.approx(10000.0 / DU_KM)

        # collect 返回标准单位 km
        from src.engine.facade_bridge import TOOL_REGISTRY


        model = TOOL_REGISTRY["design_orbit"].request_model
        params = collect_params(window._param_widgets, model)
        assert params["amplitude"] == pytest.approx(10000.0)

    def test_control_orbit_output_step_has_unit(self, qapp):
        """control_orbit 的 output_step（共享字段）也应有单位下拉。"""
        from PyQt6.QtWidgets import QComboBox

        window = _make_window(qapp)
        tool_combo = window._tool_combo
        idx = tool_combo.findData("control_orbit")
        assert idx >= 0
        tool_combo.setCurrentIndex(idx)

        output_step_row = window._param_rows["output_step"]
        assert isinstance(output_step_row[2], QComboBox)
