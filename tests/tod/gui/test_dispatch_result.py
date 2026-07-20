"""JobFinishResult frozen dataclass + fakes 模块的单测。

覆盖范围：
- JobFinishResult 冻结属性（不可变契约）
- 五种 JobStatus 的构造
- None exit_code 场景（启动失败、并发上限错误）
- error_message 字段行为
- 从 fakes 模块构造结果的工厂函数
- FakeJob 轻量替身
"""

import pytest

from tod.gui.jobs.job_status import JobFinishResult, JobStatus
from tests.tod.gui.fakes import FAKE_SCRIPT_NAME, FakeJob, make_fake_job, make_result


class TestJobFinishResultFrozen:
    """JobFinishResult 是 frozen dataclass，字段不可写。"""

    def test_frozen_rejects_field_assignment(self):
        result = make_result()
        with pytest.raises(AttributeError):
            result.job_id = "changed"  # type: ignore[misc]

    def test_frozen_rejects_status_mutation(self):
        result = make_result()
        with pytest.raises(AttributeError):
            result.status = JobStatus.FAILURE  # type: ignore[misc]

    def test_frozen_rejects_exit_code_mutation(self):
        result = make_result()
        with pytest.raises(AttributeError):
            result.exit_code = 99  # type: ignore[misc]

    def test_frozen_rejects_error_message_mutation(self):
        result = make_result()
        with pytest.raises(AttributeError):
            result.error_message = "mutated"  # type: ignore[misc]

    def test_frozen_rejects_script_name_mutation(self):
        result = make_result()
        with pytest.raises(AttributeError):
            result.script_name = "changed"  # type: ignore[misc]


class TestJobFinishResultFields:
    """字段类型和值语义。"""

    def test_has_five_fields(self):
        result = make_result()
        assert hasattr(result, "job_id")
        assert hasattr(result, "status")
        assert hasattr(result, "exit_code")
        assert hasattr(result, "error_message")
        assert hasattr(result, "script_name")

    def test_default_success_result(self):
        result = make_result()
        assert result.job_id == "j1"
        assert result.status == JobStatus.SUCCESS
        assert result.exit_code == 0
        assert result.error_message == ""
        assert result.script_name == FAKE_SCRIPT_NAME

    def test_custom_job_id(self):
        result = make_result(job_id="abc123")
        assert result.job_id == "abc123"

    def test_custom_script_name(self):
        result = make_result(script_name="my_script")
        assert result.script_name == "my_script"


class TestJobFinishResultEquality:
    """frozen dataclass 自动生成 __eq__，相同字段值应相等。"""

    def test_identical_results_are_equal(self):
        r1 = make_result()
        r2 = make_result()
        assert r1 == r2

    def test_different_job_ids_are_not_equal(self):
        r1 = make_result(job_id="a")
        r2 = make_result(job_id="b")
        assert r1 != r2

    def test_different_status_are_not_equal(self):
        r1 = make_result(status=JobStatus.SUCCESS)
        r2 = make_result(status=JobStatus.FAILURE)
        assert r1 != r2

    def test_different_exit_codes_are_not_equal(self):
        r1 = make_result(exit_code=0)
        r2 = make_result(exit_code=1)
        assert r1 != r2

    def test_different_error_messages_are_not_equal(self):
        r1 = make_result(error_message="")
        r2 = make_result(error_message="boom")
        assert r1 != r2


class TestJobFinishResultStatusVariants:
    """构造所有五种终态的 JobFinishResult。"""

    def test_success(self):
        result = make_result(status=JobStatus.SUCCESS, exit_code=0)
        assert result.status == JobStatus.SUCCESS
        assert result.status.is_terminal

    def test_failure(self):
        result = make_result(status=JobStatus.FAILURE, exit_code=1)
        assert result.status == JobStatus.FAILURE
        assert result.status.is_terminal

    def test_stopped(self):
        result = make_result(status=JobStatus.STOPPED, exit_code=-15)
        assert result.status == JobStatus.STOPPED
        assert result.status.is_terminal

    def test_pending(self):
        result = make_result(status=JobStatus.PENDING, exit_code=None)
        assert result.status == JobStatus.PENDING
        assert result.status.is_active

    def test_running(self):
        result = make_result(status=JobStatus.RUNNING, exit_code=None)
        assert result.status == JobStatus.RUNNING
        assert result.status.is_active


class TestJobFinishResultNoneExitCode:
    """exit_code 为 None 的场景（启动失败、并发上限）。"""

    def test_none_exit_code_with_failure(self):
        result = make_result(
            status=JobStatus.FAILURE,
            exit_code=None,
            error_message="脚本启动失败: test_script",
        )
        assert result.exit_code is None
        assert result.status == JobStatus.FAILURE

    def test_none_exit_code_with_empty_job_id(self):
        """并发上限错误：job_id 为空，exit_code 为 None。"""
        result = make_result(
            job_id="",
            status=JobStatus.FAILURE,
            exit_code=None,
            error_message="同时运行的任务数已达上限 (8)",
        )
        assert result.job_id == ""
        assert result.exit_code is None

    def test_none_exit_code_with_running(self):
        result = make_result(status=JobStatus.RUNNING, exit_code=None)
        assert result.exit_code is None


class TestJobFinishResultErrorMessage:
    """error_message 字段在不同场景下的行为。"""

    def test_success_has_empty_error_message(self):
        result = make_result(status=JobStatus.SUCCESS)
        assert result.error_message == ""

    def test_failure_with_detail_message(self):
        msg = "进程错误 (test_script): Crashed"
        result = make_result(status=JobStatus.FAILURE, error_message=msg)
        assert result.error_message == msg

    def test_failure_with_startup_message(self):
        msg = "脚本启动失败: test_script\nPython 解释器未找到"
        result = make_result(status=JobStatus.FAILURE, error_message=msg)
        assert "启动失败" in result.error_message


class TestMakeResultFromFakes:
    """fakes.make_result 工厂函数的契约。"""

    def test_returns_dispatch_result(self):
        result = make_result()
        assert isinstance(result, JobFinishResult)

    def test_frozen(self):
        result = make_result()
        with pytest.raises(AttributeError):
            result.job_id = "x"  # type: ignore[misc]

    def test_kwargs_override_all_fields(self):
        result = make_result(
            job_id="jid",
            status=JobStatus.STOPPED,
            exit_code=-9,
            error_message="stopped by user",
            script_name="custom",
        )
        assert result.job_id == "jid"
        assert result.status == JobStatus.STOPPED
        assert result.exit_code == -9
        assert result.error_message == "stopped by user"
        assert result.script_name == "custom"


class TestFakeJob:
    """FakeJob 轻量替身的契约。"""

    def test_default_values(self):
        job = make_fake_job()
        assert job.job_id == "j1"
        assert job.script_name == FAKE_SCRIPT_NAME
        assert job.status == JobStatus.RUNNING
        assert job.exit_code is None

    def test_custom_values(self):
        job = make_fake_job(
            job_id="abc",
            script_name="my_script",
            status=JobStatus.STOPPED,
            exit_code=-15,
        )
        assert job.job_id == "abc"
        assert job.script_name == "my_script"
        assert job.status == JobStatus.STOPPED
        assert job.exit_code == -15

    def test_script_entry_exposes_name(self):
        job = make_fake_job(script_name="test_name")
        assert job.script_entry.name == "test_name"

    def test_status_mutable(self):
        """FakeJob 是普通对象，status 可变（与 frozen JobFinishResult 对比）。"""
        job = make_fake_job()
        job.status = JobStatus.SUCCESS
        assert job.status == JobStatus.SUCCESS

    def test_fake_script_entry_has_name_only(self):
        """FakeScriptEntry 仅暴露 name，不触发 ScriptEntry 完整扫描。"""
        job = make_fake_job()
        assert hasattr(job.script_entry, "name")
        assert isinstance(job.script_entry.name, str)


class TestFakeScriptNameConstant:
    """FAKE_SCRIPT_NAME 常量。"""

    def test_is_nonempty_string(self):
        assert FAKE_SCRIPT_NAME
        assert isinstance(FAKE_SCRIPT_NAME, str)

    def test_used_as_default_in_make_result(self):
        result = make_result()
        assert result.script_name == FAKE_SCRIPT_NAME

    def test_used_as_default_in_make_fake_job(self):
        job = make_fake_job()
        assert job.script_name == FAKE_SCRIPT_NAME
