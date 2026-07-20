"""job_panel_mixin — Job 面板 Mixin 的接口与行为测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from unittest.mock import MagicMock

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QStatusBar, QTabWidget, QWidget

from tod.gui.jobs.job_panel_mixin import JobPanelMixin
from tod.gui.jobs.job_status import JobFinishResult, JobStatus
from tod.gui.jobs.output_panel import JobCard, StructuredOutputWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestJobPanelMixinImportable:
    def test_mixin_importable(self):
        assert JobPanelMixin is not None

    def test_mixin_has_required_methods(self):
        methods = [
            "_build_job_panel",
            "_on_job_started",
            "_on_job_output",
            "_on_job_finished",
            "_on_job_error",
            "_on_job_card_clicked",
            "_on_stop_current",
            "_on_stop_job_requested",
            "_confirm_and_stop",
            "_on_output_tab_close",
            "_clear_completed_jobs",
            "_update_job_count",
        ]
        for name in methods:
            assert hasattr(JobPanelMixin, name), f"JobPanelMixin missing method: {name}"


class TestMainWindowInheritsJobPanelMixin:
    def test_main_window_inherits_job_panel_mixin(self):
        from tod.gui.main_window import MainWindow
        assert issubclass(MainWindow, JobPanelMixin)


def _make_mixin(qapp) -> tuple[JobPanelMixin, dict]:
    """构造最小可用 JobPanelMixin 实例，注入所有必需的 stub 属性。"""

    class _StubMixin(QObject, JobPanelMixin):
        """继承 JobPanelMixin + QObject，支持 pyqtSignal.emit()。"""

        def __init__(self):
            super().__init__()
            self._status_bar = MagicMock(spec=QStatusBar)
            self._job_outputs: dict[str, StructuredOutputWidget] = {}
            self._job_cards: dict[str, JobCard] = {}
            self._job_manager = MagicMock()
            self._has_jobs = False
            self._current_script = None
            self._run_btn = MagicMock(spec=QPushButton)
            self._job_count_label = MagicMock(spec=QLabel)
            self._output_tabs = MagicMock(spec=QTabWidget)
            self._clear_completed_btn = MagicMock()
            # 批量运行 stub
            self._batch_manager = MagicMock()
            self._batch_cards: dict[str, MagicMock] = {}
            self._batches_container = MagicMock(spec=QWidget)

    mixin = _StubMixin()
    return mixin, {
        "status_bar": mixin._status_bar,
        "job_outputs": mixin._job_outputs,
        "job_cards": mixin._job_cards,
        "job_manager": mixin._job_manager,
        "batch_manager": mixin._batch_manager,
        "batch_cards": mixin._batch_cards,
        "batches_container": mixin._batches_container,
    }


def _make_result(
    job_id: str = "j1",
    status: JobStatus = JobStatus.SUCCESS,
    exit_code: int | None = 0,
    error_message: str = "",
    script_name: str = "test_script",
) -> JobFinishResult:
    return JobFinishResult(
        job_id=job_id,
        status=status,
        exit_code=exit_code,
        error_message=error_message,
        script_name=script_name,
    )


class TestOnJobFinishedWithJobFinishResult:
    """_on_job_finished 直接使用 JobFinishResult.status，不再回调 get_job。"""

    def test_success_status_sets_card_status(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        card = MagicMock(spec=JobCard)
        ctx["job_cards"]["j1"] = card
        output = MagicMock(spec=StructuredOutputWidget)
        ctx["job_outputs"]["j1"] = output

        result = _make_result(status=JobStatus.SUCCESS, exit_code=0)
        mixin._on_job_finished(result)

        card.set_status.assert_called_once_with(JobStatus.SUCCESS)

    def test_failure_status_sets_card_status(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        card = MagicMock(spec=JobCard)
        ctx["job_cards"]["j1"] = card
        output = MagicMock(spec=StructuredOutputWidget)
        ctx["job_outputs"]["j1"] = output

        result = _make_result(
            status=JobStatus.FAILURE,
            exit_code=1,
        )
        mixin._on_job_finished(result)

        card.set_status.assert_called_once_with(JobStatus.FAILURE)

    def test_stopped_status_sets_card_status(self, qapp):
        """停止任务通过 JobFinishResult.STOPPED 直接传入，不需再查 JobManager。"""
        mixin, ctx = _make_mixin(qapp)
        card = MagicMock(spec=JobCard)
        ctx["job_cards"]["j1"] = card
        output = MagicMock(spec=StructuredOutputWidget)
        ctx["job_outputs"]["j1"] = output

        result = _make_result(
            status=JobStatus.STOPPED,
            exit_code=-15,
        )
        mixin._on_job_finished(result)

        card.set_status.assert_called_once_with(JobStatus.STOPPED)
        # 未调用 get_job —— 不再回查 JobManager
        ctx["job_manager"].get_job.assert_not_called()

    def test_status_bar_shows_exit_code(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        ctx["job_cards"]["j1"] = MagicMock(spec=JobCard)
        ctx["job_outputs"]["j1"] = MagicMock(spec=StructuredOutputWidget)

        result = _make_result(
            status=JobStatus.FAILURE,
            exit_code=42,
            script_name="my_script",
        )
        mixin._on_job_finished(result)

        ctx["status_bar"].showMessage.assert_called()
        # _on_job_finished 先调 showMessage（exit code），再调 _update_job_count 也 showMessage
        all_calls = [args[0] for args, _ in ctx["status_bar"].showMessage.call_args_list]
        assert any("42" in msg for msg in all_calls), (
            f"exit code 42 未出现在任何 showMessage 调用中: {all_calls}"
        )


class TestOnJobErrorWithJobFinishResult:
    """_on_job_error 接收 JobFinishResult，status 由 JobManager 构造时确定。"""

    def test_error_sets_card_to_failure(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        card = MagicMock(spec=JobCard)
        ctx["job_cards"]["j1"] = card

        result = _make_result(
            status=JobStatus.FAILURE,
            exit_code=None,
            error_message="脚本启动失败: test_script",
        )
        mixin._on_job_error(result)

        card.set_status.assert_called_once_with(JobStatus.FAILURE)

    def test_global_error_with_empty_job_id_shows_status_bar(self, qapp):
        """全局错误（job_id 为空）只显示状态栏，不操作卡片。"""
        mixin, ctx = _make_mixin(qapp)

        result = _make_result(
            job_id="",
            status=JobStatus.FAILURE,
            exit_code=None,
            error_message="同时运行的任务数已达上限 (8)",
        )
        mixin._on_job_error(result)

        ctx["status_bar"].showMessage.assert_called_once_with(
            "同时运行的任务数已达上限 (8)"
        )

    def test_error_writes_to_output_stderr(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        ctx["job_cards"]["j1"] = MagicMock(spec=JobCard)
        output = MagicMock(spec=StructuredOutputWidget)
        ctx["job_outputs"]["j1"] = output

        result = _make_result(
            status=JobStatus.FAILURE,
            exit_code=None,
            error_message="进程错误 (test_script): Crashed",
        )
        mixin._on_job_error(result)

        output.append_output.assert_called_once()
        call_args = output.append_output.call_args[0]
        assert "[ERROR]" in call_args[0]
        assert call_args[1] == "stderr"


# -- batch signal 槽测试 --


def _make_batch_obj(
    batch_id: str = "batch001",
    script_name: str = "test_script",
    job_ids: tuple[str, ...] = ("j1", "j2"),
) -> MagicMock:
    """构造 MagicMock BatchRun（带 batch_id / script_name / job_ids 属性）。"""
    batch = MagicMock()
    batch.batch_id = batch_id
    batch.script_name = script_name
    batch.job_ids = job_ids
    return batch


def _make_mock_batch_manager(
    batch_id: str = "b1234567",
    script_name: str = "test_script",
    job_ids: tuple[str, ...] = ("j1",),
    status_map: dict[str, JobStatus | None] | None = None,
    aggregate: object | None = None,
) -> MagicMock:
    """构造 MagicMock BatchManager，注入真实的 get_batch / get_aggregate / _get_job_status 行为。

    Args:
        batch_id: batch 唯一标识。
        script_name: 工具显示名。
        job_ids: 子任务 job_id 元组。
        status_map: job_id → JobStatus 映射；未在 map 中的 job 返回 None。
        aggregate: get_aggregate 返回值；默认为非 None 的 MagicMock。
    """
    if status_map is None:
        status_map = {}

    bm = MagicMock()
    batch = _make_batch_obj(
        batch_id=batch_id,
        script_name=script_name,
        job_ids=job_ids,
    )
    bm.get_batch.return_value = batch
    bm.get_aggregate.return_value = aggregate if aggregate is not None else MagicMock()
    bm._get_job_status.side_effect = lambda jid: status_map.get(jid)
    return bm


class TestOnBatchCreated:
    def test_creates_and_inserts_card(self, qapp):
        from tod.gui.batch.batch_summary_card import BatchSummaryCard

        mixin, ctx = _make_mixin(qapp)
        mixin._batch_manager = _make_mock_batch_manager(
            job_ids=("j1", "j2"),
            status_map={"j1": JobStatus.RUNNING, "j2": JobStatus.RUNNING},
        )
        mixin._batch_cards_layout = MagicMock()

        mixin._on_batch_created("b1234567")

        assert "b1234567" in mixin._batch_cards
        assert isinstance(mixin._batch_cards["b1234567"], BatchSummaryCard)
        mixin._batch_cards_layout.insertWidget.assert_called_once()

    def test_shows_batches_container(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        mixin._batch_manager = _make_mock_batch_manager(
            job_ids=("j1",),
            status_map={"j1": JobStatus.RUNNING},
        )
        mixin._batch_cards_layout = MagicMock()

        mixin._on_batch_created("b1234567")

        mixin._batches_container.setVisible.assert_called_with(True)


class TestOnBatchAggregateChanged:
    def test_updates_card_view_model(self, qapp):
        from tod.gui.batch import BatchAggregate
        from tod.gui.batch.batch_summary_card import BatchSummaryCard

        mixin, ctx = _make_mixin(qapp)
        card = MagicMock(spec=BatchSummaryCard)
        mixin._batch_cards["b1234567"] = card

        mixin._batch_manager = _make_mock_batch_manager(
            job_ids=("j1",),
            status_map={"j1": JobStatus.SUCCESS},
            aggregate=BatchAggregate.SUCCESS,
        )

        mixin._on_batch_aggregate_changed("b1234567", BatchAggregate.SUCCESS)

        card.update_view_model.assert_called_once()
        vm = card.update_view_model.call_args[0][0]
        assert vm.aggregate_status == BatchAggregate.SUCCESS

    def test_noop_when_card_missing(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        mixin._on_batch_aggregate_changed("nonexistent", None)


class TestOnBatchRemoved:
    def test_removes_card_and_hides_container_when_empty(self, qapp):
        from tod.gui.batch.batch_summary_card import BatchSummaryCard

        mixin, ctx = _make_mixin(qapp)
        card = MagicMock(spec=BatchSummaryCard)
        mixin._batch_cards["b1234567"] = card
        mixin._batch_cards_layout = MagicMock()

        mixin._on_batch_removed("b1234567")

        assert "b1234567" not in mixin._batch_cards
        mixin._batch_cards_layout.removeWidget.assert_called_once_with(card)
        mixin._batches_container.setVisible.assert_called_with(False)

    def test_noop_when_card_missing(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        mixin._batch_cards_layout = MagicMock()
        mixin._on_batch_removed("nonexistent")


class TestOnBatchJobSelected:
    def test_delegates_to_on_job_card_clicked(self, qapp):
        mixin, ctx = _make_mixin(qapp)
        mixin._on_batch_job_selected("j1")
        # _on_job_card_clicked 是真实方法，不会因 job_id 不存在而报错
        # （_job_outputs.get(job_id) 返回 None 时直接跳过）


# -- 多任务 dispatch 接入测试 --


class TestMainWindowDispatchBatch:
    def test_multi_task_dispatch_creates_batch(self, qapp):
        """多任务 dispatch（>= 2 job）时 batch_manager.create_batch 被调用。"""
        from unittest.mock import patch
        from tod.gui.run.run_orchestrator import DispatchResult, RunOrchestrator
        from tod.gui.main_window import MainWindow

        window = _make_main_window_stub(qapp)
        tab = MagicMock()
        tab.entry.name = "test_script"
        tab.validate_params.return_value = True
        tab.entry.accepts_file_arg = False
        window._script_tab_bar.current_widget.return_value = tab
        window._confirm_run_provider = lambda _plan: True

        plan = MagicMock()
        plan.entry = tab.entry
        plan.specs = (MagicMock(), MagicMock(), MagicMock())

        dispatch_result = DispatchResult(
            created_job_ids=("j1", "j2", "j3"),
            rejected=(),
            total_tasks=3,
            entry=tab.entry,
        )

        with (
            patch.object(RunOrchestrator, 'build_run_plan', return_value=plan),
            patch.object(RunOrchestrator, 'dispatch', return_value=dispatch_result),
        ):
            window._run_from_tab(tab)

        window._batch_manager.create_batch.assert_called_once_with(
            script_name="test_script",
            job_ids=("j1", "j2", "j3"),
        )

    def test_single_task_dispatch_skips_batch(self, qapp):
        """单任务 dispatch（len < 2）时 batch_manager.create_batch 不被调用。"""
        from unittest.mock import patch
        from tod.gui.run.run_orchestrator import DispatchResult, RunOrchestrator
        from tod.gui.main_window import MainWindow

        window = _make_main_window_stub(qapp)
        tab = MagicMock()
        tab.entry.name = "test_script"
        tab.validate_params.return_value = True
        tab.entry.accepts_file_arg = False
        window._script_tab_bar.current_widget.return_value = tab
        window._confirm_run_provider = lambda _plan: True

        plan = MagicMock()
        plan.entry = tab.entry
        plan.specs = (MagicMock(),)

        dispatch_result = DispatchResult(
            created_job_ids=("j1",),
            rejected=(),
            total_tasks=1,
            entry=tab.entry,
        )

        with (
            patch.object(RunOrchestrator, 'build_run_plan', return_value=plan),
            patch.object(RunOrchestrator, 'dispatch', return_value=dispatch_result),
        ):
            window._run_from_tab(tab)

        window._batch_manager.create_batch.assert_not_called()

    def test_cancelled_dispatch_skips_batch(self, qapp):
        """取消运行时不调用 dispatch，不创建 batch。"""
        from unittest.mock import patch
        from tod.gui.run.run_orchestrator import RunOrchestrator
        from tod.gui.main_window import MainWindow

        window = _make_main_window_stub(qapp)
        tab = MagicMock()
        tab.entry.name = "test_script"
        tab.validate_params.return_value = True
        tab.entry.accepts_file_arg = False
        window._script_tab_bar.current_widget.return_value = tab
        window._confirm_run_provider = lambda _plan: False

        with patch.object(RunOrchestrator, 'dispatch') as mock_dispatch:
            window._run_from_tab(tab)
            mock_dispatch.assert_not_called()

        window._batch_manager.create_batch.assert_not_called()


def _make_main_window_stub(qapp) -> MagicMock:
    """构造 MainWindow stub，注入所有依赖。"""
    from tod.gui.main_window import MainWindow

    class _StubMainWindow:
        def __init__(self):
            self._status_bar = MagicMock()
            self._job_manager = MagicMock()
            self._batch_manager = MagicMock()
            self._confirm_run_provider = None
            self._script_tab_bar = MagicMock()
            self._gui_defaults = {"settings": {}}
            self._repo_root = "."
            self.tr = lambda s: s

    stub = _StubMainWindow()
    # 绑定 MainWindow 的实例方法到 stub
    stub._run_from_tab = MainWindow._run_from_tab.__get__(stub)
    stub._confirm_run = MainWindow._confirm_run.__get__(stub)
    return stub
