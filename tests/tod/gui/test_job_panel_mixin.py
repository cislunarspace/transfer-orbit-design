"""job_panel_mixin — Job 面板 Mixin 的接口与行为测试。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QStatusBar, QTabWidget

from tod.gui.job_panel_mixin import JobPanelMixin
from tod.gui.job_status import JobFinishResult, JobStatus
from tod.gui.output_panel import JobCard, StructuredOutputWidget


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

    class _StubMixin(JobPanelMixin):
        """继承 JobPanelMixin，绕过 QObject 多继承限制。"""

        def __init__(self):
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

    mixin = _StubMixin()
    return mixin, {
        "status_bar": mixin._status_bar,
        "job_outputs": mixin._job_outputs,
        "job_cards": mixin._job_cards,
        "job_manager": mixin._job_manager,
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
