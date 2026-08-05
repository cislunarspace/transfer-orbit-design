"""项目树 -- 按 Artifact 类型分组展示，支持 Ctrl+多选 + 右键上下文菜单。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from src.model import Artifact, Project

# 分组标签（含 Emoji 前缀，与 architecture.md:203-216 对齐）
_TYPE_GROUP_LABELS: dict[str, str] = {
    "orbit": "\U0001fa90 轨道",  # 🪐
    "family": "\U0001f300 轨道族",  # 🌀
    "transfer": "\U0001f680 转移",  # 🚀
    "ephemeris": "\U0001f4e1 星历",  # 📡
}

# 右键菜单项：(action_key, 显示文本, enabled, 禁用时的 tooltip)。
# 未实现项对应 e2m2e 侧能力缺口（见 issue #340 审查：family/stability 阻塞于
# Facade 语义错位与缺失 Request 模型），先灰掉，e2m2e 实现后改 enabled=True。
_ORBIT_MENU_ITEMS: list[tuple[str, str, bool, str]] = [
    ("control_orbit", "轨道保持", True, ""),
    ("generate_family", "生成轨道族", False, "待 e2m2e 实现轨道族生成"),
    ("analyze_stability", "查看稳定性", False, "待 e2m2e 实现稳定性分析"),
]
_FAMILY_MENU_ITEMS: list[tuple[str, str, bool, str]] = [
    ("expand_members", "展开/折叠成员", False, "待轨道族生成实现"),
]
_TRANSFER_MENU_ITEMS: list[tuple[str, str, bool, str]] = [
    ("optimize", "优化", False, "待 e2m2e 实现"),
]


class ProjectTreeView(QWidget):
    """项目树封装。

    Signals:
        artifact_selected(str):       单击单个 artifact_id
        artifacts_selected(list[str]): Ctrl+多选 artifact_id 列表
        context_action(str, list[str]): 右键菜单动作（action_key, artifact_ids）
    """

    artifact_selected = pyqtSignal(str)
    artifacts_selected = pyqtSignal(list)
    context_action = pyqtSignal(str, list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tree = QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # itemClicked → 单选信号
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        # artifact_id → artifact_type 映射，供右键菜单按类型构建
        self._id_to_type: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    # -- 公共 API -----------------------------------------------------------

    def refresh(self, project: Project) -> None:
        """从 Project 重建树结构。"""
        self._tree.clear()
        self._id_to_type = {}
        type_groups: dict[str, list[Artifact]] = {}
        for a in project.artifacts:
            type_groups.setdefault(a.artifact_type, []).append(a)
            self._id_to_type[a.artifact_id] = a.artifact_type

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

    def _on_context_menu(self, point) -> None:  # noqa: ANN001 -- Qt 传 QPoint
        """右键菜单：按选中 Artifact 类型构建上下文动作。"""
        item = self._tree.itemAt(point)
        if item is None:
            return  # 点空白处
        artifact_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not artifact_id:
            return  # 分组节点，无菜单

        # 右键点未选中项 → 单选该项（标准桌面交互）
        selected = self.selected_artifact_ids()
        if artifact_id not in selected:
            self._tree.setCurrentItem(item)
            selected = [artifact_id]

        menu = QMenu(self)
        if len(selected) == 1:
            atype = self._id_to_type.get(artifact_id, "")
            self._populate_type_actions(menu, atype, selected)
            menu.addSeparator()

        delete_action = QAction("删除", menu)
        delete_action.triggered.connect(
            lambda: self.context_action.emit("delete", list(selected))
        )
        menu.addAction(delete_action)

        viewport = self._tree.viewport()
        assert viewport is not None  # QTreeWidget 总有 viewport
        menu.exec(viewport.mapToGlobal(point))

    def _populate_type_actions(
        self, menu: QMenu, atype: str, selected: list[str]
    ) -> None:
        """按 artifact_type 填充类型专属菜单项（删除由调用方统一加）。"""
        if atype == "orbit":
            items = _ORBIT_MENU_ITEMS
        elif atype == "family":
            items = _FAMILY_MENU_ITEMS
        elif atype == "transfer":
            items = _TRANSFER_MENU_ITEMS
        else:
            return  # ephemeris 等无类型专属动作，仅有删除

        for action_key, text, enabled, tip in items:
            act = QAction(text, menu)
            act.setEnabled(enabled)
            if not enabled and tip:
                act.setToolTip(tip)
            if enabled:
                act.triggered.connect(
                    lambda _, k=action_key: self.context_action.emit(k, list(selected))
                )
            menu.addAction(act)
