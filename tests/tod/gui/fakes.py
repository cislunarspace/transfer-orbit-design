"""Reusable test doubles for GUI 层测试。

提供可组合的 stub / factory，避免各测试文件重复构造
``JobFinishResult``、``Job`` 等对象的样板代码。

使用示例::

    from tests.tod.gui.fakes import make_result, make_fake_job, FAKE_SCRIPT_NAME

    result = make_result(status=JobStatus.STOPPED, exit_code=-15)
    job = make_fake_job(status=JobStatus.RUNNING)

    # BatchManager 测试：
    from tests.tod.gui.fakes import FakeJobStatusProvider, make_batch_manager

    provider = FakeJobStatusProvider({"j1": JobStatus.SUCCESS, "j2": JobStatus.RUNNING})
    bm = make_batch_manager(provider)
"""

from __future__ import annotations

from tod.gui.jobs.job_status import JobFinishResult, JobStatus

FAKE_SCRIPT_NAME = "test_script"


def make_result(
    *,
    job_id: str = "j1",
    status: JobStatus = JobStatus.SUCCESS,
    exit_code: int | None = 0,
    error_message: str = "",
    script_name: str = FAKE_SCRIPT_NAME,
) -> JobFinishResult:
    """构造 ``JobFinishResult`` 实例，默认为成功终态。

    所有字段均有合理默认值，调用方只需覆盖关心的字段。
    """
    return JobFinishResult(
        job_id=job_id,
        status=status,
        exit_code=exit_code,
        error_message=error_message,
        script_name=script_name,
    )


def make_fake_job(
    *,
    job_id: str = "j1",
    script_name: str = FAKE_SCRIPT_NAME,
    status: JobStatus = JobStatus.RUNNING,
    exit_code: int | None = None,
) -> FakeJob:
    """构造 ``FakeJob`` 实例，用于测试 ``JobManager`` 和 ``JobPanelMixin`` 中的
    不依赖 ``QProcess`` 的逻辑。"""
    return FakeJob(
        job_id=job_id,
        script_name=script_name,
        status=status,
        exit_code=exit_code,
    )


class FakeJob:
    """轻量 ``Job`` 替身，不依赖 ``QProcess``。

    仅包含测试常用的字段，不替代 ``Job.dataclass`` 的完整语义。
    用于 ``JobManager`` / ``JobPanelMixin`` 测试中需要 ``Job`` 对象
    但不触发 ``QProcess`` 实例化的场景。
    """

    def __init__(
        self,
        *,
        job_id: str = "j1",
        script_name: str = FAKE_SCRIPT_NAME,
        status: JobStatus = JobStatus.RUNNING,
        exit_code: int | None = None,
    ) -> None:
        self.job_id = job_id
        self.script_name = script_name
        self.status = status
        self.exit_code = exit_code
        self._script_entry = _FakeScriptEntry(script_name)

    @property
    def script_entry(self) -> _FakeScriptEntry:
        return self._script_entry


class _FakeScriptEntry:
    """轻量 ``ScriptEntry`` 替身，仅暴露 ``name`` 属性。"""

    def __init__(self, name: str) -> None:
        self.name = name


# -- BatchManager 测试用 fakes --


class FakeJobStatusProvider:
    """可控的 ``get_job_status`` 替身，用于 BatchManager 单测。

    通过 ``status_map`` 字典控制每个 job_id 返回的状态。
    设置 ``status_map[jid] = None`` 可模拟 job 被 prune 的场景。

    Usage::

        provider = FakeJobStatusProvider({"j1": JobStatus.SUCCESS})
        assert provider.get_job_status("j1") == JobStatus.SUCCESS
        assert provider.get_job_status("unknown") is None

        # 模拟 job 被 prune
        provider.status_map["j1"] = None
        assert provider.get_job_status("j1") is None
    """

    def __init__(
        self, status_map: dict[str, JobStatus | None] | None = None
    ) -> None:
        self.status_map: dict[str, JobStatus | None] = dict(status_map or {})

    def get_job_status(self, job_id: str) -> JobStatus | None:
        """返回 job_id 对应的状态，不在 map 中则返回 None。"""
        return self.status_map.get(job_id)


def make_batch_manager(
    provider: FakeJobStatusProvider | None = None,
) -> "BatchManager":
    """构造 ``BatchManager`` 实例，默认使用空的 ``FakeJobStatusProvider``。

    Args:
        provider: 可选的 ``FakeJobStatusProvider`` 实例。

    Returns:
        已配置好 ``get_job_status`` 注入的 ``BatchManager`` 实例。
    """
    from tod.gui.batch.batch_manager import BatchManager

    if provider is None:
        provider = FakeJobStatusProvider()
    return BatchManager(get_job_status=provider.get_job_status)
