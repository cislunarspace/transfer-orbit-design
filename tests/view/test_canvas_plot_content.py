"""tests for src.view.canvas -- 绘制内容（初猜 / 星历 / 叠加）渲染组合（#359）。

覆盖 frame × plot_content 组合下画布消费的轨迹，断言 Line3D 数量与数据来源。
不测像素、不测实现细节，只断言外部可见的"画了几条线、来自哪份轨迹"。
"""

from __future__ import annotations

import numpy as np
import pytest
from e2m2e.data.templates.seed import EARTH_MOON_MU


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


_MU = EARTH_MOON_MU


def _orbit(n: int = 60, *, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, 6))


def _pos(n: int = 60, *, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, 3))


def _make_provider(artifacts: dict[str, dict]):
    def provider(artifact_id: str):
        return artifacts.get(artifact_id)

    return provider


class TestSynodicPlotContentCombinations:
    """会合系下 plot_content × 数据存在的组合（叠加渲染的 Line3D 计数）。"""

    def _canvas_with_design_orbit(self, qapp):
        """构造一个有初猜 + 星历两份的 design_orbit 画布。"""
        from src.view.canvas import OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "design": {
                        "initial_guess_states": _orbit(60, seed=0),
                        "ephemeris_synodic": _pos(60, seed=1),
                        "ephemeris_position_km": _pos(60, seed=2),
                        "ephemeris_times_et": np.linspace(0.0, 1e6, 60),
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        return canvas

    def test_guess_content_draws_only_initial_guess(self, qapp):
        """plot_content='guess'：会合系 3D 下只画 1 条初猜线。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState

        canvas = self._canvas_with_design_orbit(qapp)
        state = CanvasState(
            visible_artifacts=["design"],
            show_bodies=False,
            show_libration=False,
            plot_content="guess",
        )
        canvas.sync_state(state, ["design"])
        canvas.render()

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 1

    def test_ephemeris_content_draws_only_ephemeris_synodic(self, qapp):
        """plot_content='ephemeris'：会合系 3D 下只画 1 条星历会合系线。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState

        canvas = self._canvas_with_design_orbit(qapp)
        state = CanvasState(
            visible_artifacts=["design"],
            show_bodies=False,
            show_libration=False,
            plot_content="ephemeris",
        )
        canvas.sync_state(state, ["design"])
        canvas.render()

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 1

    def test_overlay_content_draws_two_lines_distinct_style(self, qapp):
        """plot_content='overlay'：会合系 3D 下画 2 条线，颜色不同 + 线型不同。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState

        canvas = self._canvas_with_design_orbit(qapp)
        state = CanvasState(
            visible_artifacts=["design"],
            show_bodies=False,
            show_libration=False,
            plot_content="overlay",
        )
        canvas.sync_state(state, ["design"])
        canvas.render()

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 2
        # 颜色区分（TAB10 相邻色）+ 线型区分（实线 vs 虚线）
        linestyles = {ln.get_linestyle() for ln in lines}
        assert linestyles == {"-", "--"}
        assert lines[0].get_color() != lines[1].get_color()

    def test_overlay_falls_back_to_single_when_initial_guess_missing(self, qapp):
        """control_orbit Artifact（无初猜）在 overlay 下只画星历一条。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "ctrl": {
                        "initial_guess_states": None,  # control_orbit 无初猜
                        "ephemeris_synodic": _pos(50, seed=3),
                        "ephemeris_position_km": _pos(50, seed=4),
                        "ephemeris_times_et": np.linspace(0.0, 1e6, 50),
                        "label": "受控",
                        "mu": _MU,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["ctrl"],
            show_bodies=False,
            show_libration=False,
            plot_content="overlay",
        )
        canvas.sync_state(state, ["ctrl"])
        canvas.render()

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 1

    def test_overlay_falls_back_to_single_when_ephemeris_missing(self, qapp):
        """旧 design_orbit Artifact（无 ephemeris）在 overlay 下只画初猜一条。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "old": {
                        "initial_guess_states": _orbit(50, seed=5),
                        "ephemeris_synodic": None,
                        "ephemeris_position_km": None,
                        "ephemeris_times_et": None,
                        "label": "旧 DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["old"],
            show_bodies=False,
            show_libration=False,
            plot_content="overlay",
        )
        canvas.sync_state(state, ["old"])
        canvas.render()

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 1

    def test_ephemeris_synodic_line_data_is_mu_shifted(self, qapp):
        """会合系 × 星历：画出的线数据 == ephemeris_synodic（已减 μ）。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState, OrbitCanvas

        eph_synodic = _pos(40, seed=7)  # 已经在 _artifact_for_id 减过 μ 之后
        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _orbit(40, seed=8),
                        "ephemeris_synodic": eph_synodic,
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=False,
            show_libration=False,
            plot_content="ephemeris",
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 1
        xdata, ydata, zdata = lines[0].get_data_3d()
        np.testing.assert_array_equal(np.asarray(xdata), eph_synodic[:, 0])
        np.testing.assert_array_equal(np.asarray(ydata), eph_synodic[:, 1])
        np.testing.assert_array_equal(np.asarray(zdata), eph_synodic[:, 2])


class Test3DDataEqualBoxAspect:
    """3D 渲染的等比/填充两种模式。

    equal_aspect=True 时按数据范围等比（box 分量比 == 数据范围比）；
    equal_aspect=False（默认）时保留 mpl 默认比例（z 轴不被压成数据比例，
    近平面轨道 DRO 的 Z 细节清晰可见）。
    """

    def test_3d_box_aspect_data_equal_for_flat_orbit(self, qapp):
        """equal_aspect=True：DRO 形状数据（XY≈0.6、Z≈0.05）的 box z/x 比 == 数据 z/x 比。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        n = 120
        theta = np.linspace(0, 2 * np.pi, n)
        moon = 1 - _MU
        x = moon + 0.6 * np.cos(theta)
        y = -0.6 * np.sin(theta)  # 逆行
        z = 0.05 * np.sin(3 * theta)  # 星历摄动下的小 Z 振幅
        eph_syn = np.column_stack([x, y, z])
        ig = np.column_stack([x, y, np.zeros(n), np.zeros((n, 3))])

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": ig,
                        "ephemeris_synodic": eph_syn,
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        canvas.sync_state(
            CanvasState(
                visible_artifacts=["id1"],
                show_bodies=False,
                show_libration=False,
                plot_content="ephemeris",
                equal_aspect=True,
            ),
            ["id1"],
        )
        canvas.render()

        ax = canvas._fig.axes[0]
        rx, ry, rz = np.ptp(ax.get_xlim()), np.ptp(ax.get_ylim()), np.ptp(ax.get_zlim())
        bx, by, bz = ax.get_box_aspect()
        # 等比例：box 分量比 == 数据范围比。Z 数据小，box z 也该小。
        assert bz / bx == pytest.approx(rz / rx, rel=0.05)
        assert bz / by == pytest.approx(rz / ry, rel=0.05)

    def test_3d_default_non_equal_fills_z(self, qapp):
        """equal_aspect=False（默认）：3D box z 分量不被压成数据比例，Z 细节放大。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        n = 120
        theta = np.linspace(0, 2 * np.pi, n)
        moon = 1 - _MU
        x = moon + 0.6 * np.cos(theta)
        y = -0.6 * np.sin(theta)
        z = 0.05 * np.sin(3 * theta)
        eph_syn = np.column_stack([x, y, z])
        ig = np.column_stack([x, y, np.zeros(n), np.zeros((n, 3))])

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": ig,
                        "ephemeris_synodic": eph_syn,
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        canvas.sync_state(
            CanvasState(
                visible_artifacts=["id1"],
                show_bodies=False,
                show_libration=False,
                plot_content="ephemeris",
            ),
            ["id1"],
        )
        canvas.render()

        ax = canvas._fig.axes[0]
        rx, ry, rz = np.ptp(ax.get_xlim()), np.ptp(ax.get_ylim()), np.ptp(ax.get_zlim())
        bx, by, bz = ax.get_box_aspect()
        # 默认非等比：box 的 z/x 比大于数据 z/x 比（z 被放大而非压成 0.083）。
        assert bz / bx > (rz / rx) * 3
        assert bz / by > (rz / ry) * 3


class Test2DProjectionPlaneCorrect:
    """2D 投影的天体/平动点标注应按投影平面取坐标。

    回归 guard：e2m2e 的 plot_libration_points / plot_primary_bodies 在 2D 下
    无视投影平面、恒用 (x,y)；XZ/YZ 投影下 L4/L5 的 Y≈±0.87 被错误画进纵轴
    （应为 Z），把 ylim 撑到 ±0.95，使 Z 数据细节（±0.05）被压扁看不见。
    """

    def test_xz_and_yz_ylim_reflects_z_not_libration_y(self, qapp):
        from src.view.canvas import CanvasState, OrbitCanvas

        n = 120
        theta = np.linspace(0, 2 * np.pi, n)
        moon = 1 - _MU
        x = moon + 0.6 * np.cos(theta)
        y = -0.6 * np.sin(theta)  # 逆行
        z = 0.05 * np.sin(3 * theta)  # 星历摄动下的小 Z 振幅
        eph_syn = np.column_stack([x, y, z])
        ig = np.column_stack([x, y, np.zeros(n), np.zeros((n, 3))])

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": ig,
                        "ephemeris_synodic": eph_syn,
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        z_range = float(np.ptp(eph_syn[:, 2]))  # 0.1
        for proj in ("xz", "yz"):
            canvas.sync_state(
                CanvasState(
                    visible_artifacts=["id1"],
                    projection=proj,
                    show_bodies=True,
                    show_libration=True,
                    plot_content="ephemeris",
                ),
                ["id1"],
            )
            canvas.render()
            ax = canvas._fig.axes[0]
            ylim_range = float(np.ptp(ax.get_ylim()))
            # 纵轴是 Z：应反映 Z 数据（~0.1+margin），而非被 L4/L5 的 Y 撑到 ~1.9
            assert ylim_range < z_range * 3, (
                f"{proj} 纵轴范围 {ylim_range:.3f} 远大于 Z 数据 {z_range:.3f}，疑被平动点 Y 坐标污染"
            )


class Test2DEqualAspect:
    """2D 投影的等比/填充两种模式。

    equal_aspect=True 时 aspect='equal'（纵/横每数据单位像素比≈1）；
    equal_aspect=False（默认）时 aspect='auto'，每轴独立填满画面，Z 细节清晰。
    """

    def test_2d_projections_have_equal_aspect(self, qapp):
        """equal_aspect=True：纵/横每数据单位的像素比≈1（如实反映轨道几何）。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        n = 120
        theta = np.linspace(0, 2 * np.pi, n)
        moon = 1 - _MU
        x = moon + 0.6 * np.cos(theta)
        y = -0.6 * np.sin(theta)
        z = 0.05 * np.sin(3 * theta)
        eph_syn = np.column_stack([x, y, z])
        ig = np.column_stack([x, y, np.zeros(n), np.zeros((n, 3))])

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": ig,
                        "ephemeris_synodic": eph_syn,
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        for proj in ("xy", "xz", "yz"):
            canvas.sync_state(
                CanvasState(
                    visible_artifacts=["id1"],
                    projection=proj,
                    show_bodies=False,
                    show_libration=False,
                    plot_content="ephemeris",
                    equal_aspect=True,
                ),
                ["id1"],
            )
            canvas.render()
            canvas._fig.canvas.draw()  # 触发 renderer，拿 axes 像素尺寸
            ax = canvas._fig.axes[0]
            bbox = ax.get_window_extent()
            xrng = float(np.ptp(ax.get_xlim()))
            yrng = float(np.ptp(ax.get_ylim()))
            # 纵/横每数据单位的像素比；等比例时应≈1
            ratio = (bbox.height / yrng) / (bbox.width / xrng)
            assert abs(ratio - 1.0) < 0.1, (
                f"{proj} 纵/横单位像素比 {ratio:.2f}，非等比例（轨道形状会被拉伸失真）"
            )

    def test_2d_default_non_equal_fills_z(self, qapp):
        """equal_aspect=False（默认）：XZ/YZ 投影纵轴（Z）被放大填满，不再压成细条。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        n = 120
        theta = np.linspace(0, 2 * np.pi, n)
        moon = 1 - _MU
        x = moon + 0.6 * np.cos(theta)
        y = -0.6 * np.sin(theta)
        z = 0.05 * np.sin(3 * theta)
        eph_syn = np.column_stack([x, y, z])
        ig = np.column_stack([x, y, np.zeros(n), np.zeros((n, 3))])

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": ig,
                        "ephemeris_synodic": eph_syn,
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        for proj in ("xz", "yz"):
            canvas.sync_state(
                CanvasState(
                    visible_artifacts=["id1"],
                    projection=proj,
                    show_bodies=False,
                    show_libration=False,
                    plot_content="ephemeris",
                ),
                ["id1"],
            )
            canvas.render()
            canvas._fig.canvas.draw()
            ax = canvas._fig.axes[0]
            bbox = ax.get_window_extent()
            xrng = float(np.ptp(ax.get_xlim()))
            yrng = float(np.ptp(ax.get_ylim()))
            ratio = (bbox.height / yrng) / (bbox.width / xrng)
            # 非等比：Z 数据范围远小于 X/Y，被拉伸填满画面 → 单位像素比 > 1
            assert ratio > 3.0, (
                f"{proj} 纵/横单位像素比 {ratio:.2f}，Z 未被放大（细节仍被压缩）"
            )


class TestInertialPlotContentCombinations:
    """惯性系下 plot_content × 数据存在的组合。

    惯性系下初猜无几何意义（CR3BP 无量纲），main_window 会灰显"初猜"按钮，
    画布层不再单独分支：plot_content='overlay' 与 'ephemeris' 都只画星历。
    """

    def test_inertial_overlay_draws_only_ephemeris_position(self, qapp):
        """frame=inertial + plot_content=overlay：只画 1 条星历惯性线（初猜无几何意义）。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _orbit(40, seed=0),
                        "ephemeris_synodic": _pos(40, seed=1),
                        "ephemeris_position_km": _pos(40, seed=2) * 1e5,
                        "ephemeris_times_et": None,
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=False,
            show_libration=False,
            frame="inertial",
            plot_content="overlay",
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 1  # 只画星历惯性位置，初猜不画

    def test_inertial_ephemeris_same_as_overlay_when_guess_present(self, qapp):
        """frame=inertial 下 overlay 与 ephemeris 等价（初猜无几何意义）。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState, OrbitCanvas

        provider_data = {
            "id1": {
                "initial_guess_states": _orbit(40, seed=0),
                "ephemeris_synodic": _pos(40, seed=1),
                "ephemeris_position_km": _pos(40, seed=2) * 1e5,
                "ephemeris_times_et": None,
                "label": "DRO",
                "mu": _MU,
            }
        }
        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(_make_provider(provider_data))

        canvas.sync_state(
            CanvasState(
                visible_artifacts=["id1"],
                show_bodies=False,
                show_libration=False,
                frame="inertial",
                plot_content="overlay",
            ),
            ["id1"],
        )
        canvas.render()
        n_overlay = len(
            [c for c in canvas._fig.axes[0].get_children() if isinstance(c, Line3D)]
        )

        canvas.sync_state(
            CanvasState(
                visible_artifacts=["id1"],
                show_bodies=False,
                show_libration=False,
                frame="inertial",
                plot_content="ephemeris",
            ),
            ["id1"],
        )
        canvas.render()
        n_eph = len(
            [c for c in canvas._fig.axes[0].get_children() if isinstance(c, Line3D)]
        )

        assert n_overlay == n_eph == 1


def _make_window():
    from unittest.mock import patch

    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow()


class TestMainWindowPlotContentControls:
    """main_window 在 Artifact 选择/坐标系切换时正确灰显"初猜"按钮。"""

    def test_design_orbit_artifact_keeps_guess_enabled(self, qapp):
        """选中 design_orbit Artifact 时，"初猜"按钮可点。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            source_tool="design_orbit",
            state_data=_orbit(20),
            extra={"mu": _MU, "ephemeris": {"synodic_position": _pos(20)}},
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        assert w._viz.projection_toolbar.plot_guess.isEnabled()

    def test_control_orbit_artifact_disables_guess(self, qapp):
        """选中 control_orbit Artifact 时，"初猜"按钮灰显（无 CR3BP 初猜）。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="ephemeris",
            label="受控",
            source_tool="control_orbit",
            state_data=_orbit(20),
            extra={"mu": _MU, "position_km": _pos(20) * 1e5,
                   "times_et": np.linspace(0, 1e6, 20)},
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        assert not w._viz.projection_toolbar.plot_guess.isEnabled()
        # plot_content 自动从 'guess' 退到 'ephemeris'（默认 'overlay' 不变，
        # 但若用户曾选过 guess，会被切走）
        assert w._canvas_state.plot_content != "guess"

    def test_inertial_frame_disables_guess(self, qapp):
        """切到惯性系时，"初猜"按钮灰显。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            source_tool="design_orbit",
            state_data=_orbit(20),
            extra={
                "mu": _MU,
                "ephemeris": {
                    "synodic_position": _pos(20),
                    "position_km": _pos(20) * 1e5,
                    "times_et": np.linspace(0, 1e6, 20),
                },
            },
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        assert w._viz.projection_toolbar.plot_guess.isEnabled()

        w._on_frame_changed("inertial")
        assert not w._viz.projection_toolbar.plot_guess.isEnabled()

    def test_inertial_switch_with_guess_selected_falls_back_to_ephemeris(self, qapp):
        """会合系选了初猜，切到惯性系后 plot_content 自动退到 ephemeris。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            source_tool="design_orbit",
            state_data=_orbit(20),
            extra={
                "mu": _MU,
                "ephemeris": {
                    "synodic_position": _pos(20),
                    "position_km": _pos(20) * 1e5,
                    "times_et": np.linspace(0, 1e6, 20),
                },
            },
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        w._on_plot_content_changed("guess")
        assert w._canvas_state.plot_content == "guess"

        w._on_frame_changed("inertial")
        # 切到惯性系后初猜不可用，自动退到星历
        assert w._canvas_state.plot_content == "ephemeris"

    def test_plot_content_button_signals_update_state(self, qapp):
        """toolbar.plot_* 按钮 click 经 slot 更新 _canvas_state.plot_content。"""
        w = _make_window()
        assert w._canvas_state.plot_content == "overlay"  # 默认
        w._viz.projection_toolbar.plot_ephemeris.click()
        assert w._canvas_state.plot_content == "ephemeris"
        w._viz.projection_toolbar.plot_overlay.click()
        assert w._canvas_state.plot_content == "overlay"


class TestMainWindowInertialHintDesignOrbit:
    """main_window._selected_artifacts_have_inertial 对 design_orbit 也识别星历。"""

    def test_design_orbit_with_ephemeris_position_no_hint(self, qapp):
        """design_orbit Artifact 的 ephemeris 含 position_km + times_et 时不提示。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            source_tool="design_orbit",
            state_data=_orbit(20),
            extra={
                "mu": _MU,
                "ephemeris": {
                    "synodic_position": _pos(20),
                    "position_km": _pos(20) * 1e5,
                    "times_et": np.linspace(0, 1e6, 20),
                },
            },
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        w._on_frame_changed("inertial")
        assert "无星历惯性数据" not in w._status_bar.currentMessage()

    def test_design_orbit_without_ephemeris_position_shows_hint(self, qapp):
        """design_orbit Artifact 的 ephemeris 不含 position_km/times_et 时提示。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="仅 CR3BP",
            source_tool="design_orbit",
            state_data=_orbit(20),
            extra={"mu": _MU},  # 无 ephemeris
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        w._on_frame_changed("inertial")
        assert "无星历惯性数据" in w._status_bar.currentMessage()

    def test_design_orbit_without_ephemeris_warns_in_synodic(self, qapp):
        """#359 US 10：design_orbit 产物无标称星历，会合系下也明确提示，而非静默只画初猜。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="仅 CR3BP",
            source_tool="design_orbit",
            state_data=_orbit(20),
            extra={"mu": _MU},  # 无 ephemeris
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        assert "无标称星历" in w._log.toPlainText()


class TestRestoredDesignOrbitArtifact:
    """#359 完成标准 5：从磁盘恢复的历史 design_orbit Artifact 也支持绘制内容。

    回归 guard：discovery 必须把 dro/ 下的 Artifact 标记为 source_tool="design_orbit"，
    否则 _artifact_for_id 会把它当 control_orbit 处理（state_data → ephemeris_synodic），
    初猜与星历两槽错位。
    """

    def test_restored_design_orbit_exposes_both_tracks(self, qapp, tmp_path):
        """save → discover → load → _artifact_for_id 暴露初猜 + 标称星历两份。"""
        from src.engine.facade_bridge import OrbitDesignResultData
        from src.engine.persistence import load_artifact_arrays, save_artifact
        from src.model.discovery import discover_artifacts

        n = 30
        rng = np.random.default_rng(11)
        result = OrbitDesignResultData(
            orbit_type="DRO",
            epoch_utc="2024-01-01T00:00:00",
            duration_day=30.0,
            initial_state=np.zeros(6),
            cr3bp_jacobi=3.0058,
            mu=_MU,
            states=rng.standard_normal((n, 6)),
            times=np.linspace(0, 30, n),
            correction_converged=True,
            correction_iterations=3,
            ephemeris={
                "year": np.full(n, 2024),
                "month": np.ones(n, dtype=int),
                "day": np.ones(n, dtype=int),
                "hour": np.zeros(n, dtype=int),
                "minute": np.zeros(n, dtype=int),
                "second": np.zeros(n, dtype=float),
                "position_km": rng.standard_normal((n, 3)) * 1e5,
                "velocity_mps": rng.standard_normal((n, 3)),
                "synodic_position": rng.standard_normal((n, 3)) + 1.0,
                "times_jd_tdb": None,
                "times_et": np.linspace(7.5e8, 7.6e8, n),
            },
        )
        save_artifact(result, tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        # discovery 推断 source_tool
        assert a.source_tool == "design_orbit"
        # 懒加载 NPZ → extra["ephemeris"] 全字段
        assert load_artifact_arrays(a) is True
        assert "ephemeris" in a.extra

        w = _make_window()
        w._project.add(a)
        data = w._artifact_for_id(a.artifact_id)
        assert data is not None
        # 初猜（CR3BP）与星历（synodic / position_km / times_et）四槽都可达
        assert data["initial_guess_states"] is not None
        assert data["ephemeris_synodic"] is not None
        assert data["ephemeris_position_km"] is not None
        assert data["ephemeris_times_et"] is not None
