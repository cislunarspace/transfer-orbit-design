"""BatchManager 生命周期管理器的单测。

覆盖范围：
- create_batch 正常创建 + 信号触发
- create_batch 拒绝空 job_ids（ValueError）
- batch_aggregate_changed 仅在聚合状态变化时发射（去重）
- batch_jobs_changed 每次 refresh 必发
- refresh 清理被 prune 的 job（get_job_status 返回 None）
- 空 batch 自动删除并 emit batch_removed
- remove_batch 显式移除
- get_batch / all_batches / get_aggregate 查询
"""

from __future__ import annotations

import pytest

from tod.gui.batch import BatchAggregate
from tod.gui.job_status import JobStatus

from tests.tod.gui.fakes import FakeJobStatusProvider, FAKE_SCRIPT_NAME, make_batch_manager


# -- create_batch --


class TestCreateBatch:
    def test_returns_batch_id(self, qtbot):
        provider = FakeJobStatusProvider({"j1": JobStatus.RUNNING})
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1",))
        assert isinstance(batch_id, str)
        assert len(batch_id) == 8

    def test_emits_batch_created_signal(self, qtbot):
        provider = FakeJobStatusProvider({"j1": JobStatus.RUNNING})
        bm = make_batch_manager(provider)
        with qtbot.waitSignal(bm.batch_created, timeout=1000) as blocker:
            batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1",))
        assert blocker.args == [batch_id]

    def test_stores_batch_run(self, qtbot):
        provider = FakeJobStatusProvider({"j1": JobStatus.SUCCESS, "j2": JobStatus.SUCCESS})
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1", "j2"))
        batch = bm.get_batch(batch_id)
        assert batch is not None
        assert batch.batch_id == batch_id
        assert batch.script_name == FAKE_SCRIPT_NAME
        assert batch.job_ids == ("j1", "j2")

    def test_empty_job_ids_raises_value_error(self, qtbot):
        provider = FakeJobStatusProvider()
        bm = make_batch_manager(provider)
        with pytest.raises(ValueError):
            bm.create_batch(FAKE_SCRIPT_NAME, ())

    def test_initial_aggregate_is_computed(self, qtbot):
        provider = FakeJobStatusProvider({"j1": JobStatus.SUCCESS, "j2": JobStatus.FAILURE})
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1", "j2"))
        assert bm.get_aggregate(batch_id) == BatchAggregate.PARTIAL


# -- batch_aggregate_changed 去重 --


class TestAggregateChangedDedup:
    def test_no_signal_when_aggregate_unchanged(self, qtbot):
        """连续 refresh 但状态不变时，batch_aggregate_changed 不应再发射。"""
        provider = FakeJobStatusProvider({
            "j1": JobStatus.RUNNING,
            "j2": JobStatus.RUNNING,
        })
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1", "j2"))

        # 创建时已经发射过一次 batch_aggregate_changed（隐含在 create_batch 内）
        # 再次 refresh，状态仍是 running → 不应发射
        with qtbot.assertNotEmitted(bm.batch_aggregate_changed, wait=100):
            bm.refresh()

    def test_signal_emitted_when_aggregate_changes(self, qtbot):
        """状态从 running 变为 success 时，应发射 batch_aggregate_changed。"""
        provider = FakeJobStatusProvider({
            "j1": JobStatus.RUNNING,
            "j2": JobStatus.RUNNING,
        })
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1", "j2"))

        # 两个 job 都完成
        provider.status_map["j1"] = JobStatus.SUCCESS
        provider.status_map["j2"] = JobStatus.SUCCESS

        with qtbot.waitSignal(bm.batch_aggregate_changed, timeout=1000) as blocker:
            bm.refresh()
        assert blocker.args[0] == batch_id
        assert blocker.args[1] == BatchAggregate.SUCCESS

    def test_signal_not_emitted_for_same_transition(self, qtbot):
        """连续两次 refresh 到相同终态，第二次不发射。"""
        provider = FakeJobStatusProvider({
            "j1": JobStatus.RUNNING,
        })
        bm = make_batch_manager(provider)
        bm.create_batch(FAKE_SCRIPT_NAME, ("j1",))

        provider.status_map["j1"] = JobStatus.SUCCESS
        bm.refresh()  # 第一次变化：running → success

        # 第二次 refresh，状态仍是 success → 不发射
        with qtbot.assertNotEmitted(bm.batch_aggregate_changed, wait=100):
            bm.refresh()


# -- batch_jobs_changed 每次必发 --


class TestJobsChangedAlwaysEmitted:
    def test_jobs_changed_emitted_on_every_refresh(self, qtbot):
        provider = FakeJobStatusProvider({"j1": JobStatus.RUNNING})
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1",))

        # 状态不变，但 batch_jobs_changed 应该发射
        with qtbot.waitSignal(bm.batch_jobs_changed, timeout=1000) as blocker:
            bm.refresh()
        assert blocker.args == [batch_id]


# -- refresh 清理被 prune 的 job --


class TestRefreshPrunesJobs:
    def test_all_jobs_pruned_removes_batch(self, qtbot):
        """所有 job 被 prune（get_job_status 返回 None）时，batch 自动删除。"""
        provider = FakeJobStatusProvider({"j1": JobStatus.SUCCESS})
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1",))

        # 模拟 job 被 prune
        provider.status_map["j1"] = None

        with qtbot.waitSignal(bm.batch_removed, timeout=1000) as blocker:
            bm.refresh()
        assert blocker.args == [batch_id]
        assert bm.get_batch(batch_id) is None

    def test_partial_prune_keeps_batch(self, qtbot):
        """部分 job 被 prune 时，batch 保留（含剩余 job 的聚合状态）。"""
        provider = FakeJobStatusProvider({
            "j1": JobStatus.SUCCESS,
            "j2": JobStatus.RUNNING,
        })
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1", "j2"))

        # j1 被 prune，j2 仍在运行
        provider.status_map["j1"] = None

        with qtbot.assertNotEmitted(bm.batch_removed, wait=100):
            bm.refresh()

        # batch 仍存在，聚合状态为 running（j2 仍在运行）
        assert bm.get_batch(batch_id) is not None

    def test_prune_changes_aggregate(self, qtbot):
        """prune 后聚合状态变化应发射 batch_aggregate_changed。"""
        provider = FakeJobStatusProvider({
            "j1": JobStatus.FAILURE,
            "j2": JobStatus.SUCCESS,
        })
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1", "j2"))
        assert bm.get_aggregate(batch_id) == BatchAggregate.PARTIAL

        # j1 被 prune，只剩 j2 success → 聚合变为 success
        provider.status_map["j1"] = None

        with qtbot.waitSignal(bm.batch_aggregate_changed, timeout=1000) as blocker:
            bm.refresh()
        assert blocker.args[1] == BatchAggregate.SUCCESS


# -- remove_batch --


class TestRemoveBatch:
    def test_removes_batch_and_emits(self, qtbot):
        provider = FakeJobStatusProvider({"j1": JobStatus.RUNNING})
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1",))

        with qtbot.waitSignal(bm.batch_removed, timeout=1000) as blocker:
            bm.remove_batch(batch_id)
        assert blocker.args == [batch_id]
        assert bm.get_batch(batch_id) is None

    def test_nonexistent_batch_is_noop(self, qtbot):
        provider = FakeJobStatusProvider()
        bm = make_batch_manager(provider)
        with qtbot.assertNotEmitted(bm.batch_removed, wait=100):
            bm.remove_batch("nonexistent")


# -- get_aggregate --


class TestGetAggregate:
    def test_returns_none_for_nonexistent_batch(self, qtbot):
        provider = FakeJobStatusProvider()
        bm = make_batch_manager(provider)
        assert bm.get_aggregate("nonexistent") is None

    def test_returns_correct_aggregate(self, qtbot):
        provider = FakeJobStatusProvider({
            "j1": JobStatus.STOPPED,
            "j2": JobStatus.SUCCESS,
        })
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, ("j1", "j2"))
        assert bm.get_aggregate(batch_id) == BatchAggregate.PARTIAL_WITH_STOPS


# -- all_batches --


class TestAllBatches:
    def test_empty_initially(self, qtbot):
        provider = FakeJobStatusProvider()
        bm = make_batch_manager(provider)
        assert bm.all_batches() == []

    def test_returns_all_created_batches(self, qtbot):
        provider = FakeJobStatusProvider({
            "j1": JobStatus.RUNNING,
            "j2": JobStatus.RUNNING,
        })
        bm = make_batch_manager(provider)
        id1 = bm.create_batch(FAKE_SCRIPT_NAME, ("j1",))
        id2 = bm.create_batch(FAKE_SCRIPT_NAME, ("j2",))
        batches = bm.all_batches()
        assert len(batches) == 2
        batch_ids = {b.batch_id for b in batches}
        assert batch_ids == {id1, id2}


# -- 多 batch 并存 --


class TestMultipleBatches:
    def test_independent_batch_lifecycles(self, qtbot):
        """两个 batch 独立管理：一个被 prune 不影响另一个。"""
        provider = FakeJobStatusProvider({
            "j1": JobStatus.RUNNING,
            "j2": JobStatus.SUCCESS,
        })
        bm = make_batch_manager(provider)
        batch_a = bm.create_batch(FAKE_SCRIPT_NAME, ("j1",))
        batch_b = bm.create_batch(FAKE_SCRIPT_NAME, ("j2",))

        # j1 被 prune → batch_a 删除，batch_b 不受影响
        provider.status_map["j1"] = None
        removed_ids: list[str] = []
        bm.batch_removed.connect(lambda bid: removed_ids.append(bid))
        bm.refresh()

        assert removed_ids == [batch_a]
        assert bm.get_batch(batch_a) is None
        assert bm.get_batch(batch_b) is not None


# -- 聚合状态分支覆盖 --


class TestAggregateBranches:
    """覆盖 refresh 后各种聚合状态转换。"""

    @pytest.mark.parametrize(
        "statuses, expected",
        [
            (
                {"j1": JobStatus.RUNNING, "j2": JobStatus.PENDING},
                BatchAggregate.RUNNING,
            ),
            (
                {"j1": JobStatus.SUCCESS, "j2": JobStatus.SUCCESS},
                BatchAggregate.SUCCESS,
            ),
            (
                {"j1": JobStatus.FAILURE, "j2": JobStatus.FAILURE},
                BatchAggregate.FAILURE,
            ),
            (
                {"j1": JobStatus.STOPPED, "j2": JobStatus.STOPPED},
                BatchAggregate.STOPPED,
            ),
            (
                {"j1": JobStatus.SUCCESS, "j2": JobStatus.FAILURE},
                BatchAggregate.PARTIAL,
            ),
            (
                {"j1": JobStatus.SUCCESS, "j2": JobStatus.STOPPED},
                BatchAggregate.PARTIAL_WITH_STOPS,
            ),
        ],
        ids=[
            "running",
            "success",
            "failure",
            "stopped",
            "partial",
            "partial_with_stops",
        ],
    )
    def test_aggregate_reflects_job_statuses(self, qtbot, statuses, expected):
        provider = FakeJobStatusProvider(statuses)
        bm = make_batch_manager(provider)
        batch_id = bm.create_batch(FAKE_SCRIPT_NAME, tuple(statuses.keys()))
        assert bm.get_aggregate(batch_id) == expected
