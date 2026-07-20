"""Batch — 批量运行的聚合状态枚举、不可变数据结构与纯函数。

集中管理批量运行的生命周期：

- :class:`BatchAggregate` —— StrEnum 六个取值：running / success / failure / partial / partial_with_stops / stopped
- :data:`BATCH_AGGREGATE_DISPLAY` —— 集中硬编码的中文显示文本（不做 i18n）
- :func:`aggregate_status` —— 从一组 JobStatus 推导出 BatchAggregate 的纯函数
- :class:`BatchRun` —— 一次批量运行的不可变快照（batch_id / script_name / job_ids / created_at）

设计约束：

- 纯函数 ``aggregate_status`` 不依赖 Qt，便于单测。
- ``stopped`` 是 first-class 终态；``partial_with_stops`` 与 ``partial`` 平级，不互相退化。
- ``BatchRun`` 为 frozen dataclass，每次 job_ids 变化时整体替换。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tod.gui.jobs.job_status import JobStatus


class BatchAggregate(StrEnum):
    """批量运行的聚合状态。"""

    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    PARTIAL_WITH_STOPS = "partial_with_stops"
    STOPPED = "stopped"


BATCH_AGGREGATE_DISPLAY: dict[BatchAggregate, str] = {
    BatchAggregate.RUNNING: "运行中",
    BatchAggregate.SUCCESS: "全部完成",
    BatchAggregate.FAILURE: "全部失败",
    BatchAggregate.PARTIAL: "部分完成",
    BatchAggregate.PARTIAL_WITH_STOPS: "部分完成（含已停止）",
    BatchAggregate.STOPPED: "已停止",
}


def aggregate_status(statuses: tuple[JobStatus, ...] | list[JobStatus]) -> BatchAggregate:
    """从一组 JobStatus 推导出 BatchAggregate 的纯函数。

    规则（按优先级）：
    - 空输入 → ValueError
    - 任一 pending/running → running
    - 全 success → success
    - 全 failure → failure
    - 全 stopped → stopped
    - success + failure（无 stopped）→ partial
    - stopped 与其他终态混合 → partial_with_stops

    Args:
        statuses: 一组 JobStatus（非空）。

    Returns:
        推导出的 BatchAggregate。

    Raises:
        ValueError: 输入为空序列。
    """
    if not statuses:
        raise ValueError("aggregate_status: statuses 不能为空")

    status_set = frozenset(statuses)

    # 任一活跃 → running（优先级最高）
    if status_set & _ACTIVE_STATUSES:
        return BatchAggregate.RUNNING

    has_success = JobStatus.SUCCESS in status_set
    has_failure = JobStatus.FAILURE in status_set
    has_stopped = JobStatus.STOPPED in status_set

    # 全 stopped → stopped（优先于 partial_with_stops）
    if has_stopped and not has_success and not has_failure:
        return BatchAggregate.STOPPED

    # 全 success → success
    if has_success and not has_failure and not has_stopped:
        return BatchAggregate.SUCCESS

    # 全 failure → failure
    if has_failure and not has_success and not has_stopped:
        return BatchAggregate.FAILURE

    # success + failure（无 stopped）→ partial
    if has_success and has_failure and not has_stopped:
        return BatchAggregate.PARTIAL

    # stopped 与其他终态混合 → partial_with_stops
    if has_stopped:
        return BatchAggregate.PARTIAL_WITH_STOPS

    # 理论上不会走到这里（所有组合已覆盖）
    return BatchAggregate.RUNNING


_ACTIVE_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.PENDING, JobStatus.RUNNING}
)


@dataclass(frozen=True)
class BatchRun:
    """一次批量运行的不可变快照。

    Attributes:
        batch_id: 8 位 uuid 短 id。
        script_name: 脚本显示名（来自 entry.name）。
        job_ids: 本次批量包含的 job_id 元组。
        created_at: 创建时间戳（time.time()）。
    """

    batch_id: str
    script_name: str
    job_ids: tuple[str, ...]
    created_at: float
