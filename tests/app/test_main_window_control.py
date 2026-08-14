"""tests for MainWindow control_orbit dispatch + handlers (issue #348)。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from e2m2e.data.templates.seed import EARTH_MOON_MU

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


def _make_orbit_artifact(
    window,
    *,
    with_ephemeris: bool = True,
    mu: float | None = 0.0123,
    orbit_type: str = "DRO",
):
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
        orbit_type=orbit_type,
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

    def test_control_orbit_hidden_mu_field(self, qapp):
        """control_orbit 不应在 UI 暴露 mu（由源 Artifact 注入，面板编辑无效）。

        ControlOrbitRequest.mu 是响应透传字段，e2m2e control_orbit 函数签名
        无 mu；此前面板收集到 mu 后透传，轨道保持直接 TypeError。
        """
        window = _make_window(qapp)
        _select_control_tool(window)
        assert "mu" not in window._param_widgets
    @pytest.mark.parametrize(
        ("orbit_type", "expected_mode"),
        [("Halo", 2), ("NRHO", 2), ("DRO", 1)],
    )
    def test_control_special_mode_matches_selected_orbit_type(
        self, qapp, orbit_type, expected_mode
    ):
        """特征点模式应随选中轨道类型自动设置。"""
        window = _make_window(qapp)
        _make_orbit_artifact(window, orbit_type=orbit_type)
        _select_control_tool(window)
        widget = window._param_widgets["special_mode"]
        assert widget.currentData() == expected_mode
        assert not widget.isEnabled()

    def test_context_control_updates_special_mode(self, qapp):
        """已在轨道保持工具时，右键切换 Halo 也应立即更新模式。"""
        window = _make_window(qapp)
        _select_control_tool(window)
        halo = _make_orbit_artifact(window, orbit_type="Halo")

        window._trigger_control_orbit_from_tree([halo.artifact_id])

        assert window._selected_artifact_ids == [halo.artifact_id]
        assert window._param_widgets["special_mode"].currentData() == 2

    def test_artifact_click_updates_control_special_mode(self, qapp):
        """控制面板已打开时，单击 Halo 应立即更新特征点模式。"""
        window = _make_window(qapp)
        _make_orbit_artifact(window, orbit_type="DRO")
        _select_control_tool(window)
        halo = _make_orbit_artifact(window, orbit_type="Halo")

        window._on_artifact_clicked(halo.artifact_id)

        assert window._param_widgets["special_mode"].currentData() == 2


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
        _make_orbit_artifact(window, with_ephemeris=True, mu=EARTH_MOON_MU)

        with patch("src.app.main_window.ControlOrbitWorker") as mock_cls:
            window._on_run()
            _, kwargs = mock_cls.call_args
            assert kwargs["source_mu"] == pytest.approx(EARTH_MOON_MU)

    def test_run_control_params_exclude_mu(self, qapp):
        """传给 ControlOrbitWorker 的 params 不应含 mu（否则透传给 e2m2e 报 TypeError）。

        回归：面板曾按 ControlOrbitRequest 字段收集 mu 进 params，facade 用
        **params 展开调用 control_orbit()，函数签名无 mu →
        "control_orbit() got an unexpected keyword argument 'mu'"。
        """
        window = _make_window(qapp)
        _select_control_tool(window)
        _make_orbit_artifact(window, with_ephemeris=True, mu=EARTH_MOON_MU)

        with patch("src.app.main_window.ControlOrbitWorker") as mock_cls:
            window._on_run()
            _, kwargs = mock_cls.call_args
            assert "mu" not in kwargs["params"]

    def test_run_control_blocks_when_sim_exceeds_ephemeris(self, qapp):
        """仿真总时长超出源星历覆盖时应拦截并提示，不启动 worker。

        回归：用户指定上游的多年仿真参数（30 天/次、28 天反馈弧）时，
        30 天 Halo 星历的控制律目标点会全部超出标称轨道，5 个
        蒙特卡洛样本必然全部失败（Δv=0、无机动）。
        """
        window = _make_window(qapp)
        _select_control_tool(window)
        artifact = _make_orbit_artifact(window, with_ephemeris=True, mu=EARTH_MOON_MU)
        # 给星历注入真实时间轴：30 天覆盖
        n = 721
        et = np.linspace(7.5e8, 7.5e8 + 30 * 86400, n)
        artifact.extra["ephemeris"]["times_et"] = et
        window._param_widgets["control_interval"].setValue(30.0)
        window._param_widgets["feedback_arc"].setValue(28.0)

        with patch("src.app.main_window.ControlOrbitWorker") as mock_cls:
            window._on_run()
            mock_cls.assert_not_called()
        log_text = window._log.toPlainText()
        assert "超出" in log_text and "控制间隔" in log_text

    def test_run_control_defaults_support_short_ephemeris(self, qapp):
        """GUI 短弧默认值应让 30 天标称星历直接启动控制仿真。"""
        window = _make_window(qapp)
        _select_control_tool(window)
        artifact = _make_orbit_artifact(window, with_ephemeris=True, mu=EARTH_MOON_MU)
        n = 721
        et = np.linspace(7.5e8, 7.5e8 + 30 * 86400, n)
        artifact.extra["ephemeris"]["times_et"] = et

        with patch("src.app.main_window.ControlOrbitWorker") as mock_cls:
            window._on_run()
            mock_cls.assert_called_once()
            _, kwargs = mock_cls.call_args
            assert kwargs["params"]["control_interval"] == pytest.approx(0.25)
            assert kwargs["params"]["feedback_arc"] == pytest.approx(0.125)


class TestStopRun:
    def test_stop_run_requests_worker_interruption(self, qapp):
        """停止按钮应请求当前 worker 中断，并切换为停止中状态。"""
        window = _make_window(qapp)
        worker = MagicMock()
        worker.isRunning.return_value = True
        window._worker = worker
        window._run_btn.setEnabled(False)
        window._run_btn.setText("运行中...")
        window._stop_btn.setEnabled(True)

        window._on_stop_run()

        worker.requestInterruption.assert_called_once()
        assert window._run_btn.text() == "停止中..."
        assert not window._stop_btn.isEnabled()

    def test_stop_after_worker_exit_drops_pending_control_result(self, qapp):
        """worker 已退出、完成信号待处理时，停止仍应拦截结果。"""
        window = _make_window(qapp)
        worker = MagicMock()
        worker.isRunning.return_value = False
        window._worker = worker
        window._run_btn.setEnabled(False)
        window._run_btn.setText("运行中...")
        window._stop_btn.setEnabled(True)

        result = ControlResultData(
            num_failed=1,
            sk_statistic_rows=np.empty((0, 3)),
            maneuvers_mjd_tdb=np.array([]),
            maneuvers_delta_v_mps=np.array([]),
            controlled_states=None,
            controlled_times=None,
        )
        window._on_stop_run()
        with patch("src.app.main_window.save_control_result") as mock_save:
            window._on_control_finished(result)

        worker.requestInterruption.assert_called_once()
        mock_save.assert_not_called()
        assert "运行已停止" in window._status_bar.currentMessage()

    def test_stability_does_not_overwrite_active_worker(self, qapp):
        """已有任务运行时，右键稳定性分析不得覆盖当前 worker。"""
        window = _make_window(qapp)
        artifact = _make_orbit_artifact(window, with_ephemeris=False)
        active_worker = MagicMock()
        active_worker.isRunning.return_value = True
        window._worker = active_worker
        window._stop_btn.setEnabled(True)

        with patch("src.app.main_window.StabilityWorker") as stability_cls:
            window._trigger_stability_from_tree([artifact.artifact_id])

        stability_cls.assert_not_called()
        assert window._worker is active_worker
        assert "已有任务运行" in window._status_bar.currentMessage()


class TestControlWorkerCancellation:
    def test_cancelled_control_worker_drops_completed_result(self, qapp):
        """运行中请求停止后，算法返回只发取消信号、不发完成信号。"""
        from threading import Event

        from src.engine.workers import ControlOrbitWorker

        entered = Event()
        release = Event()
        worker = ControlOrbitWorker({}, {}, None)
        cancelled: list[bool] = []
        finished: list[object] = []
        worker.cancelled.connect(lambda: cancelled.append(True))
        worker.finished.connect(finished.append)

        def control_orbit(*_args, **_kwargs):
            entered.set()
            assert release.wait(timeout=1)
            return MagicMock()

        with patch("src.engine.workers.FacadeBridge") as bridge_cls:
            bridge_cls.return_value.control_orbit.side_effect = control_orbit
            worker.start()
            assert entered.wait(timeout=1)
            worker.requestInterruption()
            release.set()
            assert worker.wait(1000)

        qapp.processEvents()
        assert cancelled == [True]
        assert finished == []


class TestOnControlFinished:
    def _make_result(self, n: int = 30) -> ControlResultData:
        return ControlResultData(
            num_failed=1,
            sk_statistic_rows=np.array([[1.0, 2.0, 3.0]]),
            maneuvers_mjd_tdb=np.array([60000.0, 60030.0]),
            maneuvers_delta_v_mps=np.array([0.5, 0.3]),
            controlled_states=np.random.randn(n, 6),
            controlled_times=np.arange(n),
            mu=EARTH_MOON_MU,
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

    def test_on_control_finished_after_stop_drops_result(self, qapp):
        """停止请求先到达时，迟到的完成信号不得落盘或注册结果。"""
        window = _make_window(qapp)
        window._stop_requested = True

        with patch("src.app.main_window.save_control_result") as mock_save:
            window._on_control_finished(self._make_result())

        mock_save.assert_not_called()
        assert not [a for a in window._project.artifacts if a.artifact_type == "ephemeris"]
        assert "运行已停止" in window._status_bar.currentMessage()

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
            mu=EARTH_MOON_MU,
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
        """_artifact_for_id 应把 extra 里的 position_km/times_et 透传给画布接口。

        #359 新契约：control_orbit Artifact 的 state_data 作为 ephemeris_synodic
        暴露（已 μ-shift），position_km/times_et 走 ephemeris_position_km/
        ephemeris_times_et 槽；initial_guess_states 为 None（无 CR3BP 初猜）。
        """
        from src.model import Artifact

        window = _make_window(qapp)
        position_km = np.random.randn(5, 3)
        times_et = np.linspace(7.5e8, 7.6e8, 5)
        a = Artifact(
            artifact_type="ephemeris",
            label="受控星历",
            source_tool="control_orbit",
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
        np.testing.assert_array_equal(result["ephemeris_position_km"], position_km)
        np.testing.assert_array_equal(result["ephemeris_times_et"], times_et)
        # state_data 作为 ephemeris_synodic 槽
        np.testing.assert_array_equal(result["ephemeris_synodic"], a.state_data)
        # control_orbit 无 CR3BP 初猜
        assert result["initial_guess_states"] is None

    def test_artifact_for_id_returns_none_for_missing_position_and_times_et(self, qapp):
        """旧 Artifact extra 无 position_km/times_et 时，对应槽显式为 None。

        #359 新契约：control_orbit 类 Artifact 缺星历字段时，所有 ephemeris_* 槽
        为 None；非顶层 fallback / 不嵌套 extra["ephemeris"]。
        """
        from src.model import Artifact

        window = _make_window(qapp)
        a = Artifact(
            artifact_type="orbit",
            label="旧轨道",
            source_tool="control_orbit",  # 走 ephemeris_synodic 槽分支
            state_data=np.random.randn(5, 6),
            extra={"mu": 0.0123},
        )
        window._project.add(a)

        result = window._artifact_for_id(a.artifact_id)
        assert result is not None
        # 显式 None：不靠隐式 fallback，画布按 plot_content 消费时缺数据明确降级
        assert result["ephemeris_position_km"] is None
        assert result["ephemeris_times_et"] is None
        # state_data 仍作为 ephemeris_synodic 可达（control_orbit 槽约定）
        assert result["ephemeris_synodic"] is not None
        # control_orbit 无初猜
        assert result["initial_guess_states"] is None

    def test_artifact_for_id_design_orbit_exposes_both_tracks(self, qapp):
        """#359：design_orbit 产物显式暴露 CR3BP 初猜 + 标称星历两份轨迹。

        回归 guard：初猜走 initial_guess_states；标称星历的会合系位置送画布前
        减 μ（ADR 0013 质心归一），ephemeris_position_km / ephemeris_times_et
        来自 extra["ephemeris"]，不嵌套、不靠 fallback。
        """
        from src.model import Artifact

        window = _make_window(qapp)
        mu = 0.0123
        n = 8
        synodic_position = np.random.randn(n, 3) + 1.0  # 量级 ~1（地心归一）
        position_km = np.random.randn(n, 3) * 1e5
        times_et = np.linspace(7.5e8, 7.6e8, n)
        cr3bp_states = np.random.randn(20, 6)
        a = Artifact(
            artifact_type="orbit",
            label="DRO 设计",
            source_tool="design_orbit",
            state_data=cr3bp_states,
            times=np.linspace(0, 1, 20),
            extra={
                "mu": mu,
                "ephemeris": {
                    "synodic_position": synodic_position,
                    "position_km": position_km,
                    "times_et": times_et,
                },
            },
        )
        window._project.add(a)

        result = window._artifact_for_id(a.artifact_id)
        assert result is not None
        # 初猜
        np.testing.assert_array_equal(result["initial_guess_states"], cr3bp_states)
        # 星历会合系：减 μ（质心归一，ADR 0013）
        np.testing.assert_allclose(
            result["ephemeris_synodic"], synodic_position - mu, rtol=0, atol=1e-12
        )
        # 星历惯性系 + 时间轴
        np.testing.assert_array_equal(result["ephemeris_position_km"], position_km)
        np.testing.assert_array_equal(result["ephemeris_times_et"], times_et)

    def test_artifact_for_id_design_orbit_without_ephemeris_only_initial_guess(
        self, qapp
    ):
        """design_orbit 产物缺 ephemeris（理论上不会）时，星历槽为 None。"""
        from src.model import Artifact

        window = _make_window(qapp)
        a = Artifact(
            artifact_type="orbit",
            label="仅 CR3BP",
            source_tool="design_orbit",
            state_data=np.random.randn(10, 6),
            extra={"mu": 0.0123},
        )
        window._project.add(a)

        result = window._artifact_for_id(a.artifact_id)
        assert result is not None
        assert result["initial_guess_states"] is not None
        assert result["ephemeris_synodic"] is None
        assert result["ephemeris_position_km"] is None
        assert result["ephemeris_times_et"] is None


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
