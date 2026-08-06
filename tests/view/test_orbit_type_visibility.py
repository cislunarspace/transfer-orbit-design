"""tests for orbit_type 切换时参数面板字段的显隐（_sync_visible_fields）。

PR #351 code review 遗留 #7：原有测试覆盖默认值 / epoch / correction / 单位，
但未对 _sync_visible_fields 的显隐做直接断言。这里补两条：
- DRO（初始）：amplitude/phase 可见，amplitude_in 隐藏；
- 切到 NRHO：perilune_height/north_south 可见，amplitude 隐藏。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture()
def qapp():
    """确保 QApplication 存在（pytest-qt 自动提供，兜底手动创建）。"""
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except ImportError:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


def _build_design_window(qapp):
    """构造一个切到 design_orbit 工具的 MainWindow（隔离真实 output 目录）。"""
    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        window = MainWindow()
    window._build_tool_params("design_orbit")
    return window


class TestSyncVisibleFields:
    def test_dro_branch_visibility(self, qapp):
        """DRO 分支：amplitude/phase 可见；amplitude_in 隐藏。"""
        window = _build_design_window(qapp)
        for name in ("amplitude", "phase"):
            label, widget, _ = window._param_rows[name]
            assert not label.isHidden(), f"{name} 的 label 在 DRO 分支应可见"
            assert not widget.isHidden(), f"{name} 的控件在 DRO 分支应可见"

        label, widget, _ = window._param_rows["amplitude_in"]
        assert label.isHidden(), "amplitude_in 的 label 在 DRO 分支应隐藏"
        assert widget.isHidden(), "amplitude_in 的控件在 DRO 分支应隐藏"

    def test_nrho_branch_visibility(self, qapp):
        """切到 NRHO：perilune_height/north_south 可见，amplitude 隐藏。"""
        window = _build_design_window(qapp)
        combo = window._param_widgets["orbit_type"]
        combo.setCurrentText("NRHO")

        for name in ("perilune_height", "north_south", "collinear_point", "phase"):
            label, widget, _ = window._param_rows[name]
            assert not widget.isHidden(), f"{name} 的控件在 NRHO 分支应可见"

        label, widget, _ = window._param_rows["amplitude"]
        assert widget.isHidden(), "amplitude 的控件在 NRHO 分支应隐藏"
