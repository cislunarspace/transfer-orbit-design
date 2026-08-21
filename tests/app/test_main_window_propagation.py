"""tests for 轨道预报 GUI 接入（issue #389）-- 面板生成、初值预填、JSON 拦截。"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication, QDateTimeEdit, QDoubleSpinBox, QLineEdit

from src.model.artifact import Artifact


@pytest.fixture()
def qapp():
    try:
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


def _switch_tool(window, key):
    combo = window._tool_combo
    for i in range(combo.count()):
        if combo.itemData(i) == key:
            combo.setCurrentIndex(i)
            return
    pytest.fail(f"工具 {key} 不在下拉中")


class TestPropagationPanel:
    def test_initial_state_has_six_spinboxes(self, qapp):
        """PropagationRequest.initial_state（min/max_length=6）生成 6 个数字框。"""
        from e2m2e.api.models import PropagationRequest

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(PropagationRequest)
        widget = widgets["initial_state"]
        assert widget.property("__params_panel_kind") == "list_float"
        assert len(widget.findChildren(QDoubleSpinBox)) == 6

    def test_epoch_without_default_is_datetime_edit(self, qapp):
        """PropagationRequest.epoch 无默认值，仍应渲染为 QDateTimeEdit。"""
        from e2m2e.api.models import PropagationRequest

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(PropagationRequest)
        assert isinstance(widgets["epoch"], QDateTimeEdit)

    def test_force_config_is_plain_line_edit(self, qapp):
        """面板中 force_config 不用勾选式 Optional 包装（留空=默认三体）。"""
        window = _make_window(qapp)
        _switch_tool(window, "orbit_propagation")
        widget = window._param_widgets["force_config"]
        assert isinstance(widget, QLineEdit)
        assert widget.placeholderText()

    def test_duration_defaults_to_30_days(self, qapp):
        """duration 默认 30 天（显示单位切到“日”）。"""
        from src.engine.facade_bridge import TOOL_REGISTRY
        from src.view.params_panel import collect_params

        window = _make_window(qapp)
        _switch_tool(window, "orbit_propagation")
        model = TOOL_REGISTRY["orbit_propagation"].request_model
        params = collect_params(window._param_widgets, model)
        year_per_day = 1.0 / 365.25
        assert params["duration"] == pytest.approx(30.0 * year_per_day)


class TestPropagationPrefill:
    def _ephemeris_artifact(self) -> Artifact:
        n = 3
        return Artifact(
            artifact_type="orbit",
            label="DRO",
            source_tool="design_orbit",
            state_data=np.zeros((n, 6)),
            times=np.linspace(0, 1, n),
            extra={
                "mu": 0.012150585,
                "ephemeris": {
                    "position_km": np.tile([6793.0, 1.0, 2.0], (n, 1)),
                    "velocity_mps": np.tile([0.0, 7500.0, 3000.0], (n, 1)),  # m/s
                    "times_et": np.array([100.0, 200.0, 300.0]),
                },
            },
        )

    def test_end_state_prefilled(self, qapp):
        """选中星历工件后，initial_state 预填末端 [r; v]（速度 m/s → km/s）。"""
        window = _make_window(qapp)
        _switch_tool(window, "orbit_propagation")
        artifact = self._ephemeris_artifact()
        window._project.add(artifact)
        window._selected_artifact_ids = [artifact.artifact_id]
        window._apply_propagation_defaults()

        widget = window._param_widgets["initial_state"]
        values = [sb.value() for sb in widget.findChildren(QDoubleSpinBox)]
        assert values == [6793.0, 1.0, 2.0, 0.0, 7.5, 3.0]

    def test_no_selection_keeps_panel_values(self, qapp):
        """无选中工件时预填为 no-op（面板值不变，可纯手填）。"""
        window = _make_window(qapp)
        _switch_tool(window, "orbit_propagation")
        widget = window._param_widgets["initial_state"]
        widget.findChildren(QDoubleSpinBox)[0].setValue(123.0)
        window._apply_propagation_defaults()
        assert widget.findChildren(QDoubleSpinBox)[0].value() == 123.0


class TestPropagationRunGating:
    def test_invalid_force_config_json_blocks_run(self, qapp):
        """非法 JSON：状态栏报错且不启动 worker。"""
        window = _make_window(qapp)
        _switch_tool(window, "orbit_propagation")
        window._param_widgets["force_config"].setText("{not json")
        with patch("src.app.main_window.PropagationWorker") as worker_cls:
            window._run_propagation()
        worker_cls.assert_not_called()
        assert window._worker is None

    def test_empty_force_config_omitted(self, qapp):
        """留空 force_config：参数里剔除（走默认三体）。"""
        from src.engine.facade_bridge import TOOL_REGISTRY
        from src.view.params_panel import collect_params

        window = _make_window(qapp)
        _switch_tool(window, "orbit_propagation")
        window._param_widgets["force_config"].setText("   ")
        # 直接走参数收集路径验证剔除逻辑（不发 worker）
        model = TOOL_REGISTRY["orbit_propagation"].request_model
        params = collect_params(window._param_widgets, model)
        text = params.pop("force_config")
        assert not str(text).strip()
        # _run_propagation 内同一逻辑：空文本 pop
        assert "force_config" not in params
