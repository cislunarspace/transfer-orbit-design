"""tests for src.view.project_tree -- 项目树按类型分组、Emoji 前缀、多选信号。"""

from __future__ import annotations

import numpy as np
import pytest
from PyQt6.QtCore import Qt


@pytest.fixture()
def qapp():
    """确保 QApplication 存在（pytest-qt 自动提供，兜底手动创建）。"""
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app
    except Exception:
        pytest.skip("QApplication 不可用（无 GUI 环境）")


def _make_artifact(artifact_type: str, label: str, artifact_id: str | None = None):
    """创建带 state_data 的 Artifact。"""
    from src.model import Artifact

    kwargs: dict = {
        "artifact_type": artifact_type,
        "label": label,
        "state_data": np.zeros((10, 6)),
    }
    if artifact_id is not None:
        kwargs["artifact_id"] = artifact_id
    return Artifact(**kwargs)


class TestProjectTreeViewRefresh:
    def test_empty_project_shows_no_items(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        tree = ProjectTreeView()
        tree.refresh(Project("empty"))
        # 树应该没有任何顶层 item
        assert tree._tree.topLevelItemCount() == 0

    def test_groups_by_artifact_type(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "DRO A", "id1"))
        project.add(_make_artifact("family", "DRO Family", "id2"))
        project.add(_make_artifact("transfer", "DRO→GEO", "id3"))

        tree = ProjectTreeView()
        tree.refresh(project)

        assert tree._tree.topLevelItemCount() == 3

    def test_emoji_prefix_in_group_label(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "DRO", "id1"))
        project.add(_make_artifact("family", "Family", "id2"))
        project.add(_make_artifact("transfer", "Transfer", "id3"))
        project.add(_make_artifact("ephemeris", "Ephem", "id4"))

        tree = ProjectTreeView()
        tree.refresh(project)

        group_texts = []
        for i in range(tree._tree.topLevelItemCount()):
            group_texts.append(tree._tree.topLevelItem(i).text(0))

        assert any("\U0001FA90" in t for t in group_texts)  # 🪐 orbit
        assert any("\U0001F300" in t for t in group_texts)  # 🌀 family
        assert any("\U0001F680" in t for t in group_texts)  # 🚀 transfer
        assert any("\U0001F4E1" in t for t in group_texts)  # 📡 ephemeris

    def test_group_not_selectable(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "DRO", "id1"))

        tree = ProjectTreeView()
        tree.refresh(project)

        group = tree._tree.topLevelItem(0)
        assert not (group.flags() & Qt.ItemFlag.ItemIsSelectable)

    def test_child_has_artifact_id_in_user_role(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "DRO A", "abc123"))

        tree = ProjectTreeView()
        tree.refresh(project)

        group = tree._tree.topLevelItem(0)
        child = group.child(0)
        assert child.data(0, Qt.ItemDataRole.UserRole) == "abc123"

    def test_multiple_artifacts_in_same_group(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "DRO A", "id1"))
        project.add(_make_artifact("orbit", "DRO B", "id2"))

        tree = ProjectTreeView()
        tree.refresh(project)

        assert tree._tree.topLevelItemCount() == 1
        group = tree._tree.topLevelItem(0)
        assert group.childCount() == 2

    def test_broken_lineage_marks_label(self, qapp):
        """issue #375 US6：谱系断链的记录显示 ⚠ 降级标记，不改 artifact_id。"""
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "Halo (L2)", "src-1"))
        orphan = _make_artifact("ephemeris", "受控星历", "ctl-1")
        orphan.extra["source_record_id"] = "deleted-id"
        project.add(orphan)

        tree = ProjectTreeView()
        tree.refresh(project)

        labels = []
        for i in range(tree._tree.topLevelItemCount()):
            group = tree._tree.topLevelItem(i)
            for j in range(group.childCount()):
                labels.append(group.child(j).text(0))

        assert any("⚠" in t for t in labels)
        assert all("⚠" not in t or "受控星历" in t for t in labels)
        # 断链产物本身仍可用：UserRole 仍是 record_id（可选中送画布）
        orphan_item = None
        for i in range(tree._tree.topLevelItemCount()):
            group = tree._tree.topLevelItem(i)
            for j in range(group.childCount()):
                if group.child(j).data(0, Qt.ItemDataRole.UserRole) == "ctl-1":
                    orphan_item = group.child(j)
        assert orphan_item is not None


class TestProjectTreeViewSignals:
    def test_single_click_emits_artifact_selected(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "DRO A", "id1"))

        tree = ProjectTreeView()
        tree.refresh(project)

        received: list[str] = []
        tree.artifact_selected.connect(received.append)

        group = tree._tree.topLevelItem(0)
        child = group.child(0)
        # 模拟点击：先点击 child item
        tree._tree.itemClicked.emit(child, 0)

        assert received == ["id1"]

    def test_multi_select_emits_artifacts_selected(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "DRO A", "id1"))
        project.add(_make_artifact("orbit", "DRO B", "id2"))

        tree = ProjectTreeView()
        tree.refresh(project)

        received: list[list[str]] = []
        tree.artifacts_selected.connect(received.append)

        group = tree._tree.topLevelItem(0)
        child0 = group.child(0)
        child1 = group.child(1)

        # 选中两个 item
        child0.setSelected(True)
        child1.setSelected(True)

        # 模拟点击最后一个
        tree._tree.itemClicked.emit(child1, 0)

        assert len(received) == 1
        assert set(received[0]) == {"id1", "id2"}

    def test_click_group_node_does_not_emit(self, qapp):
        from src.model import Project
        from src.view.project_tree import ProjectTreeView

        project = Project("test")
        project.add(_make_artifact("orbit", "DRO A", "id1"))

        tree = ProjectTreeView()
        tree.refresh(project)

        received: list[str] = []
        tree.artifact_selected.connect(received.append)

        group = tree._tree.topLevelItem(0)
        # 点击分组节点
        tree._tree.itemClicked.emit(group, 0)

        assert received == []
