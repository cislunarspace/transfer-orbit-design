"""项目树 -- 按 Artifact 类型分组展示，支持 Ctrl+多选。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from src.model import Artifact, Project

# 分组标签（含 Emoji 前缀，与 architecture.md:203-216 对齐）
_TYPE_GROUP_LABELS: dict[str, str] = {
    "orbit": "\U0001FA90 轨道",  # 🪐
    "family": "\U0001F300 轨道族",  # 🌀
    "transfer": "\U0001F680 转移",  # 🚀
    "ephemeris": "\U0001F4E1 星历",  # 📡
}


class ProjectTreeView(QWidget):
    """项目树封装。

    Signals:
        artifact_selected(str):       单击单个 artifact_id
        artifacts_selected(list[str]): Ctrl+多选 artifact_id 列表
    """

    artifact_selected = pyqtSignal(str)
    artifacts_selected = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tree = QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )
        # itemClicked → 单选信号
        self._tree.itemClicked.connect(self._on_item_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    # -- 公共 API -----------------------------------------------------------

    def refresh(self, project: Project) -> None:
        """从 Project 重建树结构。"""
        self._tree.clear()
        type_groups: dict[str, list[Artifact]] = {}
        for a in project.artifacts:
            type_groups.setdefault(a.artifact_type, []).append(a)

        for atype, items in type_groups.items():
            label = _TYPE_GROUP_LABELS.get(atype, atype)
            group = QTreeWidgetItem(self._tree, [label])
            group.setExpanded(True)
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for artifact in items:
                child = QTreeWidgetItem(group, [artifact.label])
                child.setData(0, Qt.ItemDataRole.UserRole, artifact.artifact_id)

    def selected_artifact_ids(self) -> list[str]:
        """返回当前选中的所有 artifact_id。"""
        ids: list[str] = []
        for item in self._tree.selectedItems():
            aid = item.data(0, Qt.ItemDataRole.UserRole)
            if aid:
                ids.append(aid)
        return ids

    # -- 内部 ---------------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        artifact_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not artifact_id:
            return  # 点击的是分组节点

        selected = self.selected_artifact_ids()
        if len(selected) > 1:
            self.artifacts_selected.emit(selected)
        else:
            self.artifact_selected.emit(artifact_id)
