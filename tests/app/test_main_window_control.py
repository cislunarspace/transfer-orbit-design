"""tests for MainWindow control_orbit dispatch + handlers (issue #348/#375)。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    except ImportError:
        pytest.skip("QApplication 不可用")


class _StubCatalog:
    """CatalogService 桩：清单 / 懒加载 / 写操作全在内存，不触真实库。"""

    def __init__(self) -> None:
        self.artifacts: list = []
        self.records: dict = {}
        self.calls: list = []

    def query_artifacts(self, filters=None):
        self.calls.append(("query", filters))
        return list(self.artifacts)

    def load_arrays(self, artifact):
        stored = self.records.get(artifact.record_id)
        if stored is not None:
            artifact.state_data = stored.state_data
            artifact.times = stored.times
            artifact.extra.update(stored.extra)
        return artifact.state_data is not None or stored is None

    def tag(self, record_id, tags, note=None):
        self.calls.append(("tag", record_id, tags, note))

    def delete(self, record_id):
        self.calls.append(("delete", record_id))

    def promote_member(self, record_id, member_index):
        self.calls.append(("promote", record_id, member_index))
        return "rec-promoted"

    def export(self, filters, dest):
        self.calls.append(("export", filters, dest))
        return 0


def _make_window(qapp, catalog: _StubCatalog | None = None):
    """创建 MainWindow，注入桩 catalog（不扫描 output/ 也不触真实库）。"""
    from src.app.main_window import MainWindow

    stub = catalog if catalog is not None else _StubCatalog()
    with patch("src.app.main_window.discover_artifacts", return_value=[]):
        return MainWindow(catalog=stub)


def _make_orbit_artifact(
    window,
    *,
    with_ephemeris: bool = True,
    mu: float | None = 0.0123,
    orbit_type: str = "DRO",
    record_id: str | None = None,
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
        extra["has_ephemeris"] = True
    artifact = Artifact(
        artifact_type="orbit",
        label="测试 DRO",
        orbit_type=orbit_type,
        source_tool="design_orbit",
        record_id=record_id,
        state_data=np.random.randn(n, 6),
        times=np.linspace(0, 1, n),
        extra=extra,
    )
    if record_id is not None:
        artifact.artifact_id = record_id
    window._project.add(artifact)
    window._selected_artifact_ids = [artifact.artifact_id]
    return artifact


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


