"""BatchManager — 批量运行的生命周期管理器。

管理 BatchRun 对象的创建、状态查询与信号通知：

- :class:`BatchManager` — QObject，持有内存态 ``dict[str, BatchRun]``，
  监听 Job 状态变化并发出聚合状态信号。

设计约束：

- ``BatchManager`` 不直接依赖 ``JobManager``，通过注入 ``get_job_status`` 回调
  查询 Job 状态，便于单测。
- ``batch_aggregate_changed`` 信号仅在聚合状态真正变化时发射（去重缓存
  ``_last_aggregate``），``batch_jobs_changed`` 每次查询必发。
- 空 batch（所有 job 被 prune 后）自动删除并 emit ``batch_removed``。
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from tod.gui.batch import BatchAggregate, BatchRun, aggregate_status
from tod.gui.jobs.job_status import JobStatus

class BatchManager(QObject):
    """批量运行的生命周期管理器。

    Signals:
        batch_created(batch_id): 新 batch 已创建。
        batch_jobs_changed(batch_id): batch 内 job 状态有变化（每次查询必发）。
        batch_aggregate_changed(batch_id, aggregate): 聚合状态变化（仅在变化时发）。
        batch_removed(batch_id): batch 已移除（job 全被 prune 或显式删除）。
    """

    batch_created = pyqtSignal(str)
    batch_jobs_changed = pyqtSignal(str)
    batch_aggregate_changed = pyqtSignal(str, object)
    batch_removed = pyqtSignal(str)

    def __init__(
        self,
        get_job_status: Callable[[str], JobStatus | None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_job_status = get_job_status
        self._batches: dict[str, BatchRun] = {}
        self._last_aggregate: dict[str, BatchAggregate] = {}

    # -- 公开 API --

    def create_batch(
        self,
        script_name: str,
        job_ids: tuple[str, ...],
    ) -> str:
        """创建一个新 batch，返回 batch_id。

        Args:
            script_name: 脚本显示名（来自 entry.name）。
            job_ids: 本次批量包含的 job_id 元组（非空）。

        Returns:
            新建 batch 的 8 位 uuid 短 id。

        Raises:
            ValueError: job_ids 为空。
        """
        if not job_ids:
            raise ValueError("create_batch: job_ids 不能为空")

        batch_id = uuid.uuid4().hex[:8]
        batch = BatchRun(
            batch_id=batch_id,
            script_name=script_name,
            job_ids=job_ids,
            created_at=time.time(),
        )
        self._batches[batch_id] = batch

        # 初始化聚合状态缓存
        statuses = [s for s in self._collect_job_statuses(job_ids) if s is not None]
        agg = aggregate_status(statuses)
        self._last_aggregate[batch_id] = agg

        self.batch_created.emit(batch_id)
        return batch_id

    def get_batch(self, batch_id: str) -> BatchRun | None:
        """获取 BatchRun 对象，不存在时返回 None。"""
        return self._batches.get(batch_id)

    def all_batches(self) -> list[BatchRun]:
        """返回所有活跃 batch 列表。"""
        return list(self._batches.values())

    def remove_batch(self, batch_id: str) -> None:
        """显式移除指定 batch 并 emit batch_removed。"""
        if batch_id in self._batches:
            del self._batches[batch_id]
            self._last_aggregate.pop(batch_id, None)
            self.batch_removed.emit(batch_id)

    def get_aggregate(self, batch_id: str) -> BatchAggregate | None:
        """获取 batch 当前聚合状态（实时计算，不依赖缓存）。

        Returns:
            BatchAggregate 或 None（batch 不存在时）。
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            return None
        statuses = [s for s in self._collect_job_statuses(batch.job_ids) if s is not None]
        if not statuses:
            return None
        return aggregate_status(statuses)

    def refresh(self) -> None:
        """刷新所有 batch 的聚合状态，发射信号并清理空 batch。

        应由外部定时器或 Job 状态变化回调触发。
        """
        to_remove: list[str] = []
        for batch_id, batch in self._batches.items():
            statuses = self._collect_job_statuses(batch.job_ids)

            # 过滤掉被 prune 的 job（get_job_status 返回 None）
            valid_statuses = [s for s in statuses if s is not None]
            if not valid_statuses:
                to_remove.append(batch_id)
                continue

            # 计算新聚合状态
            new_agg = aggregate_status(valid_statuses)
            self.batch_jobs_changed.emit(batch_id)

            # 仅在聚合状态变化时发射 signal（去重）
            old_agg = self._last_aggregate.get(batch_id)
            if new_agg != old_agg:
                self._last_aggregate[batch_id] = new_agg
                self.batch_aggregate_changed.emit(batch_id, new_agg)

        # 清理空 batch
        for batch_id in to_remove:
            del self._batches[batch_id]
            self._last_aggregate.pop(batch_id, None)
            self.batch_removed.emit(batch_id)

    # -- 私有方法 --

    def _collect_job_statuses(
        self, job_ids: tuple[str, ...]
    ) -> list[JobStatus | None]:
        """收集一组 job_id 对应的当前状态。"""
        return [self._get_job_status(jid) for jid in job_ids]
