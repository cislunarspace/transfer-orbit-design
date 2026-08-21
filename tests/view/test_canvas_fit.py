"""tests for src.view.canvas.OrbitCanvas.fit_to_data -- 视图适配（CONTEXT.md）。

适配 = 按当前可见轨道轨迹的坐标范围重设各轴窗口，每轴总跨度 × 1.05
（5% 余量，对称展开）；标注（地月/平动点/月球轨迹）不参与。适配后的
视图成为后续 render 的视图保持基准。
"""

from __future__ import annotations

import numpy as np
import pytest
from e2m2e.data.templates.seed import EARTH_MOON_MU


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


_MU = EARTH_MOON_MU


def _orbit_xy(x_half: float = 0.5, n: int = 50) -> np.ndarray:
    """确定性轨道状态矩阵 (n, 6)：XY 平面圆，Z 小振幅。"""
    t = np.linspace(0.0, 2.0 * np.pi, n)
    return np.column_stack(
        (
            x_half * np.cos(t),
            x_half * np.sin(t),
            0.1 * np.sin(2 * t),
            np.zeros(n),
            np.zeros(n),
            np.zeros(n),
        )
    )


def _make_canvas(
    qapp, projection: str = "3d", *, show_bodies: bool = False, center: str = "barycenter"
):
    from src.view.canvas import CanvasState, OrbitCanvas

    canvas = OrbitCanvas()
    canvas.set_artifacts_provider(
        lambda _aid: {
            "initial_guess_states": _orbit_xy(),
            "label": "id1",
            "mu": _MU,
        }
    )
    state = CanvasState(
        projection=projection,
        visible_artifacts=["id1"],
        show_bodies=show_bodies,
        show_libration=False,
        plot_content="guess",
        center=center,
    )
    canvas.sync_state(state.copy(), ["id1"])
    canvas.render(state.copy())
    return canvas


class TestFitToData:
    def test_fit_3d_applies_5pct_margin(self, qapp):
        """3D：适配后各轴跨度 = 数据跨度 × 1.05（z_ratio 约束前的 x/y 轴）。"""
        canvas = _make_canvas(qapp)
        # 模拟用户缩放到小窗口
        canvas._ax.set_xlim(-0.01, 0.01)
        canvas._ax.set_ylim(-0.01, 0.01)
        canvas._ax.set_zlim(-0.01, 0.01)

        canvas.fit_to_data()

        xlim = canvas._ax.get_xlim()
        pos = _orbit_xy()[:, :3]
        span_x = pos[:, 0].max() - pos[:, 0].min()
        assert np.ptp(xlim) == pytest.approx(span_x * 1.05, rel=1e-6)
        mid_x = (pos[:, 0].max() + pos[:, 0].min()) / 2
        assert xlim[0] == pytest.approx(mid_x - span_x * 1.05 / 2, abs=1e-9)
        assert xlim[1] == pytest.approx(mid_x + span_x * 1.05 / 2, abs=1e-9)

    def test_fit_preserves_camera_angles(self, qapp):
        """适配不清 3D 相机角（只动轴范围）。"""
        canvas = _make_canvas(qapp)
        canvas._ax.view_init(elev=45.0, azim=60.0)

        canvas.fit_to_data()

        assert canvas._ax.elev == pytest.approx(45.0)
        assert canvas._ax.azim == pytest.approx(60.0)

    def test_fit_ignores_annotations(self, qapp):
        """标注（地月）不参与：开标注后适配结果与不开标注一致。"""
        with_bodies = _make_canvas(qapp, show_bodies=True)
        assert any(line.get_gid() != "orbit" for line in with_bodies._ax.lines)

        with_bodies._ax.set_xlim(-0.01, 0.01)
        with_bodies.fit_to_data()

        # 仍按轨道范围（≈ ±0.5 × 1.05），不被地月标注（x∈[-μ, 1-μ]）拉宽
        xlim = with_bodies._ax.get_xlim()
        assert np.ptp(xlim) == pytest.approx(1.05, rel=1e-2)

    def test_fit_2d_projection(self, qapp):
        """2D 投影（xy）：两轴按各自数据范围 + 5% 余量。"""
        canvas = _make_canvas(qapp, "xy")
        canvas._ax.set_xlim(-0.01, 0.01)

        canvas.fit_to_data()

        assert np.ptp(canvas._ax.get_xlim()) == pytest.approx(1.05, rel=1e-2)
        assert np.ptp(canvas._ax.get_ylim()) == pytest.approx(1.05, rel=1e-2)

    def test_fit_custom_center_symmetrizes(self, qapp):
        """自定义中心（moon）：适配后范围对称于原点（平移后中心）。"""
        canvas = _make_canvas(qapp, center="moon")
        canvas.fit_to_data()
        for lim in (canvas._ax.get_xlim(), canvas._ax.get_ylim(), canvas._ax.get_zlim()):
            assert lim[0] == pytest.approx(-lim[1], rel=1e-6)

    def test_fit_result_becomes_preserve_baseline(self, qapp):
        """适配后的视图成为后续重绘的保持基准（CONTEXT.md: 视图适配）。"""
        canvas = _make_canvas(qapp)
        canvas.fit_to_data()
        fitted_xlim = canvas._ax.get_xlim()

        # 同布局重绘（增添条目）：保持适配出的窗口
        state = canvas._state.copy()
        state.visible_artifacts = ["id1", "id1"]
        canvas.sync_state(state.copy(), ["id1"])
        canvas.render(state.copy())

        assert canvas._ax.get_xlim() == pytest.approx(fitted_xlim)

    def test_fit_quad_layout_each_axes(self, qapp):
        """四视图：各子图独立适配。"""
        canvas = _make_canvas(qapp, "quad")
        for ax in canvas._fig.axes:
            ax.set_xlim(-0.01, 0.01)

        canvas.fit_to_data()

        for ax in canvas._fig.axes:
            assert np.ptp(ax.get_xlim()) == pytest.approx(1.05, rel=1e-2)

    def test_fit_no_orbit_data_noop(self, qapp):
        """无轨道数据（空选中）：不抛错、不改动。"""
        canvas = _make_canvas(qapp)
        state = canvas._state.copy()
        state.visible_artifacts = []
        canvas.sync_state(state.copy(), [])
        canvas.render(state.copy())
        before = canvas._ax.get_xlim()

        canvas.fit_to_data()

        assert canvas._ax.get_xlim() == before
