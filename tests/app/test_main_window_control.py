"""tests for MainWindow control_orbit dispatch + handlers (issue #348)。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.engine.facade_bridge import ControlResultData


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except ImportError:
        pytest.skip("QApplication 不可用")


def _make_window(qapp):
    """创建 MainWindow，mock 掉 discover_artifacts 避免扫描真实 output/。"""
    from src.app.main_window import MainWindow

    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow()


def _make_orbit_artifact(window, *, with_ephemeris: bool = True, mu: float | None = 0.0123):
    """向 window._project 注入一个 orbit Artifact 并选中它。"""
    from src.model import Artifact

    n = 10
    extra: dict = {"mu": mu}
    if with_ephemeris:
        extra["ephemeris"] = {
            "year": np.full(n, 2024),
            "month": np.ones(n, dtype=int),
            "day": np.ones(n, dtype=int),
            "hour": np.zeros(n, dtype=int),
            "minute": np.zeros(n, dtype=int),
            "second": np.zeros(n, dtype=float),
            "position_km": np.random.randn(n, 3),
            "velocity_mps": np.random.randn(n, 3),
            "synodic_position": np.random.randn(n, 3),
            "times_jd_tdb": None,
        }
    artifact = Artifact(
        artifact_type="orbit",
        label="测试 DRO",
        source_tool="design_orbit",
        state_data=np.random.randn(n, 6),
        times=np.linspace(0, 1, n),
        extra=extra,
    )
    window._project.add(artifact)
    window._selected_artifact_ids = [artifact.artifact_id]
    return artifact


def _select_control_tool(window):
    """切换到 control_orbit 工具并构建参数面板。"""
    window._current_tool_key = "control_orbit"
    window._build_tool_params("control_orbit")


class TestBuildToolParamsControl:
    def test_control_orbit_hidden_input_ephemeris_field(self, qapp):
        """control_orbit 工具不应在 UI 暴露 input_ephemeris。"""
        window = _make_window(qapp)
        _select_control_tool(window)
        assert "input_ephemeris" not in window._param_widgets

    def test_control_orbit_visible_params_present(self, qapp):
        """control_orbit 应暴露 control_mode / num_monte_carlo 等参数。"""
        window = _make_window(qapp)
        _select_control_tool(window)
        assert "control_mode" in window._param_widgets
        assert "num_monte_carlo" in window._param_widgets


class TestRunControlValidation:
    def test_run_control_without_selection_shows_status(self, qapp):
        """未选中任何 Artifact → _on_run → 状态栏提示，不启动 Worker。"""
        window = _make_window(qapp)
        _select_control_tool(window)
        window._selected_artifact_ids = []
        window._on_run()
        assert "请先选中" in window._status_bar.currentMessage()
        assert window._worker is None

    def test_run_control_with_old_artifact_without_ephemeris_blocked(self, qapp):
        """旧 Artifact（extra 无 ephemeris）→ 提示"无星历数据"。"""
        window = _make_window(qapp)
        _select_control_tool(window)
        _make_orbit_artifact(window, with_ephemeris=False)
        window._on_run()
        assert "无星历数据" in window._status_bar.currentMessage()
        assert window._worker is None

    def test_run_control_with_non_orbit_artifact_blocked(self, qapp):
        """选中非 orbit 类型 Artifact → _selected_orbit_artifact 返回 None。"""
        from src.model import Artifact

        window = _make_window(qapp)
        _select_control_tool(window)
        eph_artifact = Artifact(
            artifact_type="ephemeris",
            label="已有星历",
            state_data=np.random.randn(5, 6),
            times=np.arange(5),
        )
        window._project.add(eph_artifact)
        window._selected_artifact_ids = [eph_artifact.artifact_id]
        window._on_run()
        assert "请先选中" in window._status_bar.currentMessage()


class TestRunControlDispatch:
    def test_run_control_dispatches_control_worker(self, qapp):
        """选中 orbit Artifact（含 ephemeris）→ _on_run → ControlOrbitWorker 被构造。"""
        window = _make_window(qapp)
        _select_control_tool(window)
        _make_orbit_artifact(window, with_ephemeris=True)

        with patch("src.app.main_window.ControlOrbitWorker") as mock_cls:
            mock_instance = mock_cls.return_value
            window._on_run()
            mock_cls.assert_called_once()
            # Worker.start() 被调用
            mock_instance.start.assert_called_once()

    def test_run_control_passes_source_mu(self, qapp):
        """source_mu 应从 Artifact extra["mu"] 注入到 ControlOrbitWorker。"""
        window = _make_window(qapp)
        _select_control_tool(window)
        _make_orbit_artifact(window, with_ephemeris=True, mu=0.012153645822478)

        with patch("src.app.main_window.ControlOrbitWorker") as mock_cls:
            window._on_run()
            _, kwargs = mock_cls.call_args
            assert kwargs["source_mu"] == pytest.approx(0.012153645822478)


class TestOnControlFinished:
    def _make_result(self, n: int = 30) -> ControlResultData:
        return ControlResultData(
            num_failed=1,
            sk_statistic_rows=np.array([[1.0, 2.0, 3.0]]),
            maneuvers_mjd_tdb=np.array([60000.0, 60030.0]),
            maneuvers_delta_v_mps=np.array([0.5, 0.3]),
            controlled_states=np.random.randn(n, 6),
            controlled_times=np.arange(n),
            mu=0.012153645822478,
        )

    def test_on_control_finished_registers_ephemeris_artifact(self, qapp):
        """_on_control_finished 应在 Project 注册 artifact_type="ephemeris"。"""
        window = _make_window(qapp)
        result = self._make_result()

        with patch("src.app.main_window.save_control_result") as mock_save:
            mock_save.return_value = (Path("/fake/eph.json"), Path("/fake/eph.npz"))
            window._on_control_finished(result)

        eph_artifacts = [a for a in window._project.artifacts if a.artifact_type == "ephemeris"]
        assert len(eph_artifacts) == 1
        a = eph_artifacts[0]
        assert a.state_data is not None
        assert a.state_data.shape == (30, 6)
        assert a.extra["num_failed"] == 1
        assert a.extra["n_maneuvers"] == 2
        assert a.extra["total_delta_v_mps"] == pytest.approx(0.8)

    def test_on_control_finished_extra_contains_position_and_times_et(self, qapp):
        """_on_control_finished 应把 result.position_km/times_et 写入 Artifact.extra。"""
        window = _make_window(qapp)
        n = 5
        position_km = np.random.randn(n, 3)
        times_et = np.linspace(7.5e8, 7.6e8, n)
        result = ControlResultData(
            num_failed=0,
            sk_statistic_rows=np.array([[1.0, 2.0, 3.0]]),
            maneuvers_mjd_tdb=np.array([60000.0]),
            maneuvers_delta_v_mps=np.array([0.5]),
            controlled_states=np.random.randn(n, 6),
            controlled_times=times_et,
            mu=0.012153645822478,
            position_km=position_km,
            times_et=times_et,
        )

        with patch("src.app.main_window.save_control_result") as mock_save:
            mock_save.return_value = (Path("/fake/eph.json"), Path("/fake/eph.npz"))
            window._on_control_finished(result)

        eph_artifacts = [a for a in window._project.artifacts if a.artifact_type == "ephemeris"]
        assert len(eph_artifacts) == 1
        a = eph_artifacts[0]
        np.testing.assert_array_equal(a.extra["position_km"], position_km)
        np.testing.assert_array_equal(a.extra["times_et"], times_et)

    def test_on_control_finished_save_failure_keeps_artifact(self, qapp):
        """持久化失败时 in-memory Artifact 仍可用。"""
        window = _make_window(qapp)
        result = self._make_result()

        with patch("src.app.main_window.save_control_result", side_effect=OSError("disk full")):
            window._on_control_finished(result)

        eph_artifacts = [a for a in window._project.artifacts if a.artifact_type == "ephemeris"]
        assert len(eph_artifacts) == 1
        assert eph_artifacts[0].state_data is not None
        assert "持久化失败" in window._status_bar.currentMessage()

    def test_on_control_finished_all_failed_no_state_data(self, qapp):
        """全失败（controlled_states=None）时 Artifact 仍注册但无 state_data。"""
        window = _make_window(qapp)
        result = ControlResultData(
            num_failed=5,
            sk_statistic_rows=np.empty((0, 3)),
            maneuvers_mjd_tdb=np.array([]),
            maneuvers_delta_v_mps=np.array([]),
            controlled_states=None,
            controlled_times=None,
            mu=None,
        )

        with patch("src.app.main_window.save_control_result") as mock_save:
            mock_save.return_value = (Path("/fake/eph.json"), Path("/fake/eph.npz"))
            window._on_control_finished(result)

        eph_artifacts = [a for a in window._project.artifacts if a.artifact_type == "ephemeris"]
        assert len(eph_artifacts) == 1
        assert eph_artifacts[0].state_data is None


class TestArtifactForIdControlFields:
    def test_artifact_for_id_returns_position_km_and_times_et(self, qapp):
        """_artifact_for_id 应把 extra 里的 position_km/times_et 透传给画布接口。"""
        from src.model import Artifact

        window = _make_window(qapp)
        position_km = np.random.randn(5, 3)
        times_et = np.linspace(7.5e8, 7.6e8, 5)
        a = Artifact(
            artifact_type="ephemeris",
            label="受控星历",
            state_data=np.random.randn(5, 6),
            times=times_et,
            extra={
                "mu": 0.0123,
                "position_km": position_km,
                "times_et": times_et,
            },
        )
        window._project.add(a)

        result = window._artifact_for_id(a.artifact_id)
        assert result is not None
        np.testing.assert_array_equal(result["position_km"], position_km)
        np.testing.assert_array_equal(result["times_et"], times_et)

    def test_artifact_for_id_returns_none_for_missing_position_and_times_et(self, qapp):
        """旧 Artifact extra 无 position_km/times_et 时，回传 None（画布降级）。"""
        from src.model import Artifact

        window = _make_window(qapp)
        a = Artifact(
            artifact_type="orbit",
            label="旧轨道",
            state_data=np.random.randn(5, 6),
            extra={"mu": 0.0123},
        )
        window._project.add(a)

        result = window._artifact_for_id(a.artifact_id)
        assert result is not None
        assert result["position_km"] is None
        assert result["times_et"] is None


class TestOnControlError:
    def test_on_control_error_restores_button(self, qapp):
        """_on_control_error 恢复按钮状态并显示错误。"""
        window = _make_window(qapp)
        window._run_btn.setEnabled(False)
        window._run_btn.setText("运行中...")
        window._on_control_error("[KERNEL_NOT_FOUND] 内核缺失")
        assert window._run_btn.isEnabled()
        assert window._run_btn.text() == "运行"
        assert "轨道保持失败" in window._status_bar.currentMessage()
