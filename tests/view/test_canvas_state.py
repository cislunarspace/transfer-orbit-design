"""tests for src.view.canvas.CanvasState + OrbitCanvas.render -- 渲染状态与单入口。"""

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


_MU = 0.012153645822478


def _random_orbit(n: int = 100) -> np.ndarray:
    """生成随机轨道状态矩阵 (n, 6)。"""
    rng = np.random.default_rng(42)
    return rng.random((n, 6))


def _make_provider(artifacts: dict[str, dict]):
    """构造 artifact 数据回调（模拟 main_window._artifact_for_id）。"""

    def provider(artifact_id: str):
        return artifacts.get(artifact_id)

    return provider


class TestCanvasState:
    def test_default_projection_is_3d(self):
        from src.view.canvas import CanvasState

        state = CanvasState()
        assert state.projection == "3d"
        assert state.visible_artifacts == []
        assert state.show_bodies is True
        assert state.show_libration is True

    def test_default_frame_is_synodic(self):
        from src.view.canvas import CanvasState

        state = CanvasState()
        assert state.frame == "synodic"

    def test_default_plot_content_is_overlay(self, qapp):
        """#359：绘制内容默认 'overlay'（初猜 + 星历叠加）。"""
        from src.view.canvas import CanvasState

        state = CanvasState()
        assert state.plot_content == "overlay"

    def test_copy_carries_frame(self):
        from src.view.canvas import CanvasState

        state = CanvasState(frame="inertial")
        copied = state.copy()
        assert copied.frame == "inertial"
        copied.frame = "synodic"
        assert state.frame == "inertial"  # 副本独立

    def test_copy_carries_plot_content(self, qapp):
        """#359：copy 携带 plot_content 字段且独立。"""
        from src.view.canvas import CanvasState

        state = CanvasState(plot_content="guess")
        copied = state.copy()
        assert copied.plot_content == "guess"
        copied.plot_content = "ephemeris"
        assert state.plot_content == "guess"  # 副本独立

    def test_copy_returns_new_instance(self):
        from src.view.canvas import CanvasState

        state = CanvasState(projection="xy", visible_artifacts=["a", "b"])
        copied = state.copy()
        assert copied is not state
        assert copied.projection == "xy"
        assert copied.show_bodies is True

    def test_copy_visible_artifacts_list_is_independent(self):
        from src.view.canvas import CanvasState

        state = CanvasState(visible_artifacts=["a", "b"])
        copied = state.copy()
        copied.visible_artifacts.append("c")
        assert state.visible_artifacts == ["a", "b"]
        assert copied.visible_artifacts == ["a", "b", "c"]


class TestOrbitCanvasRender:
    def test_render_single_artifact_3d(self, qapp):
        """sync_state + render 后 3D ax 有 Line3D。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        # 关闭地月/L 点标注，隔离轨道线计数（标注在 3D 下也是 Line3D marker）
        # plot_content="guess" 只画初猜（避免 overlay 默认下两份 None 槽的歧义）
        state = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=False,
            show_libration=False,
            plot_content="guess",
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()

        from mpl_toolkits.mplot3d.art3d import Line3D

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 1

    def test_render_multiple_artifacts_tab10_colors(self, qapp):
        """两条轨道颜色不同（tab10 分配）。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "A",
                        "mu": _MU,
                    },
                    "id2": {
                        "initial_guess_states": _random_orbit(),
                        "label": "B",
                        "mu": _MU,
                    },
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1", "id2"],
            show_bodies=False,
            show_libration=False,
            plot_content="guess",
        )
        canvas.sync_state(state, ["id1", "id2"])
        canvas.render()

        from mpl_toolkits.mplot3d.art3d import Line3D

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 2
        assert lines[0].get_color() != lines[1].get_color()

    def test_switch_projection_xy_creates_2d_axes(self, qapp):
        """projection='xy' 时 render 创建 2D ax 且有 Line2D。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        state = CanvasState(
            projection="xy", visible_artifacts=["id1"], plot_content="guess"
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()

        from matplotlib.lines import Line2D

        ax = canvas._fig.axes[0]
        assert ax.name != "3d"
        lines = [c for c in ax.get_children() if isinstance(c, Line2D)]
        assert len(lines) == 1

    def test_switch_back_to_3d_from_2d(self, qapp):
        """投影 2D -> 3D 切换后 ax 回到 3d。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        provider = _make_provider(
            {
                "id1": {
                    "initial_guess_states": _random_orbit(),
                    "label": "DRO",
                    "mu": _MU,
                }
            }
        )
        canvas.set_artifacts_provider(provider)

        canvas.sync_state(
            CanvasState(projection="xy", visible_artifacts=["id1"], plot_content="guess"),
            ["id1"],
        )
        canvas.render()
        assert canvas._fig.axes[0].name != "3d"

        canvas.sync_state(
            CanvasState(projection="3d", visible_artifacts=["id1"], plot_content="guess"),
            ["id1"],
        )
        canvas.render()
        assert canvas._fig.axes[0].name == "3d"

    def test_toggle_bodies_off_hides_body_artists(self, qapp):
        """show_bodies=False 时不绘制地月标注（无 mu 依赖）。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1"], show_bodies=False, plot_content="guess"
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()
        # 无异常即通过；地月标注禁用不影响轨道渲染
        ax = canvas._fig.axes[0]
        assert ax is not None

    def test_toggle_libration_off_hides_libration(self, qapp):
        """show_libration=False 时不绘制 L 点标注。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1"], show_libration=False, plot_content="guess"
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()
        ax = canvas._fig.axes[0]
        assert ax is not None

    def test_render_with_bodies_and_libration_on_adds_artists(self, qapp):
        """默认开标注时，地月 + L 点 artist 比仅轨道时多。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "DRO",
                        "mu": _MU,
                    }
                }
            )
        )

        canvas.sync_state(
            CanvasState(
                visible_artifacts=["id1"],
                show_bodies=True,
                show_libration=True,
                plot_content="guess",
            ),
            ["id1"],
        )
        canvas.render()
        n_with = len(canvas._fig.axes[0].get_children())

        canvas.sync_state(
            CanvasState(
                visible_artifacts=["id1"],
                show_bodies=False,
                show_libration=False,
                plot_content="guess",
            ),
            ["id1"],
        )
        canvas.render()
        n_without = len(canvas._fig.axes[0].get_children())

        assert n_with > n_without

    def test_old_artifact_without_mu_no_crash(self, qapp):
        """extra 无 mu 时 render 不崩，无地月标注。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "旧DRO",
                        "mu": None,
                    }
                }
            )
        )
        state = CanvasState(visible_artifacts=["id1"], plot_content="guess")
        canvas.sync_state(state, ["id1"])
        canvas.render()  # 不抛异常

        ax = canvas._fig.axes[0]
        assert ax is not None

    def test_sync_state_missing_artifact_skipped(self, qapp):
        """provider 返回 None（无该 artifact）时跳过，不崩溃。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(_make_provider({}))
        state = CanvasState(visible_artifacts=["missing"], plot_content="guess")
        canvas.sync_state(state, ["missing"])
        canvas.render()
        ax = canvas._fig.axes[0]
        assert ax is not None

    def test_plot_multiple_passthrough_still_works(self, qapp):
        """plot_multiple 便捷封装仍可用（向后兼容）。"""
        from src.view.canvas import OrbitCanvas

        canvas = OrbitCanvas()
        canvas.plot_multiple(orbits=[(_random_orbit(), "A"), (_random_orbit(), "B")])
        ax = canvas._fig.axes[0]
        assert "2 条轨道" in ax.get_title()


def _random_position_km(n: int = 50) -> np.ndarray:
    """生成随机 GCRS 位置数组 (n, 3)，单位 km（量级 ~1e5 模拟地月距离）。"""
    rng = np.random.default_rng(7)
    return rng.standard_normal((n, 3)) * 1e5


class TestOrbitCanvasInertialFrame:
    """frame='inertial' 分支：ephemeris_position_km 画轨迹 + 地球原点 + 月球轨迹（SPICE）。"""

    def test_inertial_orbit_line_equals_position_km(self, qapp):
        """frame=inertial 时 3D 轨道线的 xyz 数据 == 注入的 ephemeris_position_km。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        position_km = _random_position_km()
        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "受控",
                        "mu": _MU,
                        "ephemeris_position_km": position_km,
                        "ephemeris_times_et": None,  # 此例不测月球轨迹
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=False,  # 隔离：只断言轨道线
            show_libration=False,
            frame="inertial",
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()

        from mpl_toolkits.mplot3d.art3d import Line3D

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) == 1
        xdata, ydata, zdata = lines[0].get_data_3d()
        np.testing.assert_array_equal(np.asarray(xdata), position_km[:, 0])
        np.testing.assert_array_equal(np.asarray(ydata), position_km[:, 1])
        np.testing.assert_array_equal(np.asarray(zdata), position_km[:, 2])

    def test_inertial_2d_projection_uses_position_km(self, qapp):
        """frame=inertial + projection=xy：2D 轨道线数据 == position_km 的 (x,y)。"""
        from matplotlib.lines import Line2D

        from src.view.canvas import CanvasState, OrbitCanvas

        position_km = _random_position_km()
        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "受控",
                        "mu": _MU,
                        "ephemeris_position_km": position_km,
                        "ephemeris_times_et": None,
                    }
                }
            )
        )
        state = CanvasState(
            projection="xy",
            visible_artifacts=["id1"],
            show_bodies=False,
            show_libration=False,
            frame="inertial",
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()

        ax = canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line2D)]
        assert len(lines) == 1
        np.testing.assert_array_equal(np.asarray(lines[0].get_xdata()), position_km[:, 0])
        np.testing.assert_array_equal(np.asarray(lines[0].get_ydata()), position_km[:, 1])

    def test_inertial_does_not_draw_libration_points(self, qapp):
        """frame=inertial 时即使 show_libration=True 也不画 L 点。

        回归 guard：惯性系下不应触发 draw_libration_points（无 mu 几何意义）。
        通过 patch viz_adapter.draw_libration_points 断言不被调用。
        """
        from unittest.mock import patch

        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "受控",
                        "mu": _MU,
                        "ephemeris_position_km": _random_position_km(),
                        "ephemeris_times_et": None,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=False,
            show_libration=True,  # 开 L 点开关，但 inertial 不应画
            frame="inertial",
        )
        canvas.sync_state(state, ["id1"])
        with patch("src.engine.viz_adapter.draw_libration_points") as mock_lib:
            canvas.render()
        mock_lib.assert_not_called()

    def test_inertial_draws_earth_origin_marker(self, qapp):
        """frame=inertial + show_bodies=True：画地球原点 marker（在 (0,0,0)）。"""
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "受控",
                        "mu": _MU,
                        "ephemeris_position_km": _random_position_km(),
                        "ephemeris_times_et": None,
                    }
                }
            )
        )
        # 关 show_bodies 时只有 1 条轨道线
        state_off = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=False,
            show_libration=False,
            frame="inertial",
        )
        canvas.sync_state(state_off, ["id1"])
        canvas.render()
        ax = canvas._fig.axes[0]
        n_off = len([c for c in ax.get_children() if isinstance(c, Line3D)])

        # 开 show_bodies 时多出地球 marker（+ 月球轨迹若 SPICE 可用）
        state_on = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=True,
            show_libration=False,
            frame="inertial",
        )
        canvas.sync_state(state_on, ["id1"])
        canvas.render()
        ax = canvas._fig.axes[0]
        n_on = len([c for c in ax.get_children() if isinstance(c, Line3D)])
        assert n_on > n_off  # 至少多出地球 marker

    def test_inertial_without_position_km_does_not_crash(self, qapp):
        """position_km 缺失时 inertial 分支不崩（降级为空轨迹）。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(),
                        "label": "无星历",
                        "mu": _MU,
                        "ephemeris_position_km": None,
                        "ephemeris_times_et": None,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=True,
            show_libration=False,
            frame="inertial",
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()  # 不抛
        ax = canvas._fig.axes[0]
        assert ax is not None

    @pytest.mark.spice
    def test_inertial_draws_moon_trajectory_from_spice(self, qapp):
        """frame=inertial + times_et：用 SPICE 查月球 GCRS 位置画轨迹线。

        需要 de440s.bsp 与 naif0012.tls（@pytest.mark.spice，CI 跳过）。
        断言月球轨迹线存在于 axes（灰色虚线，label='Moon'）。
        """
        from e2m2e.data.kernels.manager import SPICEManager

        # 确保 .bsp + 闰秒已 furnsh（find_ephemeris_kernel + load_kernel 在
        # viz_adapter.draw_moon_gcrs_trajectory 内部完成，这里只验证可调用）
        from src.engine.viz_adapter import draw_moon_gcrs_trajectory

        from src.view.canvas import CanvasState, OrbitCanvas

        # 取一段真实 ET 范围（2024 年初约一周），5 个采样点足够画线
        spice = SPICEManager()
        spice._ensure_leapseconds()
        from e2m2e.data.kernels._spice_loader import get_spiceypy

        sp = get_spiceypy()
        t0 = sp.str2et("2024-01-01T00:00:00")
        times_et = np.array([t0 + 86400.0 * k for k in range(5)])

        position_km = _random_position_km(5)
        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "initial_guess_states": _random_orbit(5),
                        "label": "受控",
                        "mu": _MU,
                        "ephemeris_position_km": position_km,
                        "ephemeris_times_et": times_et,
                    }
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=True,
            show_libration=False,
            frame="inertial",
        )
        canvas.sync_state(state, ["id1"])
        canvas.render()

        # 月球轨迹线在 axes 中（label='Moon'，灰色虚线）
        from mpl_toolkits.mplot3d.art3d import Line3D

        ax = canvas._fig.axes[0]
        moon_lines = [
            c
            for c in ax.get_children()
            if isinstance(c, Line3D) and (c.get_label() == "Moon")
        ]
        assert len(moon_lines) == 1
        # 复用同一入口校验：直接调 viz_adapter 函数也返回 True
        import matplotlib.pyplot as plt

        fig2 = plt.figure()
        ax2 = fig2.add_subplot(111, projection="3d")
        try:
            ok = draw_moon_gcrs_trajectory(ax2, times_et, is_3d=True)
        finally:
            plt.close(fig2)
        assert ok is True


def _make_window():
    """构造测试用 MainWindow（不扫描磁盘）。"""
    from unittest.mock import patch

    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow()


class TestMainWindowCanvasStateFlow:
    """CanvasState 流集成：toolbar 信号 -> main_window slot -> canvas render。"""

    def test_projection_button_signal_updates_state(self, qapp):
        w = _make_window()
        w._viz.projection_toolbar.projection_xy.click()
        assert w._canvas_state.projection == "xy"

    def test_projection_changed_rerenders_canvas(self, qapp):
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            state_data=_random_orbit(),
            extra={"mu": _MU},
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        assert w._selected_artifact_ids == [a.artifact_id]
        assert w._viz.canvas._fig.axes[0].name == "3d"

        w._on_projection_changed("xy")
        assert w._viz.canvas._fig.axes[0].name != "3d"

    def test_toggle_signals_update_state(self, qapp):
        w = _make_window()
        w._viz.projection_toolbar.show_bodies.setChecked(False)
        assert w._canvas_state.show_bodies is False
        w._viz.projection_toolbar.show_libration.setChecked(False)
        assert w._canvas_state.show_libration is False

    def test_old_artifact_missing_mu_logs_warning(self, qapp):
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="旧DRO",
            state_data=_random_orbit(),
            extra={},
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        assert "无 mu" in w._log.toPlainText()

    def test_click_artifact_renders_orbit_on_canvas(self, qapp):
        """点击 artifact 后画布上确实画出轨道（Line3D）。

        回归 guard：若 sync_state 未填充 visible_artifacts（阻塞 #1），
        render() 遍历空列表，画布上不会有轨道线。
        """
        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            state_data=_random_orbit(),
            extra={"mu": _MU},
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)

        ax = w._viz.canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) >= 1

    def test_design_finished_renders_via_canvas_state(self, qapp):
        """_on_design_finished 走 CanvasState 流（render 单入口），不走旧 plot_orbit。

        回归 guard：若 _on_design_finished 调 _render_artifact（阻塞 #2），
        _selected_artifact_ids 不更新、画布上无轨道。
        """
        from pathlib import Path
        from unittest.mock import patch

        from mpl_toolkits.mplot3d.art3d import Line3D

        from src.engine.facade_bridge import OrbitDesignResultData

        rng = np.random.default_rng(42)
        result = OrbitDesignResultData(
            orbit_type="DRO",
            epoch_utc="2024-01-01T00:00:00",
            duration_day=365.25,
            initial_state=np.zeros(6),
            cr3bp_jacobi=3.0058,
            mu=_MU,
            states=rng.standard_normal((50, 6)),
            times=np.linspace(0, 365.25, 50),
            correction_converged=True,
            correction_iterations=3,
        )

        w = _make_window()
        with patch("src.app.main_window.save_artifact") as mock_save:
            mock_save.return_value = (Path("/fake/dro.json"), Path("/fake/dro.npz"))
            w._on_design_finished(result)

        # _selected_artifact_ids 已更新
        assert len(w._selected_artifact_ids) == 1

        # 画布上有轨道
        ax = w._viz.canvas._fig.axes[0]
        lines = [c for c in ax.get_children() if isinstance(c, Line3D)]
        assert len(lines) >= 1

    def test_render_reuses_in_memory_arrays(self, qapp, tmp_path):
        """切换投影不触发 NPZ 重读——懒加载仅一次，投影切换复用内存（验收 #5）。

        走 MainWindow 集成路径：点击触发一次 load_artifact_arrays，
        随后多次切换投影，断言调用计数仍为 1。
        """
        from unittest.mock import patch

        from src.engine.facade_bridge import OrbitDesignResultData
        from src.engine.persistence import load_artifact_arrays as _real_load
        from src.engine.persistence import save_artifact
        from src.model.discovery import discover_artifacts

        rng = np.random.default_rng(42)
        result = OrbitDesignResultData(
            orbit_type="DRO",
            epoch_utc="2024-01-01T00:00:00",
            duration_day=365.25,
            initial_state=np.zeros(6),
            cr3bp_jacobi=3.0058,
            mu=_MU,
            states=rng.standard_normal((50, 6)),
            times=np.linspace(0, 365.25, 50),
            correction_converged=True,
            correction_iterations=3,
        )
        save_artifact(result, tmp_path)
        artifacts = discover_artifacts(tmp_path)
        assert len(artifacts) == 1
        a = artifacts[0]
        assert a.state_data is None  # discovery 不加载数组

        w = _make_window()
        w._project.add(a)

        with patch("src.app.main_window.load_artifact_arrays", wraps=_real_load) as mock_load:
            w._on_artifact_clicked(a.artifact_id)
            assert mock_load.call_count == 1  # 点击时懒加载一次
            # 多次切换投影，不应再次读盘
            w._on_projection_changed("xy")
            w._on_projection_changed("yz")
            w._on_projection_changed("3d")
            assert mock_load.call_count == 1  # 仍为 1，数据已在内存

    def test_frame_button_signal_updates_state(self, qapp):
        """toolbar.frame_inertial.click() 经 slot 更新 _canvas_state.frame。"""
        w = _make_window()
        w._viz.projection_toolbar.frame_inertial.click()
        assert w._canvas_state.frame == "inertial"
        w._viz.projection_toolbar.frame_synodic.click()
        assert w._canvas_state.frame == "synodic"

    def test_frame_inertial_without_ephemeris_shows_status_hint(self, qapp):
        """inertial 切换时若 Artifact 无 position_km/times_et，状态栏给提示。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="orbit",
            label="纯 CR3BP",
            state_data=_random_orbit(),
            extra={"mu": _MU},  # 无 position_km / times_et
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        w._on_frame_changed("inertial")
        assert w._canvas_state.frame == "inertial"
        assert "无星历惯性数据" in w._status_bar.currentMessage()

    def test_frame_inertial_with_ephemeris_no_hint(self, qapp):
        """inertial 切换时若 Artifact 有 position_km/times_et，状态栏无降级提示。"""
        from src.model import Artifact

        w = _make_window()
        a = Artifact(
            artifact_type="ephemeris",
            label="受控",
            state_data=_random_orbit(),
            extra={
                "mu": _MU,
                "position_km": _random_position_km(),
                "times_et": np.linspace(0, 1e6, 50),
            },
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        w._on_frame_changed("inertial")
        assert "无星历惯性数据" not in w._status_bar.currentMessage()
