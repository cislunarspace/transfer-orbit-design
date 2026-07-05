# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle, QTreeWidget, QTreeWidgetItem

from tod.scripting import ScriptEntry
from tod.gui.script_tree import TreeNode


class SidebarTreeWidget(QTreeWidget):
    """Tree widget for selecting registered scripts from sidebar nodes."""

    _NODE_ROLE = Qt.ItemDataRole.UserRole
    _SCRIPT_ROLE = Qt.ItemDataRole.UserRole + 1
    _HIGHLIGHT_ROLE = Qt.ItemDataRole.UserRole + 2
    _ICON_SIZE = QSize(24, 18)
    _COLOR_RAIL_WIDTH = 4

    def __init__(self, nodes: list[TreeNode], parent=None):
        super().__init__(parent)
        self._script_selected_callback: Callable[[ScriptEntry], None] | None = None
        self._saved_expand_state: dict[int, bool] = {}

        self.setHeaderHidden(True)
        self.setIconSize(self._ICON_SIZE)
        self.itemClicked.connect(self._on_item_clicked)
        self._populate(nodes)
        self.collapse_all()

    def set_script_selected_callback(
        self,
        callback: Callable[[ScriptEntry], None],
    ) -> None:
        """设置脚本选中时的回调"""

        self._script_selected_callback = callback

    def expand_all(self) -> None:
        """展开所有节点"""

        super().expandAll()

    def collapse_all(self) -> None:
        """折叠所有节点"""

        super().collapseAll()

    def search(self, query: str) -> list[QTreeWidgetItem]:
        """Search for nodes matching query (case-insensitive)."""
        self._save_expand_state()
        self._clear_highlights()
        self.collapse_all()

        query_lower = query.lower()
        results: list[QTreeWidgetItem] = []

        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            self._collect_matching_items(item, query_lower, results)

        for item in results:
            item.setData(0, self._HIGHLIGHT_ROLE, True)
            self._expand_parent_chain(item)

        return results

    def clear_search(self) -> None:
        """Restore original expand state and clear highlights."""
        self._clear_highlights()
        self._restore_expand_state()

    def _collect_matching_items(
        self,
        item: QTreeWidgetItem,
        query_lower: str,
        results: list[QTreeWidgetItem],
    ) -> None:
        node = item.data(0, self._NODE_ROLE)
        if not isinstance(node, TreeNode):
            return

        text = item.text(0).lower()
        name = node.name.lower()
        if query_lower in text or query_lower in name:
            results.append(item)

        for i in range(item.childCount()):
            self._collect_matching_items(item.child(i), query_lower, results)

    def _expand_parent_chain(self, item: QTreeWidgetItem) -> None:
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()

    def _save_expand_state(self) -> None:
        self._saved_expand_state = {}
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            self._collect_expand_state(item)

    def _collect_expand_state(self, item: QTreeWidgetItem) -> None:
        self._saved_expand_state[id(item)] = item.isExpanded()
        for i in range(item.childCount()):
            self._collect_expand_state(item.child(i))

    def _restore_expand_state(self) -> None:
        for item_id, was_expanded in self._saved_expand_state.items():
            for i in range(self.topLevelItemCount()):
                item = self.topLevelItem(i)
                self._restore_item_state(item, item_id, was_expanded)

    def _restore_item_state(
        self, item: QTreeWidgetItem, item_id: int, was_expanded: bool
    ) -> None:
        if id(item) == item_id:
            item.setExpanded(was_expanded)
        for i in range(item.childCount()):
            self._restore_item_state(item.child(i), item_id, was_expanded)

    def _clear_highlights(self) -> None:
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            self._clear_item_highlight(item)

    def _clear_item_highlight(self, item: QTreeWidgetItem) -> None:
        item.setData(0, self._HIGHLIGHT_ROLE, False)
        for i in range(item.childCount()):
            self._clear_item_highlight(item.child(i))

    def _populate(self, nodes: list[TreeNode]) -> None:
        self.clear()
        for node in nodes:
            self.addTopLevelItem(self._build_item(node))

    def _build_item(self, node: TreeNode) -> QTreeWidgetItem:
        text = (
            node.script_entry.description
            if node.node_type == "script" and node.script_entry is not None
            else node.name
        )
        item = QTreeWidgetItem([text])
        item.setData(0, self._NODE_ROLE, node)
        item.setIcon(0, self._icon_for_node(node))
        if node.script_entry is not None:
            item.setData(0, self._SCRIPT_ROLE, node.script_entry)
        for child in node.children:
            item.addChild(self._build_item(child))
        return item

    def select_script(self, script_path: str) -> None:
        """高亮选中指定 script_path 的节点，并滚动到可见。"""
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            found = self._find_and_select(item, script_path)
            if found:
                return

    def _find_and_select(
        self, item: QTreeWidgetItem, script_path: str
    ) -> bool:
        node = item.data(0, self._NODE_ROLE)
        if not isinstance(node, TreeNode):
            return False

        if (
            node.node_type == "script"
            and node.script_entry is not None
            and node.script_entry.script_path == script_path
        ):
            self.setCurrentItem(item)
            self.scrollToItem(item)
            return True

        for i in range(item.childCount()):
            if self._find_and_select(item.child(i), script_path):
                item.setExpanded(True)
                return True
        return False

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        node = item.data(0, self._NODE_ROLE)
        if not isinstance(node, TreeNode):
            return

        if node.node_type == "script" and node.script_entry is not None:
            if self._script_selected_callback is not None:
                self._script_selected_callback(node.script_entry)
            return

        item.setExpanded(not item.isExpanded())

    def _icon_for_node(self, node: TreeNode) -> QIcon:
        standard_icon = self._standard_icon_for_node(node)
        pixmap = QPixmap(self._ICON_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.fillRect(
            0,
            0,
            self._COLOR_RAIL_WIDTH,
            self._ICON_SIZE.height(),
            QColor(node.color),
        )

        if standard_icon is not None:
            glyph = standard_icon.pixmap(16, 16)
            painter.drawPixmap(self._COLOR_RAIL_WIDTH + 3, 1, glyph)

        painter.end()
        return QIcon(pixmap)

    def _standard_icon_for_node(self, node: TreeNode) -> QIcon | None:
        style = QApplication.style()
        if node.node_type == "folder":
            return style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        if node.node_type == "empty_folder":
            return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        return None
