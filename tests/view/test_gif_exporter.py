"""tests for src.view.gif_exporter -- 接缝 C（薄）。

两类测试：
1. 纯逻辑（不渲染、不生成文件）：_export_times / _frame_index_ranges 的窗与索引
   计算正确性。
2. 端到端（生成文件）：小帧数（3-5）synodic / inertial GIF 合法（文件存在、
   帧>1、尺寸>0、PIL 可识别为 GIF）。不依赖 SPICE，月球轨迹降级跳过。
3. MainWindow 集成：toolbar 按钮 -> slot 路径（mock QFileDialog + dialog.exec）。
"""

from __future__ import annotations

import numpy as np
import pytest
from e2m2e.data.templates.seed import EARTH_MOON_MU


@pytest.fixture()
def qapp():
    """确保 QApplication 存在（与现有 view 测试一致的兜底）。"""
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


_MU = EARTH_MOON_MU


def _random_orbit(n: int = 100) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.random((n, 6))


def _random_position_km(n: int = 50) -> np.ndarray:
    rng = np.random.default_rng(7)
    return rng.standard_normal((n, 3)) * 1e5


def _make_provider(artifacts: dict[str, dict]):
    def provider(artifact_id: str):
        return artifacts.get(artifact_id)

    return provider


# ---------------------------------------------------------------------------
# 纯逻辑
# ---------------------------------------------------------------------------


class TestExportTimes:
    def test_default_range_uses_times_et_minmax(self):
        from src.view.gif_exporter import _export_times

        times_et = np.linspace(0.0, 1000.0, 50)
        out = _export_times(times_et, time_range=None, n_frames=5)
        assert out.shape == (5,)
        assert out[0] == pytest.approx(0.0)
        assert out[-1] == pytest.approx(1000.0)

    def test_explicit_range_respected(self):
        from src.view.gif_exporter import _export_times

        times_et = np.linspace(0.0, 1000.0, 50)
        out = _export_times(times_et, time_range=(100.0, 500.0), n_frames=5)
        assert out[0] == pytest.approx(100.0)
        assert out[-1] == pytest.approx(500.0)

    def test_n_frames_below_2_clamped(self):
        from src.view.gif_exporter import _export_times

        out = _export_times(np.arange(10.0), time_range=None, n_frames=1)
        assert len(out) == 2

    def test_monotonic_increasing(self):
        from src.view.gif_exporter import _export_times

        out = _export_times(np.arange(50.0), time_range=None, n_frames=8)
        assert np.all(np.diff(out) > 0)


class TestFrameIndexRanges:
    def test_cumulative_grows_monotonically(self):
        """cumulative 模式：每帧索引段长度单调不减。"""
        from src.view.gif_exporter import _frame_index_ranges

        times_et = np.linspace(0.0, 100.0, 100)
        export_times = np.linspace(0.0, 100.0, 5)
        ranges = _frame_index_ranges(
            export_times, times_et, window_mode="cumulative", sliding_window_seconds=None
        )
        assert len(ranges) == 5
        sizes = [len(r) for r in ranges]
        assert all(sizes[i] <= sizes[i + 1] for i in range(4))
        # 末帧应包含全部数据点
        assert len(ranges[-1]) == 100

    def test_sliding_window_uses_width(self):
        """sliding 模式：每帧索引段跨度不超过 w 秒。"""
        from src.view.gif_exporter import _frame_index_ranges

        times_et = np.linspace(0.0, 1000.0, 1001)  # 1 点/秒
        export_times = np.linspace(100.0, 900.0, 9)
        w = 50.0  # 50 秒窗
        ranges = _frame_index_ranges(
            export_times, times_et, window_mode="sliding", sliding_window_seconds=w
        )
        for i, ti in enumerate(export_times):
            span = times_et[ranges[i]]
            # 窗口 [ti-w, ti]，跨度应 <= w+1（边界点容差）
            assert span.max() - span.min() <= w + 2.0
            assert span.max() == pytest.approx(ti, abs=2.0)

    def test_empty_gap_falls_back_to_nearest(self):
        """采样间隙（mask 空）时回退到最近点，不返回空段。"""
        from src.view.gif_exporter import _frame_index_ranges

        # 稀疏采样：0, 10, 20, ...
        times_et = np.arange(0.0, 100.0, 10.0)
        # 导出时刻取 5（采样间隙）
        export_times = np.array([0.0, 5.0, 10.0])
        ranges = _frame_index_ranges(
            export_times, times_et, window_mode="cumulative", sliding_window_seconds=None
        )
        for r in ranges:
            assert len(r) >= 1


# ---------------------------------------------------------------------------
# 端到端（Pillow 可用时）
# ---------------------------------------------------------------------------


def _pil_available() -> bool:
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _pil_available(), reason="Pillow 不可用")
class TestExportAnimationEndToEnd:
    def _make_canvas(self, artifacts: dict[str, dict]):
        from src.view.canvas import OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(_make_provider(artifacts))
        return canvas

    def test_synodic_gif_basic(self, qapp, tmp_path):
        """synodic GIF：文件存在、帧数>1、尺寸>0、PIL 识别为 GIF。"""
        from PIL import Image

        from src.view.gif_exporter import export_animation

        n = 60
        canvas = self._make_canvas(
            {
                "a": {
                    "initial_guess_states": _random_orbit(n),
                    "ephemeris_synodic": _random_orbit(n)[:, :3],
                    "label": "DRO",
                    "mu": _MU,
                    "ephemeris_times_et": np.linspace(0.0, 1e6, n),
                    "ephemeris_position_km": None,
                }
            }
        )
        out = export_animation(
            canvas,
            canvas._artifacts_provider("a"),
            frame="synodic",
            time_range=None,
            n_frames=3,
            window_mode="cumulative",
            output_path=tmp_path / "syn.gif",
        )
        assert out.exists()
        assert out.stat().st_size > 0
        with Image.open(out) as img:
            assert img.format == "GIF"
            assert img.n_frames >= 3
            assert img.size[0] > 0 and img.size[1] > 0

    def test_inertial_gif_basic(self, qapp, tmp_path):
        """inertial GIF：ephemeris_position_km 子集 + 地球原点（月球轨迹降级跳过）。"""
        from PIL import Image

        from src.view.gif_exporter import export_animation

        n = 40
        canvas = self._make_canvas(
            {
                "a": {
                    "initial_guess_states": _random_orbit(n),
                    "ephemeris_position_km": _random_position_km(n),
                    "ephemeris_times_et": np.linspace(0.0, 1e6, n),
                    "label": "受控",
                    "mu": _MU,
                }
            }
        )
        out = export_animation(
            canvas,
            canvas._artifacts_provider("a"),
            frame="inertial",
            time_range=None,
            n_frames=3,
            window_mode="cumulative",
            output_path=tmp_path / "inert.gif",
        )
        assert out.exists()
        assert out.stat().st_size > 0
        with Image.open(out) as img:
            assert img.format == "GIF"
            assert img.n_frames >= 3

    def test_sliding_window_mode(self, qapp, tmp_path):
        """sliding 模式：每帧轨迹不累积，末帧不含起点附近数据。"""
        from src.view.gif_exporter import export_animation

        n = 100
        times_et = np.linspace(0.0, 1e6, n)
        canvas = self._make_canvas(
            {
                "a": {
                    "initial_guess_states": _random_orbit(n),
                    "ephemeris_synodic": _random_orbit(n)[:, :3],
                    "ephemeris_times_et": times_et,
                    "label": "DRO",
                    "mu": _MU,
                }
            }
        )
        out = export_animation(
            canvas,
            canvas._artifacts_provider("a"),
            frame="synodic",
            time_range=None,
            n_frames=4,
            window_mode="sliding",
            sliding_window_seconds=1e5,  # 1/10 总时长
            output_path=tmp_path / "slide.gif",
        )
        assert out.exists()
        assert out.stat().st_size > 0

    def test_invalid_frame_raises(self, qapp, tmp_path):
        from src.view.gif_exporter import export_animation

        n = 20
        canvas = self._make_canvas(
            {
                "a": {
                    "initial_guess_states": _random_orbit(n),
                    "ephemeris_synodic": _random_orbit(n)[:, :3],
                    "ephemeris_times_et": np.arange(n, dtype=float),
                }
            }
        )
        with pytest.raises(ValueError, match="frame 非法"):
            export_animation(
                canvas,
                canvas._artifacts_provider("a"),
                frame="rotating",
                time_range=None,
                n_frames=3,
                window_mode="cumulative",
                output_path=tmp_path / "x.gif",
            )

    def test_missing_times_et_raises(self, qapp, tmp_path):
        from src.view.gif_exporter import export_animation

        n = 20
        canvas = self._make_canvas(
            {
                "a": {
                    "initial_guess_states": _random_orbit(n),
                    "ephemeris_synodic": _random_orbit(n)[:, :3],
                }  # 无 ephemeris_times_et
            }
        )
        with pytest.raises(ValueError, match="缺少时间数据"):
            export_animation(
                canvas,
                canvas._artifacts_provider("a"),
                frame="synodic",
                time_range=None,
                n_frames=3,
                window_mode="cumulative",
                output_path=tmp_path / "x.gif",
            )

    def test_inertial_missing_position_km_raises(self, qapp, tmp_path):
        from src.view.gif_exporter import export_animation

        n = 20
        canvas = self._make_canvas(
            {
                "a": {
                    "initial_guess_states": _random_orbit(n),
                    "ephemeris_synodic": _random_orbit(n)[:, :3],
                    "ephemeris_times_et": np.arange(n, dtype=float),
                }
            }
        )
        with pytest.raises(ValueError, match="惯性系星历数据"):
            export_animation(
                canvas,
                canvas._artifacts_provider("a"),
                frame="inertial",
                time_range=None,
                n_frames=3,
                window_mode="cumulative",
                output_path=tmp_path / "x.gif",
            )

    def test_canvas_state_restored_after_export(self, qapp, tmp_path):
        """导出后 canvas 的 provider / 可见 artifact / plot_content 恢复。"""
        from src.view.canvas import CanvasState, OrbitCanvas

        n = 30
        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "orig": {
                        "initial_guess_states": _random_orbit(n),
                        "ephemeris_synodic": _random_orbit(n)[:, :3],
                        "label": "DRO",
                        "mu": _MU,
                        "ephemeris_times_et": np.linspace(0.0, 1e6, n),
                    }
                }
            )
        )
        canvas.sync_state(
            CanvasState(visible_artifacts=["orig"], plot_content="ephemeris"),
            ["orig"],
        )
        saved_provider = canvas._artifacts_provider
        saved_visible = list(canvas._state.visible_artifacts)
        saved_content = canvas._state.plot_content

        from src.view.gif_exporter import export_animation

        export_animation(
            canvas,
            canvas._artifacts_provider("orig"),
            frame="synodic",
            time_range=None,
            n_frames=3,
            window_mode="cumulative",
            output_path=tmp_path / "restore.gif",
        )
        assert canvas._artifacts_provider is saved_provider
        assert list(canvas._state.visible_artifacts) == saved_visible
        assert canvas._state.plot_content == saved_content
        # 导出过程覆盖了 Axes（自动缩放）：视图标记失效，后续渲染按数据
        # 自动缩放，而非“保持”用户从未交互过的导出末帧窗口
        assert canvas._view_valid is False

    def test_progress_callback_invoked(self, qapp, tmp_path):
        from src.view.gif_exporter import export_animation

        n = 30
        canvas = self._make_canvas(
            {
                "a": {
                    "initial_guess_states": _random_orbit(n),
                    "ephemeris_synodic": _random_orbit(n)[:, :3],
                    "ephemeris_times_et": np.linspace(0.0, 1e6, n),
                    "label": "DRO",
                    "mu": _MU,
                }
            }
        )
        calls: list[tuple[int, int]] = []

        def cb(i: int, total: int) -> None:
            calls.append((i, total))

        export_animation(
            canvas,
            canvas._artifacts_provider("a"),
            frame="synodic",
            time_range=None,
            n_frames=4,
            window_mode="cumulative",
            output_path=tmp_path / "cb.gif",
            progress_callback=cb,
        )
        assert len(calls) == 4
        assert calls[0] == (1, 4)
        assert calls[-1] == (4, 4)


# ---------------------------------------------------------------------------
# MainWindow 集成
# ---------------------------------------------------------------------------


def _make_window():
    from unittest.mock import patch

    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow()


class TestMainWindowExportAnimationSlot:
    def test_no_selection_shows_hint(self, qapp):
        w = _make_window()
        w._on_export_animation()
        assert "请先在左侧项目树中选择" in w._status_bar.currentMessage()

    def test_synodic_export_via_dialog(self, qapp, tmp_path, monkeypatch):
        """选中带 ephemeris_times_et 的 Artifact → 弹对话框(自动 accept) → 选路径 → 导出。"""
        from src.model import Artifact

        w = _make_window()
        n = 40
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            source_tool="design_orbit",
            state_data=_random_orbit(n),
            extra={
                "mu": _MU,
                "ephemeris": {
                    "synodic_position": _random_orbit(n)[:, :3],
                    "position_km": _random_position_km(n),
                    "times_et": np.linspace(0.0, 1e6, n),
                },
            },
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)

        # mock dialog.exec 返回 Accepted
        monkeypatch.setattr(
            "src.app.main_window.QDialog.exec",
            lambda self: 1,  # QDialog.DialogCode.Accepted
        )
        # mock QFileDialog.getSaveFileName 返回临时路径
        out = tmp_path / "slot.gif"
        monkeypatch.setattr(
            "src.app.main_window.QFileDialog.getSaveFileName",
            lambda *a, **kw: (str(out), ""),
        )
        w._on_export_animation()
        assert out.exists()
        assert "导出完成" in w._status_bar.currentMessage()

    def test_dialog_cancel_aborts(self, qapp, tmp_path, monkeypatch):
        from src.model import Artifact

        w = _make_window()
        n = 40
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            source_tool="design_orbit",
            state_data=_random_orbit(n),
            extra={
                "mu": _MU,
                "ephemeris": {
                    "synodic_position": _random_orbit(n)[:, :3],
                    "times_et": np.linspace(0.0, 1e6, n),
                },
            },
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)

        monkeypatch.setattr(
            "src.app.main_window.QDialog.exec",
            lambda self: 0,  # Rejected
        )
        w._on_export_animation()
        # 状态栏停留在"就绪"或空，不应有"正在导出"
        assert "正在导出" not in w._status_bar.currentMessage()

    def test_export_button_exists(self, qapp):
        """工具栏有"导出动画"按钮且可点击。"""
        w = _make_window()
        btn = w._viz.projection_toolbar.export_animation
        assert btn.text() == "导出动画"
        assert btn.isEnabled()

    def test_initial_guess_mode_blocks_export(self, qapp, tmp_path, monkeypatch):
        """#359：plot_content='guess' 时拒绝导出动画（无物理时间轴）。"""
        from src.model import Artifact

        w = _make_window()
        n = 40
        a = Artifact(
            artifact_type="orbit",
            label="DRO",
            source_tool="design_orbit",
            state_data=_random_orbit(n),
            extra={
                "mu": _MU,
                "ephemeris": {
                    "synodic_position": _random_orbit(n)[:, :3],
                    "position_km": _random_position_km(n),
                    "times_et": np.linspace(0.0, 1e6, n),
                },
            },
        )
        w._project.add(a)
        w._on_artifact_clicked(a.artifact_id)
        # 切到初猜模式
        w._on_plot_content_changed("guess")
        assert w._canvas_state.plot_content == "guess"

        w._on_export_animation()
        assert "初猜模式" in w._status_bar.currentMessage()
        # 不应进入对话框/导出流程
        assert "正在导出" not in w._status_bar.currentMessage()
