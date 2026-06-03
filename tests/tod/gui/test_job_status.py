"""JobStatus — 枚举 + 中文显示映射 + from_exit_code 转换逻辑的单测。"""

import pytest

from tod.gui.job_status import JOB_STATUS_DISPLAY, JobStatus


class TestJobStatusEnum:
    def test_has_five_canonical_values(self):
        assert {s.name for s in JobStatus} == {
            "PENDING",
            "RUNNING",
            "SUCCESS",
            "FAILURE",
            "STOPPED",
        }

    def test_values_are_lowercase_strings(self):
        for s in JobStatus:
            assert s.value == s.value.lower()

    def test_is_active(self):
        assert JobStatus.PENDING.is_active is True
        assert JobStatus.RUNNING.is_active is True
        assert JobStatus.SUCCESS.is_active is False
        assert JobStatus.FAILURE.is_active is False
        assert JobStatus.STOPPED.is_active is False

    def test_is_terminal(self):
        assert JobStatus.PENDING.is_terminal is False
        assert JobStatus.RUNNING.is_terminal is False
        assert JobStatus.SUCCESS.is_terminal is True
        assert JobStatus.FAILURE.is_terminal is True
        assert JobStatus.STOPPED.is_terminal is True


class TestJobStatusDisplay:
    def test_display_map_covers_all_members(self):
        assert set(JOB_STATUS_DISPLAY.keys()) == set(JobStatus)

    def test_display_values_are_chinese_strings(self):
        # 简单判定：每个值至少含一个中文字符（CJK 范围）
        for status, text in JOB_STATUS_DISPLAY.items():
            assert any("一" <= ch <= "鿿" for ch in text), (
                f"{status} 缺少中文显示: {text!r}"
            )

    def test_display_values_are_nonempty(self):
        for text in JOB_STATUS_DISPLAY.values():
            assert text and text.strip()


class TestFromExitCode:
    def test_zero_exit_returns_success(self):
        assert JobStatus.from_exit_code(0) == JobStatus.SUCCESS

    def test_nonzero_exit_returns_failure(self):
        assert JobStatus.from_exit_code(1) == JobStatus.FAILURE
        assert JobStatus.from_exit_code(-1) == JobStatus.FAILURE
        assert JobStatus.from_exit_code(127) == JobStatus.FAILURE

    def test_negative_exit_returns_failure(self):
        # QProcess 报告崩溃时常给出负值
        assert JobStatus.from_exit_code(-11) == JobStatus.FAILURE

    def test_stopped_true_overrides_success(self):
        # stopped 优先级最高：即使 exit_code=0 也应返回 STOPPED
        assert JobStatus.from_exit_code(0, stopped=True) == JobStatus.STOPPED

    def test_stopped_true_overrides_failure(self):
        assert JobStatus.from_exit_code(1, stopped=True) == JobStatus.STOPPED
        assert JobStatus.from_exit_code(2, stopped=True) == JobStatus.STOPPED

    def test_stopped_false_default_does_not_change_behavior(self):
        assert JobStatus.from_exit_code(0, stopped=False) == JobStatus.SUCCESS
        assert JobStatus.from_exit_code(1, stopped=False) == JobStatus.FAILURE

    def test_stopped_default_is_false(self):
        """默认 stopped=False 行为应与显式 stopped=False 一致。"""
        assert JobStatus.from_exit_code(0) == JobStatus.from_exit_code(
            0, stopped=False
        )
        assert JobStatus.from_exit_code(1) == JobStatus.from_exit_code(
            1, stopped=False
        )
