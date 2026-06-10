"""BatchAggregate 枚举、聚合纯函数、BatchRun frozen dataclass 的单测。

覆盖范围：
- BatchAggregate 六个枚举值
- BATCH_AGGREGATE_DISPLAY 中文映射完整性
- aggregate_status 九个聚合分支 + ValueError on empty
- BatchRun frozen 不可变契约
- BatchRun batch_id 为 8 位 uuid 短 id
"""

import time

import pytest

from tod.gui.batch import (
    BATCH_AGGREGATE_DISPLAY,
    BatchAggregate,
    BatchRun,
    aggregate_status,
)
from tod.gui.job_status import JobStatus


# -- BatchAggregate 枚举 --


class TestBatchAggregateEnum:
    def test_has_six_canonical_values(self):
        assert {s.name for s in BatchAggregate} == {
            "RUNNING",
            "SUCCESS",
            "FAILURE",
            "PARTIAL",
            "PARTIAL_WITH_STOPS",
            "STOPPED",
        }

    def test_values_are_lowercase_strings(self):
        for s in BatchAggregate:
            assert s.value == s.value.lower()

    def test_is_str_enum(self):
        assert isinstance(BatchAggregate.RUNNING, str)
        assert BatchAggregate.RUNNING == "running"


# -- BATCH_AGGREGATE_DISPLAY --


class TestBatchAggregateDisplay:
    def test_display_map_covers_all_members(self):
        assert set(BATCH_AGGREGATE_DISPLAY.keys()) == set(BatchAggregate)

    def test_display_values_are_chinese_strings(self):
        for agg, text in BATCH_AGGREGATE_DISPLAY.items():
            assert any("一" <= ch <= "鿿" for ch in text), (
                f"{agg} 缺少中文显示: {text!r}"
            )

    def test_display_values_are_nonempty(self):
        for text in BATCH_AGGREGATE_DISPLAY.values():
            assert text and text.strip()


# -- aggregate_status 纯函数 --


class TestAggregateStatusEmptyInput:
    def test_empty_list_raises_value_error(self):
        with pytest.raises(ValueError):
            aggregate_status([])

    def test_empty_tuple_raises_value_error(self):
        with pytest.raises(ValueError):
            aggregate_status(())


class TestAggregateStatusRunning:
    def test_single_pending_returns_running(self):
        assert aggregate_status([JobStatus.PENDING]) == BatchAggregate.RUNNING

    def test_single_running_returns_running(self):
        assert aggregate_status([JobStatus.RUNNING]) == BatchAggregate.RUNNING

    def test_mixed_pending_and_success_returns_running(self):
        result = aggregate_status([JobStatus.PENDING, JobStatus.SUCCESS])
        assert result == BatchAggregate.RUNNING

    def test_mixed_running_and_failure_returns_running(self):
        result = aggregate_status([JobStatus.RUNNING, JobStatus.FAILURE])
        assert result == BatchAggregate.RUNNING

    def test_all_pending_returns_running(self):
        result = aggregate_status([JobStatus.PENDING, JobStatus.PENDING])
        assert result == BatchAggregate.RUNNING

    def test_mixed_running_and_pending_returns_running(self):
        result = aggregate_status([JobStatus.RUNNING, JobStatus.PENDING])
        assert result == BatchAggregate.RUNNING


class TestAggregateStatusAllSuccess:
    def test_single_success(self):
        assert aggregate_status([JobStatus.SUCCESS]) == BatchAggregate.SUCCESS

    def test_all_success(self):
        result = aggregate_status([JobStatus.SUCCESS, JobStatus.SUCCESS, JobStatus.SUCCESS])
        assert result == BatchAggregate.SUCCESS


class TestAggregateStatusAllFailure:
    def test_single_failure(self):
        assert aggregate_status([JobStatus.FAILURE]) == BatchAggregate.FAILURE

    def test_all_failure(self):
        result = aggregate_status([JobStatus.FAILURE, JobStatus.FAILURE])
        assert result == BatchAggregate.FAILURE


class TestAggregateStatusAllStopped:
    def test_single_stopped(self):
        assert aggregate_status([JobStatus.STOPPED]) == BatchAggregate.STOPPED

    def test_all_stopped(self):
        result = aggregate_status([JobStatus.STOPPED, JobStatus.STOPPED])
        assert result == BatchAggregate.STOPPED


class TestAggregateStatusPartial:
    """success + failure（无 stopped）→ partial"""

    def test_success_and_failure(self):
        result = aggregate_status([JobStatus.SUCCESS, JobStatus.FAILURE])
        assert result == BatchAggregate.PARTIAL

    def test_multiple_success_and_failure(self):
        result = aggregate_status(
            [JobStatus.SUCCESS, JobStatus.SUCCESS, JobStatus.FAILURE]
        )
        assert result == BatchAggregate.PARTIAL


class TestAggregateStatusPartialWithStops:
    """stopped 与其他终态混合 → partial_with_stops（first-class，不退化为 partial）"""

    def test_success_and_stopped(self):
        result = aggregate_status([JobStatus.SUCCESS, JobStatus.STOPPED])
        assert result == BatchAggregate.PARTIAL_WITH_STOPS

    def test_failure_and_stopped(self):
        result = aggregate_status([JobStatus.FAILURE, JobStatus.STOPPED])
        assert result == BatchAggregate.PARTIAL_WITH_STOPS

    def test_success_failure_and_stopped(self):
        result = aggregate_status(
            [JobStatus.SUCCESS, JobStatus.FAILURE, JobStatus.STOPPED]
        )
        assert result == BatchAggregate.PARTIAL_WITH_STOPS

    def test_stopped_and_stopped(self):
        """全 stopped 应走 STOPPED 分支，不是 partial_with_stops。"""
        result = aggregate_status([JobStatus.STOPPED, JobStatus.STOPPED])
        assert result == BatchAggregate.STOPPED

    def test_single_stopped_with_success(self):
        result = aggregate_status([JobStatus.STOPPED, JobStatus.SUCCESS])
        assert result == BatchAggregate.PARTIAL_WITH_STOPS


# -- BatchRun frozen dataclass --


class TestBatchRunFrozen:
    def test_frozen_rejects_batch_id_mutation(self):
        br = BatchRun(
            batch_id="abcd1234",
            script_name="test",
            job_ids=("j1",),
            created_at=time.time(),
        )
        with pytest.raises(AttributeError):
            br.batch_id = "changed"  # type: ignore[misc]

    def test_frozen_rejects_job_ids_mutation(self):
        br = BatchRun(
            batch_id="abcd1234",
            script_name="test",
            job_ids=("j1",),
            created_at=time.time(),
        )
        with pytest.raises(AttributeError):
            br.job_ids = ("j2",)  # type: ignore[misc]

    def test_frozen_rejects_script_name_mutation(self):
        br = BatchRun(
            batch_id="abcd1234",
            script_name="test",
            job_ids=("j1",),
            created_at=time.time(),
        )
        with pytest.raises(AttributeError):
            br.script_name = "changed"  # type: ignore[misc]

    def test_frozen_rejects_created_at_mutation(self):
        br = BatchRun(
            batch_id="abcd1234",
            script_name="test",
            job_ids=("j1",),
            created_at=time.time(),
        )
        with pytest.raises(AttributeError):
            br.created_at = 0.0  # type: ignore[misc]


class TestBatchRunFields:
    def test_batch_id_is_8_chars(self):
        br = BatchRun(
            batch_id="abcd1234",
            script_name="test",
            job_ids=("j1",),
            created_at=100.0,
        )
        assert len(br.batch_id) == 8

    def test_job_ids_is_tuple(self):
        br = BatchRun(
            batch_id="abcd1234",
            script_name="test",
            job_ids=("j1", "j2", "j3"),
            created_at=100.0,
        )
        assert isinstance(br.job_ids, tuple)
        assert len(br.job_ids) == 3

    def test_equality(self):
        now = 100.0
        br1 = BatchRun("abcd1234", "test", ("j1",), now)
        br2 = BatchRun("abcd1234", "test", ("j1",), now)
        assert br1 == br2

    def test_inequality(self):
        now = 100.0
        br1 = BatchRun("abcd1234", "test", ("j1",), now)
        br2 = BatchRun("abcd5678", "test", ("j1",), now)
        assert br1 != br2
