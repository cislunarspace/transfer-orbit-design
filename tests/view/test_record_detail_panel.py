"""tests for src.view.record_detail_panel -- 记录详情面板（issue #375）。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest


@pytest.fixture()
def qapp():
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


def _make_artifact(**overrides):
    from src.model.artifact import Artifact

    kwargs = dict(
        artifact_id="rec-1",
        record_id="rec-1",
        artifact_type="orbit",
        label="Halo (L2, C_J=3.0500)",
        orbit_type="Halo",
        source_tool="design_orbit",
        created_at=datetime(2026, 8, 19, 10, 0, tzinfo=UTC),
        extra={
            "record_id": "rec-1",
            "source_record_id": None,
            "orbit_family": "halo",
            "libration_point": 2,
            "jacobi": [3.05, 3.05],
            "amplitude": [8000.0, 8000.0],
            "has_cr3bp": True,
            "has_ephemeris": True,
            "member_count": 1,
            "tags": ["课程A", "北族"],
            "note": "课堂示例",
        },
    )
    kwargs.update(overrides)
    return Artifact(**kwargs)


class TestShowRecord:
    def test_displays_classification_and_tags(self, qapp):
        from src.view.record_detail_panel import RecordDetailPanel

        panel = RecordDetailPanel()
        panel.show_record(_make_artifact())
        info = panel._info_label.text()
        assert "Halo" in info
        assert "L2" in info
        assert "halo" in info
        assert panel._tags_edit.text() == "课程A, 北族"
        assert panel._note_edit.toPlainText() == "课堂示例"

    def test_lineage_broken_shows_marker(self, qapp):
        panel_artifact = _make_artifact(
            artifact_type="ephemeris",
            label="受控星历（Halo L2）",
            source_tool="control_orbit",
            extra={
                "record_id": "rec-2",
                "source_record_id": "gone-id",
                "orbit_family": "halo",
                "libration_point": 2,
                "jacobi": None,
                "amplitude": None,
                "has_cr3bp": False,
                "has_ephemeris": True,
                "member_count": 0,
                "tags": [],
                "note": "",
            },
        )
        from src.view.record_detail_panel import RecordDetailPanel

        panel = RecordDetailPanel()
        panel.show_record(panel_artifact, broken_lineage=True)
        assert "断链" in panel._info_label.text()
        assert "gone-id" in panel._info_label.text()

    def test_lineage_intact_shows_upstream_label(self, qapp):
        from src.view.record_detail_panel import RecordDetailPanel

        panel = RecordDetailPanel()
        artifact = _make_artifact(extra={**_make_artifact().extra, "source_record_id": "rec-0"})
        panel.show_record(artifact, upstream_label="Halo (L2, C_J=3.0500)")
        assert "←" in panel._info_label.text()

    def test_family_record_shows_member_row(self, qapp):
        from src.view.record_detail_panel import RecordDetailPanel

        artifact = _make_artifact(
            artifact_type="family",
            label="Halo 族 (L2, 50 条)",
            source_tool="orbit_family_generation",
            extra={
                "record_id": "rec-f",
                "source_record_id": None,
                "orbit_family": "halo",
                "libration_point": 2,
                "jacobi": None,
                "amplitude": None,
                "has_cr3bp": True,
                "has_ephemeris": False,
                "member_count": 50,
                "tags": [],
                "note": "",
            },
        )
        panel = RecordDetailPanel()
        panel.show_record(artifact)
        assert panel._member_row.isHidden() is False
        assert panel._member_spin.maximum() == 49

    def test_orbit_record_hides_member_row(self, qapp):
        from src.view.record_detail_panel import RecordDetailPanel

        panel = RecordDetailPanel()
        panel.show_record(_make_artifact())
        assert panel._member_row.isHidden() is True

    def test_clear_resets_panel(self, qapp):
        from src.view.record_detail_panel import RecordDetailPanel

        panel = RecordDetailPanel()
        panel.show_record(_make_artifact())
        panel.clear()
        assert panel._current_record_id is None
        assert panel._info_label.text() == "未选中记录"


class TestSignals:
    def test_save_emits_tag_requested(self, qapp):
        from PyQt6.QtWidgets import QPushButton

        from src.view.record_detail_panel import RecordDetailPanel

        panel = RecordDetailPanel()
        panel.show_record(_make_artifact())
        panel._tags_edit.setText("新课, 案例")
        panel._note_edit.setPlainText("更新注释")
        received: list = []
        panel.tag_requested.connect(lambda *args: received.append(args))
        save_btn = next(b for b in panel.findChildren(QPushButton) if b.text() == "保存标注")
        save_btn.click()
        assert received == [("rec-1", ["新课", "案例"], "更新注释")]

    def test_promote_emits_promote_requested(self, qapp):
        from PyQt6.QtWidgets import QPushButton

        from src.view.record_detail_panel import RecordDetailPanel

        artifact = _make_artifact(
            artifact_type="family",
            source_tool="orbit_family_generation",
            extra={
                "record_id": "rec-f",
                "source_record_id": None,
                "orbit_family": "halo",
                "libration_point": 2,
                "jacobi": None,
                "amplitude": None,
                "has_cr3bp": True,
                "has_ephemeris": False,
                "member_count": 10,
                "tags": [],
                "note": "",
            },
        )
        panel = RecordDetailPanel()
        panel.show_record(artifact)
        panel._member_spin.setValue(3)
        received: list = []
        panel.promote_requested.connect(lambda *args: received.append(args))
        promote_btn = next(
            b for b in panel.findChildren(QPushButton) if b.text() == "提升成员为记录"
        )
        promote_btn.click()
        assert received == [("rec-1", 3)]
