"""tests for src.view.params_panel -- epoch QDateTimeEdit 与 correction_method 下拉。

根因回归：DesignOrbitRequest.epoch 是 Any 类型，曾被渲染成 QLineEdit 并把
元组默认值 str() 成 "(2024, 1, 1, 0, 0, 0.0)"，收集时按字符串传给 e2m2e 的
spice.str2et 导致解析失败（所有轨道类型设计失败）。修复为结构化编辑控件，
收集成 [年,月,日,时,分,秒] list，可直接被 _epoch_to_iso 格式化。
correction_method 由 str 文本框改为 QComboBox 下拉（standard/two_level）。
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
# epoch -> QDateTimeEdit
# ---------------------------------------------------------------------------


class TestEpochField:
    def test_epoch_is_epoch_container(self, qapp):
        """epoch 应生成 kind=epoch 的控件。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        assert widgets["epoch"].property("__params_panel_kind") == "epoch"

    def test_epoch_is_datetime_edit(self, qapp):
        """epoch 是 QDateTimeEdit（带日历弹出）。"""
        from PyQt6.QtWidgets import QDateTimeEdit

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        edit = widgets["epoch"]
        assert isinstance(edit, QDateTimeEdit)
        assert edit.displayFormat() == "yyyy-MM-dd HH:mm:ss"
        assert edit.calendarPopup()

    def test_epoch_default_values(self, qapp):
        """默认值 == 2024-01-01 00:00:00.000。"""
        from PyQt6.QtCore import QDateTime

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        assert widgets["epoch"].dateTime() == QDateTime(2024, 1, 1, 0, 0, 0, 0)

    def test_epoch_range_constraints(self, qapp):
        """年份范围 1900-2100。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        edit = widgets["epoch"]
        assert edit.minimumDateTime().date().year() == 1900
        assert edit.maximumDateTime().date().year() == 2100

    def test_epoch_collect_roundtrip(self, qapp):
        """collect_params 应返回 [年,月,日,时,分,秒] list。"""
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        params = collect_params(widgets, DesignOrbitRequest)
        assert params["epoch"] == pytest.approx([2024.0, 1.0, 1.0, 0.0, 0.0, 0.0])

    def test_epoch_collect_after_modify(self, qapp):
        """修改日期后 collect_params 应返回新值。"""
        from PyQt6.QtCore import QDateTime

        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        widgets["epoch"].setDateTime(QDateTime(2030, 6, 1, 0, 0, 0, 0))

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["epoch"] == pytest.approx([2030.0, 6.0, 1.0, 0.0, 0.0, 0.0])

    def test_epoch_to_iso_compatible(self, qapp):
        """关键回归：collect 出的 epoch 应能被 e2m2e _epoch_to_iso 格式化。"""
        from e2m2e.algorithm.design.design_orbit import _epoch_to_iso

        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        params = collect_params(widgets, DesignOrbitRequest)
        iso = _epoch_to_iso(params["epoch"])
        assert iso == "2024-01-01T00:00:00.000"

    def test_epoch_not_optional_wrapped(self, qapp):
        """epoch 不应被 Optional 包装（无 QCheckBox）。"""
        from PyQt6.QtWidgets import QCheckBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        assert widgets["epoch"].findChild(QCheckBox) is None


# ---------------------------------------------------------------------------
# correction_method -> QComboBox
# ---------------------------------------------------------------------------


class TestCorrectionMethod:
    def test_correction_method_is_combo(self, qapp):
        """correction_method 应生成 QComboBox。"""
        from PyQt6.QtWidgets import QComboBox

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        assert isinstance(widgets["correction_method"], QComboBox)

    def test_correction_method_options(self, qapp):
        """下拉项应为 standard / two_level。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        combo = widgets["correction_method"]
        items = [combo.itemText(i) for i in range(combo.count())]
        assert items == ["standard", "two_level"]

    def test_correction_method_default(self, qapp):
        """默认选中 two_level。"""
        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(DesignOrbitRequest)
        assert widgets["correction_method"].currentText() == "two_level"

    def test_correction_method_collect(self, qapp):
        """collect_params 应返回当前选中项字符串。"""
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        params = collect_params(widgets, DesignOrbitRequest)
        assert params["correction_method"] == "two_level"

    def test_correction_method_collect_after_switch(self, qapp):
        """切到 standard 后 collect_params 应返回 standard。"""
        from src.view.params_panel import build_params_from_model, collect_params

        widgets = build_params_from_model(DesignOrbitRequest)
        combo = widgets["correction_method"]
        combo.setCurrentIndex(0)  # standard

        params = collect_params(widgets, DesignOrbitRequest)
        assert params["correction_method"] == "standard"


# ---------------------------------------------------------------------------
# 不误伤其它 Any 字段
# ---------------------------------------------------------------------------


class TestNoFalsePositive:
    def test_input_ephemeris_stays_line_edit(self, qapp):
        """ControlOrbitRequest.input_ephemeris 是 Any 但不应被改成 epoch 控件。"""
        from PyQt6.QtWidgets import QLineEdit

        from src.view.params_panel import build_params_from_model

        widgets = build_params_from_model(ControlOrbitRequest)
        assert isinstance(widgets["input_ephemeris"], QLineEdit)
