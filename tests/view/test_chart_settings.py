"""tests for src.view.chart_settings -- 图表设置持久化与画布应用。"""

from __future__ import annotations

import numpy as np
import pytest
from e2m2e.data.templates.seed import EARTH_MOON_MU

_MU = EARTH_MOON_MU


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


def _make_provider(artifacts: dict[str, dict]):
    def provider(artifact_id: str):
        return artifacts.get(artifact_id)

    return provider


def _dro_eph(n: int = 60) -> np.ndarray:
    th = np.linspace(0, 2 * np.pi, n)
    moon = 1 - _MU
    return np.column_stack([moon + 0.6 * np.cos(th), -0.6 * np.sin(th), 0.05 * np.sin(3 * th)])


class TestSettingsPersistence:
    """QSettings 保存/加载往返。"""

    def test_roundtrip(self, qapp, tmp_path):
        from PyQt6.QtCore import QSettings

        from src.view.chart_settings import ChartSettings, load_settings, save_settings

        # 用独立 ini 文件隔离，不污染真实设置
        qs = QSettings(str(tmp_path / "chart.ini"), QSettings.Format.IniFormat)
        settings = ChartSettings(
            orbit_linewidth=1.5,
            colormap="Dark2",
            earth_size=300.0,
            moon_size=60.0,
            lp_color="#123456",
            lp_size=120.0,
            label_fontsize=14.0,
            z_ratio=0.3,
        )
        save_settings(qs, settings)
        loaded = load_settings(qs)
        assert loaded == settings

    def test_missing_keys_use_defaults(self, qapp, tmp_path):
        from PyQt6.QtCore import QSettings

        from src.view.chart_settings import ChartSettings, load_settings

        qs = QSettings(str(tmp_path / "empty.ini"), QSettings.Format.IniFormat)
        loaded = load_settings(qs)
        assert loaded == ChartSettings()


class TestCanvasAppliesSettings:
    """画布按 ChartSettings 渲染：线宽 / 颜色 / L 点样式 / z_ratio。"""

    def _canvas(self, qapp):
        from src.view.canvas import CanvasState, OrbitCanvas

        canvas = OrbitCanvas()
        canvas.set_artifacts_provider(
            _make_provider(
                {
                    "id1": {
                        "label": "DRO",
                        "mu": _MU,
                        "ephemeris_synodic": _dro_eph(),
                    }
                }
            )
        )
        canvas.sync_state(
            CanvasState(
                visible_artifacts=["id1"],
                show_bodies=True,
                show_libration=True,
                plot_content="ephemeris",
            ),
            ["id1"],
        )
        return canvas

    def test_orbit_linewidth_applied(self, qapp):
        from src.view.chart_settings import ChartSettings

        canvas = self._canvas(qapp)
        canvas.set_chart_settings(ChartSettings(orbit_linewidth=2.5))
        canvas.render()
        ax = canvas._fig.axes[0]
        # 第一条线是轨道
        assert ax.lines[0].get_linewidth() == pytest.approx(2.5)

    def test_lp_color_and_size_applied(self, qapp):
        from src.view.chart_settings import ChartSettings

        canvas = self._canvas(qapp)
        canvas.set_chart_settings(
            ChartSettings(lp_color="#00ff00", lp_size=200.0)
        )
        canvas.render()
        ax = canvas._fig.axes[0]
        lp_lines = [ln for ln in ax.lines if ln.get_marker() == "^"]
        assert len(lp_lines) == 5
        assert lp_lines[0].get_color() == "#00ff00"
        assert lp_lines[0].get_markersize() == pytest.approx(200.0**0.5)

    def test_z_ratio_applied_to_equal_aspect(self, qapp):
        from src.view.chart_settings import ChartSettings

        canvas = self._canvas(qapp)
        canvas.set_chart_settings(ChartSettings(z_ratio=0.8))
        canvas.render()
        ax = canvas._fig.axes[0]
        xs = np.ptp(ax.get_xlim())
        ys = np.ptp(ax.get_ylim())
        zs = np.ptp(ax.get_zlim())
        # Z 区间 = XY 较小范围的 0.8 倍
        assert zs == pytest.approx(min(xs, ys) * 0.8, rel=0.05)
