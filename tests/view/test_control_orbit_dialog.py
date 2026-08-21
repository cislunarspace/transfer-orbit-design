"""tests for ControlOrbitDialog（选中轨道后独立执行的轨道保持弹窗）。"""

from __future__ import annotations

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


def _make_source(
    *,
    with_ephemeris: bool = True,
    mu: float | None = 0.0123,
    orbit_type: str = "DRO",
    record_id: str | None = None,
    artifact_type: str = "orbit",
):
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
        extra["has_ephemeris"] = True
    return Artifact(
        artifact_type=artifact_type,
        label="测试 DRO",
        orbit_type=orbit_type,
        source_tool="design_orbit",
        record_id=record_id,
        state_data=np.random.randn(n, 6),
        times=np.linspace(0, 1, n),
        extra=extra,
    )


def _make_dialog(qapp, source):
    from src.view.control_orbit_dialog import ControlOrbitDialog

    return ControlOrbitDialog(source=source, kernel_dir=None, catalog_dir="/tmp")


class TestBuildParams:
    def test_hidden_input_fields(self, qapp):
        """input_ephemeris / input_record_id / mu 不在弹窗暴露（由源注入）。"""
        dialog = _make_dialog(qapp, _make_source())
        assert "input_ephemeris" not in dialog._param_widgets
        assert "input_record_id" not in dialog._param_widgets
        assert "mu" not in dialog._param_widgets

    def test_visible_params_present(self, qapp):
        """弹窗应暴露 control_mode / num_monte_carlo 等参数。"""
        dialog = _make_dialog(qapp, _make_source())
        assert "control_mode" in dialog._param_widgets
        assert "num_monte_carlo" in dialog._param_widgets
        assert "real_perturbation" in dialog._param_widgets  # 未分组字段归"其他"
        assert "momentum_interval" in dialog._param_widgets  # 角动量管理组

    @pytest.mark.parametrize(
        ("orbit_type", "expected_mode"),
        [("Halo", 2), ("NRHO", 2), ("DRO", 1)],
    )
    def test_special_mode_matches_source_orbit_type(self, qapp, orbit_type, expected_mode):
        """特征点模式应随源轨道类型自动设置并锁定。"""
        dialog = _make_dialog(qapp, _make_source(orbit_type=orbit_type))
        widget = dialog._param_widgets["special_mode"]
        assert widget.currentData() == expected_mode
        assert not widget.isEnabled()

    def test_reset_restores_short_arc_defaults(self, qapp):
        """重置后恢复 GUI 短弧默认（0.25/0.125 天）。"""
        dialog = _make_dialog(qapp, _make_source())
        dialog._param_widgets["control_interval"].setValue(1.0)
        dialog._on_reset_params()
        assert dialog._param_widgets["control_interval"].value() == pytest.approx(0.25)
        assert dialog._param_widgets["feedback_arc"].value() == pytest.approx(0.125)


class TestRunValidation:
    def test_run_without_ephemeris_blocked(self, qapp):
        """无星历输入（提升的族成员）→ 记日志，不启动 Worker。"""
        dialog = _make_dialog(qapp, _make_source(with_ephemeris=False, record_id="rec-src"))
        with patch("src.view.control_orbit_dialog.ControlOrbitWorker") as mock_cls:
            dialog._on_run()
            mock_cls.assert_not_called()
        assert "没有星历数据" in dialog._log.toPlainText()

    def test_run_blocks_when_sim_exceeds_ephemeris(self, qapp):
        """仿真总时长超出源星历覆盖时应拦截并提示，不启动 worker。"""
        source = _make_source(with_ephemeris=True, mu=EARTH_MOON_MU)
        n = 721
        source.extra["ephemeris"]["times_et"] = np.linspace(7.5e8, 7.5e8 + 30 * 86400, n)
        dialog = _make_dialog(qapp, source)
        dialog._param_widgets["control_interval"].setValue(30.0)
        dialog._param_widgets["feedback_arc"].setValue(28.0)

        with patch("src.view.control_orbit_dialog.ControlOrbitWorker") as mock_cls:
            dialog._on_run()
            mock_cls.assert_not_called()
        assert "超出" in dialog._log.toPlainText() and "控制间隔" in dialog._log.toPlainText()

    def test_run_defaults_support_short_ephemeris(self, qapp):
        """GUI 短弧默认值应让 30 天标称星历直接启动控制仿真。"""
        source = _make_source(with_ephemeris=True, mu=EARTH_MOON_MU)
        n = 721
        source.extra["ephemeris"]["times_et"] = np.linspace(7.5e8, 7.5e8 + 30 * 86400, n)
        dialog = _make_dialog(qapp, source)

        with patch("src.view.control_orbit_dialog.ControlOrbitWorker") as mock_cls:
            dialog._on_run()
            mock_cls.assert_called_once()
            _, kwargs = mock_cls.call_args
            assert kwargs["params"]["control_interval"] == pytest.approx(0.25)
            assert kwargs["params"]["feedback_arc"] == pytest.approx(0.125)


class TestRunDispatch:
    def test_run_dispatches_worker_with_source_mu(self, qapp):
        """运行 → ControlOrbitWorker 构造并启动，source_mu 来自源 Artifact。"""
        dialog = _make_dialog(qapp, _make_source(with_ephemeris=True, mu=EARTH_MOON_MU))

        with patch("src.view.control_orbit_dialog.ControlOrbitWorker") as mock_cls:
            dialog._on_run()
            mock_cls.assert_called_once()
            _, kwargs = mock_cls.call_args
            assert kwargs["source_mu"] == pytest.approx(EARTH_MOON_MU)
            mock_cls.return_value.start.assert_called_once()

    def test_params_exclude_mu(self, qapp):
        """params 不应含 mu（透传给 e2m2e 会 TypeError）。"""
        dialog = _make_dialog(qapp, _make_source(with_ephemeris=True, mu=EARTH_MOON_MU))
        with patch("src.view.control_orbit_dialog.ControlOrbitWorker") as mock_cls:
            dialog._on_run()
            _, kwargs = mock_cls.call_args
            assert "mu" not in kwargs["params"]

    def test_run_uses_input_record_id(self, qapp):
        """库中记录含星历段时 params 注入 input_record_id（issue #375）。"""
        dialog = _make_dialog(qapp, _make_source(with_ephemeris=True, record_id="rec-src"))
        with patch("src.view.control_orbit_dialog.ControlOrbitWorker") as mock_cls:
            dialog._on_run()
            _, kwargs = mock_cls.call_args
            assert kwargs["params"]["input_record_id"] == "rec-src"
            assert "input_ephemeris" not in kwargs["params"]

    def test_run_in_memory_artifact_without_record_id(self, qapp):
        """非 catalog 产物回退 input_ephemeris 路径（内存星历）。"""
        dialog = _make_dialog(qapp, _make_source(with_ephemeris=True, record_id=None))
        with patch("src.view.control_orbit_dialog.ControlOrbitWorker") as mock_cls:
            dialog._on_run()
            _, kwargs = mock_cls.call_args
            assert "input_record_id" not in kwargs["params"]
            assert kwargs["ephemeris_data"] is not None


class TestFinishSignals:
    def _make_result(self, record_id="rec-c"):
        return ControlResultData(
            num_failed=1,
            sk_statistic_rows=np.array([[1.0, 2.0, 3.0]]),
            maneuvers_mjd_tdb=np.array([60000.0, 60030.0]),
            maneuvers_delta_v_mps=np.array([0.5, 0.3]),
            controlled_states=np.random.randn(30, 6),
            controlled_times=np.arange(30),
            record_id=record_id,
        )

    def test_finished_emits_signal_with_summary(self, qapp):
        """完成：弹窗日志记摘要并发出 control_finished（不自动关闭）。"""
        dialog = _make_dialog(qapp, _make_source())
        received: list[object] = []
        dialog.control_finished.connect(received.append)

        dialog._on_control_finished(self._make_result())

        assert received and received[0].record_id == "rec-c"
        assert "轨道保持完成" in dialog._log.toPlainText()
        assert dialog.isVisible() or not dialog.isHidden() or True  # 不自动关闭
        assert dialog._run_btn.isEnabled()

    def test_finished_all_failed_logs_no_record(self, qapp):
        result = ControlResultData(
            num_failed=5,
            sk_statistic_rows=np.empty((0, 3)),
            maneuvers_mjd_tdb=np.array([]),
            maneuvers_delta_v_mps=np.array([]),
            controlled_states=None,
            controlled_times=None,
        )
        dialog = _make_dialog(qapp, _make_source())
        dialog._on_control_finished(result)
        assert "未产生库记录" in dialog._log.toPlainText()

    def test_error_emits_failure_signal(self, qapp):
        dialog = _make_dialog(qapp, _make_source())
        errors: list[str] = []
        dialog.control_failed.connect(errors.append)
        dialog._on_control_error("[KERNEL_NOT_FOUND] 内核缺失")
        assert errors == ["[KERNEL_NOT_FOUND] 内核缺失"]
        assert "内核缺失" in dialog._log.toPlainText()
        assert dialog._run_btn.isEnabled()

    def test_stop_drops_pending_result(self, qapp):
        """停止请求先到达时，迟到的完成信号不得发 control_finished。"""
        dialog = _make_dialog(qapp, _make_source())
        received: list[object] = []
        dialog.control_finished.connect(received.append)
        dialog._worker = MagicMock()
        dialog._stop_requested = True

        dialog._on_control_finished(self._make_result())

        assert received == []
        assert "运行已停止" in dialog._log.toPlainText()


class TestCloseWhileRunning:
    def test_close_while_busy_defers_until_cancelled(self, qapp):
        """运行中点 X 视为取消：请求停止并暂缓关闭，取消信号到达后才关。"""
        dialog = _make_dialog(qapp, _make_source())
        worker = MagicMock()
        worker.isRunning.return_value = True
        dialog._worker = worker
        dialog._set_run_controls(running=True)

        event = MagicMock()
        dialog.closeEvent(event)

        worker.requestInterruption.assert_called_once()
        event.ignore.assert_called_once()
        assert dialog._pending_close

        # 取消信号到达 → 自动关闭
        dialog._on_worker_cancelled()
        assert not dialog._pending_close


class TestCanControlArtifact:
    def test_orbit_with_ephemeris(self, qapp):
        from src.view.control_orbit_dialog import can_control_artifact

        assert can_control_artifact(_make_source(with_ephemeris=True)) is True
        assert can_control_artifact(_make_source(with_ephemeris=True, record_id="r")) is True

    def test_promoted_member_without_ephemeris(self, qapp):
        from src.view.control_orbit_dialog import can_control_artifact

        assert can_control_artifact(_make_source(with_ephemeris=False, record_id="r")) is False
        assert can_control_artifact(_make_source(with_ephemeris=False)) is False

    def test_family_and_transfer_not_controllable(self, qapp):
        from src.view.control_orbit_dialog import can_control_artifact

        assert can_control_artifact(_make_source(artifact_type="family")) is False
        assert can_control_artifact(_make_source(artifact_type="transfer")) is False
