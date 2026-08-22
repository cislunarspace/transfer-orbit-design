"""tests for TimelineBar 时间轴控件 + MainWindow 接线（ADR-0014，issue #395）。

接缝：
- TimelineBar 公开 API（区间映射、灰显、UTC 标签、节流信号）
- MainWindow 拖动后状态更新（current_et 写入 CanvasState）与区间并集/灰显
"""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


class TestTimelineBar:
    def test_default_position_at_range_start(self, qapp):
        """设置区间后默认停在起点（US 14），UTC 标签更新。"""
        from src.view.timeline_bar import TimelineBar

        bar = TimelineBar()
        bar.set_time_range(7.5e8, 7.6e8)
        assert bar.isEnabled()
        assert bar.current_et() == pytest.approx(7.5e8)
        assert "UTC" in bar.time_label.text()

    def test_unavailable_disables(self, qapp):
        """set_unavailable 灰显滑块。"""
        from src.view.timeline_bar import TimelineBar

        bar = TimelineBar()
        bar.set_time_range(0.0, 1.0)
        bar.set_unavailable()
        assert not bar.isEnabled()

    def test_throttled_signal_emits_during_drag(self, qapp):
        """按住拖动：周期节流到期即发射（10 Hz，拖动中持续刷新），映射到 et 区间。"""
        from src.view.timeline_bar import TimelineBar

        bar = TimelineBar()
        bar.set_time_range(100.0, 200.0)
        received: list[float] = []
        bar.et_changed.connect(received.append)
        bar.slider.sliderPressed.emit()  # 按住
        bar.slider.setValue(bar.slider.maximum())  # 拖到末端 = et 上界
        bar._flush()  # 周期到期
        assert received == [pytest.approx(200.0)]
        bar._flush()  # 再一个周期
        assert len(received) == 2

    def test_release_emits_final_value_and_stops(self, qapp):
        """松手：补发最终值一次。"""
        from src.view.timeline_bar import TimelineBar

        bar = TimelineBar()
        bar.set_time_range(100.0, 200.0)
        received: list[float] = []
        bar.et_changed.connect(received.append)
        bar.slider.sliderPressed.emit()
        bar.slider.setValue(0)
        bar.slider.sliderReleased.emit()
        assert received == [pytest.approx(100.0)]

    def test_programmatic_set_et_does_not_emit(self, qapp):
        """程序化 set_et（重绘同步用）不发射信号，避免反馈环。"""
        from src.view.timeline_bar import TimelineBar

        bar = TimelineBar()
        bar.set_time_range(100.0, 200.0)
        received: list[float] = []
        bar.et_changed.connect(received.append)
        bar.set_et(150.0)
        assert received == []
        assert bar.current_et() == pytest.approx(150.0)


class TestMainWindowTimeline:
    def _make_window(self, qapp):
        from unittest.mock import patch

        from src.app.main_window import MainWindow

        class _StubCatalog:
            def query_artifacts(self, filters=None):
                return []

            def load_arrays(self, artifact):
                return True

        with patch("src.app.main_window.discover_artifacts", return_value=[]):
            return MainWindow(catalog=_StubCatalog())

    def test_union_range_and_enabled(self, qapp, monkeypatch):
        """多个星历产物：滑块区间为时间并集，滑块可用，t 默认停在起点。"""
        window = self._make_window(qapp)
        window._viz.canvas.set_artifacts_provider(
            lambda aid: {
                "label": aid,
                "mu": None,
                "ephemeris_synodic": np.zeros((3, 3)),
                "ephemeris_times_et": (
                    np.array([0.0, 50.0, 100.0])
                    if aid == "a1"
                    else np.array([150.0, 200.0, 250.0])
                ),
            }
        )
        window._selected_artifact_ids = ["a1", "a2"]
        window._render_canvas()
        timeline = window._viz.timeline
        assert timeline.isEnabled()
        assert timeline._et_min == pytest.approx(0.0)
        assert timeline._et_max == pytest.approx(250.0)
        assert window._canvas_state.current_et == pytest.approx(0.0)

    def test_disabled_without_ephemeris(self, qapp, monkeypatch):
        """同屏只有初猜（无 times_et）：滑块灰显，current_et 置 None。"""
        window = self._make_window(qapp)
        window._viz.canvas.set_artifacts_provider(
            lambda aid: {
                "label": aid,
                "mu": 0.012,
                "initial_guess_states": np.zeros((5, 6)),
            }
        )
        window._selected_artifact_ids = ["a1"]
        window._render_canvas()
        assert not window._viz.timeline.isEnabled()
        assert window._canvas_state.current_et is None

    def test_slider_stays_in_sync_with_state(self, qapp, monkeypatch):
        """区间扩大后 current_et 仍在范围内：滑块与画布时刻保持一致，不回起点。"""
        window = self._make_window(qapp)
        window._viz.canvas.set_artifacts_provider(
            lambda aid: {
                "label": aid,
                "mu": None,
                "ephemeris_synodic": np.zeros((3, 3)),
                "ephemeris_times_et": np.array([100.0, 200.0, 300.0]),
            }
        )
        window._selected_artifact_ids = ["a1"]
        window._render_canvas()
        window._on_timeline_changed(250.0)
        # 区间扩大（新增产物）：滑块应与 current_et 同步，不回到起点
        window._viz.canvas.set_artifacts_provider(
            lambda aid: {
                "label": aid,
                "mu": None,
                "ephemeris_synodic": np.zeros((3, 3)),
                "ephemeris_times_et": (
                    np.array([100.0, 200.0, 300.0])
                    if aid == "a1"
                    else np.array([400.0, 500.0, 600.0])
                ),
            }
        )
        window._selected_artifact_ids = ["a1", "a2"]
        window._render_canvas()
        assert window._canvas_state.current_et == pytest.approx(250.0)
        assert window._viz.timeline.current_et() == pytest.approx(250.0)


    def test_timeline_change_updates_state(self, qapp):
        """拖动后 current_et 更新并重绘（外部行为，需有星历产物驱动时间轴）。"""
        window = self._make_window(qapp)
        window._viz.canvas.set_artifacts_provider(
            lambda aid: {
                "label": aid,
                "mu": None,
                "ephemeris_synodic": np.zeros((3, 3)),
                "ephemeris_times_et": np.array([100.0, 200.0, 300.0]),
            }
        )
        window._selected_artifact_ids = ["a1"]
        window._render_canvas()
        window._on_timeline_changed(123.0)
        assert window._canvas_state.current_et == pytest.approx(123.0)


class TestFrameSwitchKeepsTime:
    def test_frame_switch_preserves_current_et(self, qapp):
        """US6：切换坐标系不重置时刻（两系共享同一 t）。"""
        window = None
        from unittest.mock import patch

        from src.app.main_window import MainWindow

        class _StubCatalog:
            def query_artifacts(self, filters=None):
                return []

            def load_arrays(self, artifact):
                return True

        with patch("src.app.main_window.discover_artifacts", return_value=[]):
            window = MainWindow(catalog=_StubCatalog())
        window._viz.canvas.set_artifacts_provider(
            lambda aid: {
                "label": aid,
                "mu": None,
                "ephemeris_synodic": np.zeros((3, 3)),
                "ephemeris_position_km": np.zeros((3, 3)),
                "ephemeris_times_et": np.array([100.0, 200.0, 300.0]),
            }
        )
        window._selected_artifact_ids = ["a1"]
        window._render_canvas()
        window._on_timeline_changed(250.0)
        window._on_frame_changed("inertial")
        assert window._canvas_state.current_et == pytest.approx(250.0)
        assert window._viz.timeline.current_et() == pytest.approx(250.0)
