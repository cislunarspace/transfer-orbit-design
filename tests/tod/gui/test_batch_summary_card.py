"""BatchSummaryCard 及其 view model 的单测。

覆盖范围：
- BatchJobRow / BatchSummaryViewModel frozen 不可变契约
- BatchSummaryCard.update_view_model 渲染标题+聚合状态+badge颜色
- partial_with_stops 副标题含"N 个已停止"
- 展开区各行显示 "#index 状态中文 job_id短码"
- job_selected 信号在行单击时发射，携带 job_id
- 初始 collapsed 状态（details 不可见）
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from tod.gui.batch import BATCH_AGGREGATE_DISPLAY, BatchAggregate
from tod.gui.batch.batch_summary_card import (
    BatchJobRow,
    BatchSummaryCard,
    BatchSummaryViewModel,
)
from tod.gui.jobs.job_status import JOB_STATUS_DISPLAY, JobStatus


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# -- frozen 不可变契约 --


class TestBatchJobRowFrozen:
    def test_frozen_rejects_index_mutation(self):
        row = BatchJobRow(job_id="abcd1234", index=1, status=JobStatus.RUNNING)
        with pytest.raises(AttributeError):
            row.index = 2  # type: ignore[misc]

    def test_frozen_rejects_job_id_mutation(self):
        row = BatchJobRow(job_id="abcd1234", index=1, status=JobStatus.RUNNING)
        with pytest.raises(AttributeError):
            row.job_id = "changed"  # type: ignore[misc]

    def test_frozen_rejects_status_mutation(self):
        row = BatchJobRow(job_id="abcd1234", index=1, status=JobStatus.RUNNING)
        with pytest.raises(AttributeError):
            row.status = JobStatus.SUCCESS  # type: ignore[misc]

    def test_fields_roundtrip(self):
        row = BatchJobRow(job_id="aaaa0000", index=3, status=JobStatus.STOPPED)
        assert row.job_id == "aaaa0000"
        assert row.index == 3
        assert row.status == JobStatus.STOPPED


class TestBatchSummaryViewModelFrozen:
    def test_frozen_rejects_script_name_mutation(self):
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test",
            total_jobs=2,
            aggregate_status=BatchAggregate.RUNNING,
            jobs=(
                BatchJobRow(job_id="j1", index=1, status=JobStatus.RUNNING),
                BatchJobRow(job_id="j2", index=2, status=JobStatus.RUNNING),
            ),
        )
        with pytest.raises(AttributeError):
            vm.script_name = "changed"  # type: ignore[misc]

    def test_frozen_rejects_stopped_count_mutation(self):
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test",
            total_jobs=1,
            aggregate_status=BatchAggregate.STOPPED,
            jobs=(BatchJobRow(job_id="j1", index=1, status=JobStatus.STOPPED),),
            stopped_count=1,
        )
        with pytest.raises(AttributeError):
            vm.stopped_count = 0  # type: ignore[misc]

    def test_default_stopped_count_is_zero(self):
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test",
            total_jobs=1,
            aggregate_status=BatchAggregate.SUCCESS,
            jobs=(BatchJobRow(job_id="j1", index=1, status=JobStatus.SUCCESS),),
        )
        assert vm.stopped_count == 0


# -- 视觉渲染 --


class TestBatchSummaryCardRendering:
    def test_collapsed_by_default(self, qapp):
        card = BatchSummaryCard()
        details = card._details_widget
        assert not details.isVisible()

    def test_title_shows_script_name_and_aggregate(self, qapp):
        card = BatchSummaryCard()
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test_script",
            total_jobs=3,
            aggregate_status=BatchAggregate.RUNNING,
            jobs=(
                BatchJobRow(job_id="j1", index=1, status=JobStatus.RUNNING),
                BatchJobRow(job_id="j2", index=2, status=JobStatus.RUNNING),
                BatchJobRow(job_id="j3", index=3, status=JobStatus.RUNNING),
            ),
        )
        card.update_view_model(vm)
        title_text = card._title_label.text()
        assert "test_script" in title_text
        assert "3" in title_text
        assert BATCH_AGGREGATE_DISPLAY[BatchAggregate.RUNNING] in title_text

    def test_subtitle_hidden_for_success(self, qapp):
        card = BatchSummaryCard()
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test_script",
            total_jobs=2,
            aggregate_status=BatchAggregate.SUCCESS,
            jobs=(
                BatchJobRow(job_id="j1", index=1, status=JobStatus.SUCCESS),
                BatchJobRow(job_id="j2", index=2, status=JobStatus.SUCCESS),
            ),
        )
        card.update_view_model(vm)
        assert card._subtitle_label.isHidden()

    def test_subtitle_visible_for_partial_with_stops(self, qapp):
        card = BatchSummaryCard()
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test_script",
            total_jobs=3,
            aggregate_status=BatchAggregate.PARTIAL_WITH_STOPS,
            jobs=(
                BatchJobRow(job_id="j1", index=1, status=JobStatus.SUCCESS),
                BatchJobRow(job_id="j2", index=2, status=JobStatus.STOPPED),
                BatchJobRow(job_id="j3", index=3, status=JobStatus.STOPPED),
            ),
            stopped_count=2,
        )
        card.update_view_model(vm)
        assert not card._subtitle_label.isHidden()
        subtitle_text = card._subtitle_label.text()
        assert "2" in subtitle_text
        assert "已停止" in subtitle_text


# -- 展开区行内容 --


class TestBatchSummaryCardRows:
    def test_rows_display_index_status_short_id(self, qapp):
        card = BatchSummaryCard()
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test_script",
            total_jobs=2,
            aggregate_status=BatchAggregate.PARTIAL,
            jobs=(
                BatchJobRow(job_id="abcdef12", index=1, status=JobStatus.SUCCESS),
                BatchJobRow(job_id="34567890", index=2, status=JobStatus.FAILURE),
            ),
        )
        card.update_view_model(vm)
        layout = card._details_layout
        row_widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
        assert len(row_widgets) == 2

        row1_text = row_widgets[0].text()
        assert "#1" in row1_text
        assert JOB_STATUS_DISPLAY[JobStatus.SUCCESS] in row1_text
        assert "abcdef" in row1_text

        row2_text = row_widgets[1].text()
        assert "#2" in row2_text
        assert JOB_STATUS_DISPLAY[JobStatus.FAILURE] in row2_text
        assert "345678" in row2_text


# -- job_selected 信号 --


class TestBatchSummaryCardSignal:
    def test_job_selected_emitted_on_row_click(self, qapp, qtbot):
        card = BatchSummaryCard()
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test_script",
            total_jobs=2,
            aggregate_status=BatchAggregate.PARTIAL,
            jobs=(
                BatchJobRow(job_id="abcdef12", index=1, status=JobStatus.SUCCESS),
                BatchJobRow(job_id="34567890", index=2, status=JobStatus.FAILURE),
            ),
        )
        card.update_view_model(vm)
        layout = card._details_layout
        row2_widget = layout.itemAt(1).widget()

        with qtbot.waitSignal(card.job_selected, timeout=1000) as blocker:
            row2_widget.mousePressEvent(None)
        assert blocker.args == ["34567890"]

    def test_job_selected_first_row(self, qapp, qtbot):
        card = BatchSummaryCard()
        vm = BatchSummaryViewModel(
            batch_id="abcd1234",
            script_name="test_script",
            total_jobs=1,
            aggregate_status=BatchAggregate.SUCCESS,
            jobs=(BatchJobRow(job_id="aaaa0000", index=1, status=JobStatus.SUCCESS),),
        )
        card.update_view_model(vm)
        layout = card._details_layout
        row1_widget = layout.itemAt(0).widget()

        with qtbot.waitSignal(card.job_selected, timeout=1000) as blocker:
            row1_widget.mousePressEvent(None)
        assert blocker.args == ["aaaa0000"]
