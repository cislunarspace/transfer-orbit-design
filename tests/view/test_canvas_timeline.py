"""tests for 主画布时间轴渲染（ADR-0014，issue #395）。

接缝：构造 CanvasState 直接调 OrbitCanvas.render()，断言 Axes 上
gid=timeline-marker 的 marker（是否存在、位置是否等于 times_et 插值）。
SPICE 月球查询经 viz_adapter 打桩，不触真实内核。
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


_TIMES = np.array([100.0, 200.0, 300.0])
_SYN = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 2.0, 2.0]])
_POS_KM = np.array([[10.0, 0.0, 0.0], [20.0, 10.0, 0.0], [30.0, 20.0, 10.0]])


def _make_canvas(qapp, *, with_km: bool = False):
    from src.view.canvas import OrbitCanvas

    canvas = OrbitCanvas()
    data = {
        "label": "受控",
        "mu": None,
        "ephemeris_synodic": _SYN,
        "ephemeris_times_et": _TIMES,
    }
    if with_km:
        data["ephemeris_position_km"] = _POS_KM

    canvas.set_artifacts_provider(lambda aid: data if aid == "a1" else None)
    return canvas


def _markers(ax):
    """收集 gid=timeline-marker 的 Line3D/scatter（3D 与 2D 兼容）。"""
    from mpl_toolkits.mplot3d.art3d import Line3D

    out = []
    for c in ax.get_children():
        if getattr(c, "get_gid", lambda: None)() == "timeline-marker":
            out.append(c)
    assert out or True
    return out


def _marker_xyz(ax):
    from mpl_toolkits.mplot3d.art3d import Line3D

    m = _markers(ax)
    assert m, "应有 timeline-marker"
    line = next(c for c in m if isinstance(c, Line3D))
    return np.column_stack([np.asarray(d) for d in line.get_data_3d()])


class TestSynodicMarker:
    def test_marker_at_interpolated_position(self, qapp):
        """会合系：current_et 落在采样点之间时，marker 位于线性插值位置。"""
        from src.view.canvas import CanvasState

        canvas = _make_canvas(qapp)
        canvas.sync_state(
            CanvasState(
                visible_artifacts=["a1"],
                show_bodies=False,
                show_libration=False,
                plot_content="ephemeris",
                current_et=150.0,
            ),
            ["a1"],
        )
        canvas.render()
        xyz = _marker_xyz(canvas._fig.axes[0])
        assert xyz[0] == pytest.approx([0.5, 0.5, 0.5])

    def test_marker_exactly_at_sample(self, qapp):
        """current_et 恰为采样点时，marker 位于该采样点。"""
        from src.view.canvas import CanvasState

        canvas = _make_canvas(qapp)
        canvas.sync_state(
            CanvasState(
                visible_artifacts=["a1"],
                show_bodies=False,
                show_libration=False,
                plot_content="ephemeris",
                current_et=200.0,
            ),
            ["a1"],
        )
        canvas.render()
        xyz = _marker_xyz(canvas._fig.axes[0])
        assert xyz[0] == pytest.approx([1.0, 1.0, 1.0])

    def test_no_marker_when_et_out_of_range(self, qapp):
        """current_et 超出产物时间范围：marker 消失。"""
        from src.view.canvas import CanvasState

        canvas = _make_canvas(qapp)
        canvas.sync_state(
            CanvasState(
                visible_artifacts=["a1"],
                show_bodies=False,
                show_libration=False,
                plot_content="ephemeris",
                current_et=999.0,
            ),
            ["a1"],
        )
        canvas.render()
        assert not _markers(canvas._fig.axes[0])

    def test_no_marker_when_current_et_none(self, qapp):
        """current_et=None（时间轴未激活）：不画任何 marker。"""
        from src.view.canvas import CanvasState

        canvas = _make_canvas(qapp)
        canvas.sync_state(
            CanvasState(
                visible_artifacts=["a1"],
                show_bodies=False,
                show_libration=False,
                plot_content="ephemeris",
            ),
            ["a1"],
        )
        canvas.render()
        assert not _markers(canvas._fig.axes[0])


class TestInertialMarker:
    def _render_inertial(self, qapp, **kw):
        from src.view.canvas import CanvasState

        canvas = _make_canvas(qapp, with_km=True)
        # 月球轨迹查询打桩：返回固定假月球位置（n,3），避免触真实内核
        from unittest.mock import patch

        fake_moon = np.tile(np.array([[4.0e5, 0.0, 0.0]]), (len(_TIMES), 1))
        with patch(
            "src.engine.viz_adapter.moon_position_gcrs", return_value=fake_moon
        ):
            canvas.sync_state(
                CanvasState(
                    visible_artifacts=["a1"],
                    show_bodies=True,
                    show_libration=False,
                    frame="inertial",
                    current_et=kw.get("current_et", 200.0),
                    projection=kw.get("projection", "3d"),
                    center=kw.get("center", "barycenter"),
                ),
                ["a1"],
            )
            canvas.render()
        return canvas

    def test_marker_at_interpolated_km(self, qapp):
        """惯性系：marker 位于 position_km 插值位置（GCRS km）。"""
        canvas = self._render_inertial(qapp, current_et=150.0)
        xyz = _marker_xyz(canvas._fig.axes[0])
        assert xyz[0] == pytest.approx([15.0, 5.0, 0.0])

    def test_marker_missing_when_out_of_range(self, qapp):
        """惯性系：超出时间范围 marker 消失。"""
        canvas = self._render_inertial(qapp, current_et=-1.0)
        assert not _markers(canvas._fig.axes[0])

    def test_quad_renders_marker_in_all_panels(self, qapp):
        """四视图：每个子图都有 marker。"""
        canvas = self._render_inertial(qapp, projection="quad")
        assert len(canvas._fig.axes) == 4
        for ax in canvas._fig.axes:
            assert _markers(ax), "四视图各子图都应有 marker"

    def test_moon_now_marker_at_interpolated_position(self, qapp):
        """惯性系地心视图：月球此刻 marker 位于月球轨迹插值位置。"""
        from unittest.mock import patch

        from src.view.canvas import CanvasState

        canvas = _make_canvas(qapp, with_km=True)
        # 月球轨迹随时间线性变化，便于验证插值
        fake_moon = np.column_stack(
            [np.linspace(3.8e5, 4.0e5, len(_TIMES)), np.zeros((len(_TIMES), 2))]
        )
        with patch(
            "src.engine.viz_adapter.moon_position_gcrs", return_value=fake_moon
        ):
            canvas.sync_state(
                CanvasState(
                    visible_artifacts=["a1"],
                    show_bodies=True,
                    show_libration=False,
                    frame="inertial",
                    current_et=150.0,
                ),
                ["a1"],
            )
            canvas.render()
        ax = canvas._fig.axes[0]
        from mpl_toolkits.mplot3d.art3d import Line3D

        moon_marker = next(
            c
            for c in _markers(ax)
            if isinstance(c, Line3D) and "月球（此刻）" in c.get_label()
        )
        x = np.asarray(moon_marker.get_data_3d()[0])[0]
        assert x == pytest.approx(3.85e5)


class TestSynodic2DMarker:
    def test_xy_projection_marker_position(self, qapp):
        """会合系 2D 投影：marker 落在 XY 平面插值位置。"""
        from src.view.canvas import CanvasState

        canvas = _make_canvas(qapp)
        canvas.sync_state(
            CanvasState(
                visible_artifacts=["a1"],
                show_bodies=False,
                show_libration=False,
                plot_content="ephemeris",
                projection="xy",
                current_et=250.0,
            ),
            ["a1"],
        )
        canvas.render()
        m = _markers(canvas._fig.axes[0])
        assert m
        off = m[0].get_offsets()
        assert off[0, 0] == pytest.approx(1.5) and off[0, 1] == pytest.approx(1.5)
