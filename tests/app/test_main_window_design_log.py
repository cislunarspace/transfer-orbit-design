"""tests for MainWindow design_orbit 启动日志去重（重复日志 bug 回归）。"""

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


def _select_halo(window):
    """切到 design_orbit 工具并选 Halo 类型。"""
    tool_combo = window._tool_combo
    idx = tool_combo.findData("design_orbit")
    assert idx >= 0
    tool_combo.setCurrentIndex(idx)

    orbit_combo = window._param_widgets["orbit_type"]
    halo_idx = orbit_combo.findText("Halo")
    assert halo_idx >= 0
    orbit_combo.setCurrentIndex(halo_idx)


class TestDesignOrbitStartupLogNoDuplicate:
    def test_run_design_does_not_duplicate_start_and_params_log(self, qapp):
        """design_orbit 启动时，日志面板里"开始""参数:"各只应出现一次。

        回归：用户报告点击运行后，"开始 Halo 轨道设计""参数: {...}"
        在日志里各显示两次。根因是主窗口 _run_design_orbit 启动 worker
        前先 append 一次，worker.run 开头又 emit 一次（经 _on_worker_log
        写回同一块 LogPanel）。这里手动触发槽函数模拟 worker 的开场日志，
        断言最终面板里"开始""参数:"各只出现一次。
        """
        window = _make_window(qapp)
        _select_halo(window)

        with patch("src.app.main_window.OrbitDesignWorker"):
            window._on_run()  # 走 _run_design_orbit；mock worker 不真启线程
            # 模拟 worker.run() 开头 emit 的两条开场 log
            window._on_worker_log("开始设计 Halo 轨道...")
            window._on_worker_log("参数: {'amplitude': 30000.0}")

        text = window._log.toPlainText()
        assert text.count("开始") == 1
        assert text.count("参数:") == 1
