"""tests for src.view.canvas -- 视图保持（增添轨道条目不重置窗口）。

render() 全量重建 Axes，但布局（projection × frame × center）不变的重绘
应恢复用户旋转/缩放后的视角与坐标范围；布局切换（投影/坐标系/中心）改变
视图空间，仍走自动缩放。首次渲染（此前无数据）不恢复，避免把空轴的
(0, 1) 默认范围带到有数据的图上。
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


def _orbit(n: int = 50) -> np.ndarray:
    """确定性轨道状态矩阵 (n, 6)，范围约 [-1, 1]。"""
    t = np.linspace(0.0, 2.0 * np.pi, n)
    return np.column_stack(
        (
            0.5 * np.cos(t),
            0.5 * np.sin(t),
            0.1 * np.sin(2 * t),
            np.zeros(n),
            np.zeros(n),
            np.zeros(n),
        )
    )


def _provider_with(*aids: str):
    """构造返回指定 artifact 的数据回调。"""
    data = {aid: {"initial_guess_states": _orbit(), "label": aid, "mu": _MU} for aid in aids}

    def provider(artifact_id: str):
        return data.get(artifact_id)

    return provider


def _make_canvas(qapp, *aids: str):
    from src.view.canvas import CanvasState, OrbitCanvas

    canvas = OrbitCanvas()
    canvas.set_artifacts_provider(_provider_with(*aids))
    state = CanvasState(
        visible_artifacts=list(aids),
        show_bodies=False,
        show_libration=False,
        plot_content="guess",
    )
    canvas.sync_state(state.copy(), list(aids))
    canvas.render(state.copy())
    return canvas


class TestViewPreservation:
    def test_adding_artifact_preserves_3d_view(self, qapp):
        """增添轨道条目：相机角与三轴范围保持用户交互结果。"""
        canvas = _make_canvas(qapp, "id1")
        ax = canvas._ax
        # 模拟用户旋转 + 缩放
        ax.view_init(elev=45.0, azim=60.0)
        ax.set_xlim(-0.2, 0.2)
        ax.set_ylim(0.0, 0.4)
        ax.set_zlim(-0.1, 0.1)

        # 增添轨道条目：多选渲染 id1 + id2
        state = canvas._state.copy()
        state.visible_artifacts = ["id1", "id2"]
        canvas.sync_state(state.copy(), ["id1", "id2"])
        canvas.render(state.copy())

        new_ax = canvas._ax
        assert new_ax is not ax  # 全量重建 Axes
        assert new_ax.elev == pytest.approx(45.0)
        assert new_ax.azim == pytest.approx(60.0)
        assert new_ax.get_xlim() == pytest.approx((-0.2, 0.2))
        assert new_ax.get_ylim() == pytest.approx((0.0, 0.4))
        assert new_ax.get_zlim() == pytest.approx((-0.1, 0.1))

    def test_adding_artifact_preserves_2d_view(self, qapp):
        """2D 投影下增添条目：两轴范围保持。"""
        canvas = _make_canvas(qapp, "id1")
        state = canvas._state.copy()
        state.projection = "xy"
        canvas.sync_state(state.copy(), ["id1"])
        canvas.render(state.copy())
        canvas._ax.set_xlim(-0.1, 0.1)
        canvas._ax.set_ylim(0.0, 0.3)

        state = canvas._state.copy()
        state.visible_artifacts = ["id1", "id2"]
        canvas.sync_state(state.copy(), ["id1", "id2"])
        canvas.render(state.copy())

        assert canvas._ax.get_xlim() == pytest.approx((-0.1, 0.1))
        assert canvas._ax.get_ylim() == pytest.approx((0.0, 0.3))

    def test_removing_artifact_preserves_view(self, qapp):
        """移除条目同一视图空间，窗口同样保持。"""
        canvas = _make_canvas(qapp, "id1", "id2")
        canvas._ax.set_xlim(-0.2, 0.2)

        state = canvas._state.copy()
        state.visible_artifacts = ["id1"]
        canvas.sync_state(state.copy(), ["id1"])
        canvas.render(state.copy())

        assert canvas._ax.get_xlim() == pytest.approx((-0.2, 0.2))

    def test_projection_change_resets_view(self, qapp):
        """切换投影改变视图空间：不恢复旧范围，按数据自动缩放。"""
        canvas = _make_canvas(qapp, "id1")
        canvas._ax.set_xlim(-0.001, 0.001)

        state = canvas._state.copy()
        state.projection = "xy"
        canvas.sync_state(state.copy(), ["id1"])
        canvas.render(state.copy())

        # 自动缩放覆盖数据范围（约 [-0.5, 0.5]），不再是用户缩放窗口
        assert canvas._ax.get_xlim() != pytest.approx((-0.001, 0.001))
        assert canvas._ax.get_xlim()[1] > 0.3

    def test_inplace_state_mutation_still_detects_layout_change(self, qapp):
        """main_window 原地修改 CanvasState（同一对象）：投影切换仍须识别为
        布局变化并重置视图，不能因新旧 state 同一对象而误保持。"""
        canvas = _make_canvas(qapp, "id1")
        state = canvas._state
        canvas._ax.set_xlim(-0.001, 0.001)

        state.projection = "xy"  # 原地改字段（生产路径：main_window 直接赋值）
        canvas.sync_state(state, ["id1"])
        canvas.render(state)

        assert canvas._ax.get_xlim() != pytest.approx((-0.001, 0.001))

    def test_center_change_resets_view(self, qapp):
        """切换绘图中心整体平移坐标系：不恢复旧范围（居中逻辑重新接管）。"""
        canvas = _make_canvas(qapp, "id1")
        user_xlim = (-0.2, 0.2)
        canvas._ax.set_xlim(user_xlim)

        state = canvas._state.copy()
        state.center = "moon"
        canvas.sync_state(state.copy(), ["id1"])
        canvas.render(state.copy())

        # moon 中心视图按新坐标对称居中（质心系下月球在 x≈0.98 处，平移后
        # 轨道中心远离 0），不再是用户的缩放窗口
        assert canvas._ax.get_xlim() != pytest.approx(user_xlim)

    def test_first_render_not_polluted_by_empty_axes(self, qapp):
        """首次渲染（此前无数据）不恢复空轴的 (0, 1) 默认范围。"""
        canvas = _make_canvas(qapp, "id1")

        # __init__ 的空 Axes 默认范围是 (0, 1)；首次 render 后应按数据缩放
        lo, hi = canvas._ax.get_xlim()
        assert lo < -0.3
        assert hi > 0.3

    def test_quad_layout_preserves_each_subplot(self, qapp):
        """四视图布局：四个子图的窗口分别保持。"""
        canvas = _make_canvas(qapp, "id1")
        state = canvas._state.copy()
        state.projection = "quad"
        canvas.sync_state(state.copy(), ["id1"])
        canvas.render(state.copy())
        assert len(canvas._fig.axes) == 4
        # 模拟用户缩放各子图（创建顺序 3d / xy / xz / yz）
        canvas._fig.axes[0].set_xlim(-0.15, 0.15)
        canvas._fig.axes[1].set_xlim(-0.25, 0.25)
        canvas._fig.axes[2].set_xlim(-0.35, 0.35)

        state = canvas._state.copy()
        state.visible_artifacts = ["id1", "id2"]
        canvas.sync_state(state.copy(), ["id1", "id2"])
        canvas.render(state.copy())

        assert len(canvas._fig.axes) == 4
        assert canvas._fig.axes[0].get_xlim() == pytest.approx((-0.15, 0.15))
        assert canvas._fig.axes[1].get_xlim() == pytest.approx((-0.25, 0.25))
        assert canvas._fig.axes[2].get_xlim() == pytest.approx((-0.35, 0.35))

    def test_empty_render_invalidates_view(self, qapp):
        """渲染空选中集后视图失效：下次有数据时按数据缩放，不恢复旧窗口。"""
        canvas = _make_canvas(qapp, "id1")
        canvas._ax.set_xlim(-0.001, 0.001)

        state = canvas._state.copy()
        state.visible_artifacts = []
        canvas.sync_state(state.copy(), [])
        canvas.render(state.copy())

        state = canvas._state.copy()
        state.visible_artifacts = ["id1"]
        canvas.sync_state(state.copy(), ["id1"])
        canvas.render(state.copy())

        assert canvas._ax.get_xlim() != pytest.approx((-0.001, 0.001))

    def test_preserve_view_false_each_render_autoscales(self, qapp):
        """preserve_view=False 时逐帧渲染各自自动缩放（GIF 导出场景）。

        帧数据是增长前缀：若误保持视图，后续帧会锁死在首帧的小窗口里。
        """
        canvas = _make_canvas(qapp, "id1")
        full = _orbit(200)
        spans = []

        for frame in (full[:20], full):
            canvas.set_artifacts_provider(
                lambda _aid, _f=frame: {
                    "initial_guess_states": _f,
                    "label": "id1",
                    "mu": _MU,
                }
            )
            canvas.sync_state(canvas._state.copy(), ["id1"])
            canvas.render(preserve_view=False)
            lo, hi = canvas._ax.get_xlim()
            spans.append(hi - lo)

        # 各帧按自身数据缩放：全轨迹窗口明显大于短前缀帧的窗口
        assert spans[1] > 2.0 * spans[0]
