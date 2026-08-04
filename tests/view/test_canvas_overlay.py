"""tests for src.view.canvas.OrbitCanvas.plot_multiple -- 多轨道叠加渲染。"""

from __future__ import annotations

import numpy as np
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
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


def _random_orbit(n: int = 100) -> np.ndarray:
    """生成随机轨道状态矩阵 (n, 6)。"""
    rng = np.random.default_rng(42)
    return rng.random((n, 6))


class TestPlotMultiple:
    def test_renders_all_orbits(self, qapp):
        """plot_multiple 叠加两条轨道后 figure 上有 2 条 Line3D。"""
        from src.view.canvas import OrbitCanvas

        canvas = OrbitCanvas()
        states1 = _random_orbit()
        states2 = _random_orbit()
        canvas.plot_multiple(orbits=[(states1, "A"), (states2, "B")])

        from mpl_toolkits.mplot3d.art3d import Line3D

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 2

    def test_uses_different_colors(self, qapp):
        """两条轨道应使用不同颜色。"""
        from src.view.canvas import OrbitCanvas

        canvas = OrbitCanvas()
        states1 = _random_orbit()
        states2 = _random_orbit()
        canvas.plot_multiple(orbits=[(states1, "A"), (states2, "B")])

        from mpl_toolkits.mplot3d.art3d import Line3D

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 2
        color1 = lines[0].get_color()
        color2 = lines[1].get_color()
        assert color1 != color2

    def test_empty_list_no_error(self, qapp):
        """plot_multiple([]) 不抛异常。"""
        from src.view.canvas import OrbitCanvas

        canvas = OrbitCanvas()
        canvas.plot_multiple(orbits=[])

    def test_title_shows_count(self, qapp):
        """title 包含轨道数量。"""
        from src.view.canvas import OrbitCanvas

        canvas = OrbitCanvas()
        states1 = _random_orbit()
        states2 = _random_orbit()
        canvas.plot_multiple(orbits=[(states1, "A"), (states2, "B")])

        ax = canvas._fig.axes[0]
        title = ax.get_title()
        assert "2 条轨道" in title

    def test_single_orbit_title(self, qapp):
        """单条轨道 title 显示 '1 条轨道'。"""
        from src.view.canvas import OrbitCanvas

        canvas = OrbitCanvas()
        canvas.plot_multiple(orbits=[(_random_orbit(), "Solo")])

        ax = canvas._fig.axes[0]
        title = ax.get_title()
        assert "1 条轨道" in title

    def test_with_toolbar_passthrough(self, qapp):
        """OrbitCanvasWithToolbar.plot_multiple 正常透传。"""
        from src.view.canvas import OrbitCanvasWithToolbar

        wrapper = OrbitCanvasWithToolbar()
        wrapper.plot_multiple(orbits=[(_random_orbit(), "A"), (_random_orbit(), "B")])

        ax = wrapper.canvas._fig.axes[0]
        assert "2 条轨道" in ax.get_title()
