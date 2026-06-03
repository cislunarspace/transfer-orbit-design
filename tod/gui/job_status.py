"""JobStatus — 任务生命周期枚举与中文显示映射。

集中管理 Job 状态机：

- :class:`JobStatus` —— StrEnum 五个取值：pending / running / success / failure / stopped
- :data:`JOB_STATUS_DISPLAY` —— 集中硬编码的中文显示文本（不做 i18n）
- :meth:`JobStatus.from_exit_code` —— 子进程退出码到状态的纯函数

设计约束：

- 不引入 pending 真队列（pending 留给后续 issue）；此处枚举值先就位以稳定类型契约。
- ``is_active`` 描述"尚未终态"，``is_terminal`` 描述"不可再变更"。
- ``from_exit_code(stopped=True)`` 优先级最高：用户主动停止必须压过 exit_code。
"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Job 生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    STOPPED = "stopped"

    @property
    def is_active(self) -> bool:
        """尚未终态：可以继续推进状态。"""
        return self in _ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        """已经终态：状态机不再变化。"""
        return self in _TERMINAL_STATUSES

    @staticmethod
    def from_exit_code(code: int, *, stopped: bool = False) -> "JobStatus":
        """退出码 → JobStatus 的纯函数。

        Args:
            code: 子进程退出码（QProcess.finished 回调中的 int）。
            stopped: 是否由用户主动停止（stop_job 路径）。优先级最高，
                即便 ``code == 0`` 也会被归类为 ``STOPPED``。

        Returns:
            ``STOPPED`` 当 ``stopped=True``；否则 ``code == 0`` → ``SUCCESS``，
            其他取值 → ``FAILURE``。
        """
        if stopped:
            return JobStatus.STOPPED
        if code == 0:
            return JobStatus.SUCCESS
        return JobStatus.FAILURE


_ACTIVE_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.PENDING, JobStatus.RUNNING}
)
_TERMINAL_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.SUCCESS, JobStatus.FAILURE, JobStatus.STOPPED}
)

# 集中硬编码的中文显示文本；不接 i18n（issue #197 设计约束）
JOB_STATUS_DISPLAY: dict[JobStatus, str] = {
    JobStatus.PENDING: "等待中",
    JobStatus.RUNNING: "运行中",
    JobStatus.SUCCESS: "已完成",
    JobStatus.FAILURE: "失败",
    JobStatus.STOPPED: "已停止",
}
