"""QTreeWidget sidebar component for script tree nodes."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle, QTreeWidget, QTreeWidgetItem

from tod.gui.script_registry import ScriptEntry
from tod.gui.script_tree import TreeNode


class SidebarTreeWidget(QTreeWidget):
    """Tree widget for selecting registered scripts from sidebar nodes."""

    _NODE_ROLE = Qt.ItemDataRole.UserRole
    _SCRIPT_ROLE = Qt.ItemDataRole.UserRole + 1
    _ICON_SIZE = QSize(24, 18)
    _COLOR_RAIL_WIDTH = 4

    def __init__(self, nodes: list[TreeNode], parent=None):
        super().__init__(parent)
        self._script_selected_callback: Callable[[ScriptEntry], None] | None = None

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
