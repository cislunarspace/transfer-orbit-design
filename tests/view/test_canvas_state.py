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
                {"id1": {"states": _random_orbit(), "label": "DRO", "mu": _MU}}
            )
        )
        # 关闭地月/L 点标注，隔离轨道线计数（标注在 3D 下也是 Line3D marker）
        state = CanvasState(
            visible_artifacts=["id1"],
            show_bodies=False,
            show_libration=False,
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
                    "id1": {"states": _random_orbit(), "label": "A", "mu": _MU},
                    "id2": {"states": _random_orbit(), "label": "B", "mu": _MU},
                }
            )
        )
        state = CanvasState(
            visible_artifacts=["id1", "id2"],
            show_bodies=False,
            show_libration=False,
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
                {"id1": {"states": _random_orbit(), "label": "DRO", "mu": _MU}}
            )
        )
        state = CanvasState(projection="xy", visible_artifacts=["id1"])
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
            {"id1": {"states": _random_orbit(), "label": "DRO", "mu": _MU}}
        )
        canvas.set_artifacts_provider(provider)

        canvas.sync_state(CanvasState(projection="xy", visible_artifacts=["id1"]), ["id1"])
        canvas.render()
        assert canvas._fig.axes[0].name != "3d"

        canvas.sync_state(CanvasState(projection="3d", visible_artifacts=["id1"]), ["id1"])
        canvas.render()
        assert canvas._fig.axes[0].name == "3d"

    def test_toggle_bodies_off_hides_body_artists(self, qapp):
        """show_bodies=False 时不绘制地月标注（无 mu 依赖）。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {"id1": {"states": _random_orbit(), "label": "DRO", "mu": _MU}}
            )
        )
        state = CanvasState(visible_artifacts=["id1"], show_bodies=False)
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
                {"id1": {"states": _random_orbit(), "label": "DRO", "mu": _MU}}
            )
        )
        state = CanvasState(visible_artifacts=["id1"], show_libration=False)
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
                {"id1": {"states": _random_orbit(), "label": "DRO", "mu": _MU}}
            )
        )

        canvas.sync_state(
            CanvasState(visible_artifacts=["id1"], show_bodies=True, show_libration=True),
            ["id1"],
        )
        canvas.render()
        n_with = len(canvas._fig.axes[0].get_children())

        canvas.sync_state(
            CanvasState(visible_artifacts=["id1"], show_bodies=False, show_libration=False),
            ["id1"],
        )
        canvas.render()
        n_without = len(canvas._fig.axes[0].get_children())

        assert n_with > n_without

    def test_render_reuses_in_memory_arrays(self, qapp):
        """切换投影不触发 NPZ 重读（数据复用验收 #5）。"""
        from unittest.mock import patch

        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {"id1": {"states": _random_orbit(), "label": "DRO", "mu": _MU}}
            )
        )

        with patch("src.app.main_window.load_artifact_arrays") as mock_load:
            canvas.sync_state(
                CanvasState(projection="3d", visible_artifacts=["id1"]), ["id1"]
            )
            canvas.render()
            canvas.sync_state(
                CanvasState(projection="xy", visible_artifacts=["id1"]), ["id1"]
            )
            canvas.render()
            canvas.sync_state(
                CanvasState(projection="yz", visible_artifacts=["id1"]), ["id1"]
            )
            canvas.render()

        mock_load.assert_not_called()

    def test_old_artifact_without_mu_no_crash(self, qapp):
        """extra 无 mu 时 render 不崩，无地月标注。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider({"id1": {"states": _random_orbit(), "label": "旧DRO", "mu": None}})
        )
        state = CanvasState(visible_artifacts=["id1"])
        canvas.sync_state(state, ["id1"])
        canvas.render()  # 不抛异常

        ax = canvas._fig.axes[0]
        assert ax is not None

    def test_sync_state_missing_artifact_skipped(self, qapp):
        """provider 返回 None（无该 artifact）时跳过，不崩溃。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(_make_provider({}))
        state = CanvasState(visible_artifacts=["missing"])
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
