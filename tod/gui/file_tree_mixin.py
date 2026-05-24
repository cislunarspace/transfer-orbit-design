"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tod.gui.file_discovery import FileInfo, discover_files, format_size
from tod.gui.file_operations import (
    FILE_PATH_ROLE,
    format_delete_confirmation,
    get_selected_paths,
    make_relative_paths,
    reveal_in_file_manager,
)

if TYPE_CHECKING:
    from tod.gui.script_registry import ScriptEntry


class FileTreeMixin:
    """提供文件浏览器 Tab 的构建和操作方法，由 MainWindow 通过多重继承混入。"""

    _repo_root: Path
    _files: list[FileInfo]
    _status_bar: QStatusBar
    _current_script: ScriptEntry | None
    _rebuild_params_panel: Callable[..., Any]
    _file_tree: QTreeWidget

    def _build_file_browser_tab(self, tabs) -> None:
        """构建文件浏览器 Tab 并添加到 tabs 中。"""
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(4)

        # 工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(4, 4, 4, 4)
        toolbar_layout.setSpacing(4)

        self._copy_btn = QToolButton()
        self._copy_btn.setText(QCoreApplication.translate("FileTreeMixin", "复制"))
        self._copy_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        copy_menu = QMenu(cast(QWidget, self))
        copy_abs_action = copy_menu.addAction(QCoreApplication.translate("FileTreeMixin", "复制绝对路径"))
        copy_rel_action = copy_menu.addAction(QCoreApplication.translate("FileTreeMixin", "复制相对路径"))
        if copy_abs_action is not None:
            copy_abs_action.triggered.connect(self._on_copy_abs)
        if copy_rel_action is not None:
            copy_rel_action.triggered.connect(self._on_copy_rel)
        self._copy_btn.setMenu(copy_menu)
        self._copy_btn.setEnabled(False)
        toolbar_layout.addWidget(self._copy_btn)

        self._reveal_btn = QPushButton(QCoreApplication.translate("FileTreeMixin", "打开"))
        self._reveal_btn.clicked.connect(self._on_reveal_in_file_manager)
        self._reveal_btn.setEnabled(False)
        toolbar_layout.addWidget(self._reveal_btn)

        self._delete_btn = QPushButton(QCoreApplication.translate("FileTreeMixin", "删除"))
        self._delete_btn.clicked.connect(self._on_delete_files)
        self._delete_btn.setEnabled(False)
        toolbar_layout.addWidget(self._delete_btn)

        self._refresh_btn = QPushButton(QCoreApplication.translate("FileTreeMixin", "刷新"))
        self._refresh_btn.clicked.connect(self._refresh_files)
        toolbar_layout.addWidget(self._refresh_btn)

        toolbar_layout.addStretch()
        files_layout.addLayout(toolbar_layout)

        self._file_tree = QTreeWidget()
        self._file_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._file_tree.setHeaderLabels(["Filename", "Size", "Modified", "Type"])
        self._file_tree.setAlternatingRowColors(True)
        self._file_tree.setRootIsDecorated(True)
        self._file_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        self._file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_tree.customContextMenuRequested.connect(self._on_file_tree_context_menu)
        self._file_tree.itemSelectionChanged.connect(self._update_file_toolbar_state)
        QShortcut(QKeySequence("Delete"), self._file_tree, self._on_delete_files)
        files_layout.addWidget(self._file_tree, stretch=1)

        tabs.addTab(files_widget, "Files")

    # ── File Tree Operations ───────────────────────────────────

    def _on_file_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        abs_path = item.data(0, FILE_PATH_ROLE)
        if abs_path:
            self._status_bar.showMessage(f"Selected: {abs_path}")

    def _on_copy_abs(self) -> None:
        paths = get_selected_paths(self._file_tree)
        if not paths:
            return
        text = "\n".join(paths)
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)
        self._status_bar.showMessage(QCoreApplication.translate("FileTreeMixin", "已复制绝对路径（{} 个文件）").format(len(paths)), 3000)

    def _on_copy_rel(self) -> None:
        paths = get_selected_paths(self._file_tree)
        if not paths:
            return
        rel_paths = make_relative_paths(paths, self._repo_root)
        text = "\n".join(rel_paths)
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)
        self._status_bar.showMessage(QCoreApplication.translate("FileTreeMixin", "已复制相对路径（{} 个文件）").format(len(paths)), 3000)

    def _on_reveal_in_file_manager(self) -> None:
        paths = get_selected_paths(self._file_tree)
        if not paths:
            return
        reveal_in_file_manager(paths[0])

    def _on_delete_files(self) -> None:
        paths = get_selected_paths(self._file_tree)
        if not paths:
            return
        title, message = format_delete_confirmation(paths)
        reply = QMessageBox.question(
            cast(QWidget, self),
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        import os
        for p in paths:
            try:
                os.remove(p)
            except OSError as e:
                self._status_bar.showMessage(QCoreApplication.translate("FileTreeMixin", "删除失败: {}").format(e), 5000)
                return
        self._refresh_files()
        self._status_bar.showMessage(QCoreApplication.translate("FileTreeMixin", "已删除 {} 个文件").format(len(paths)), 3000)

    def _update_file_toolbar_state(self) -> None:
        paths = get_selected_paths(self._file_tree)
        has_selection = bool(paths)
        is_single_selection = len(paths) == 1
        self._copy_btn.setEnabled(has_selection)
        self._reveal_btn.setEnabled(is_single_selection)
        self._delete_btn.setEnabled(has_selection)

    def _on_file_tree_context_menu(self, position) -> None:
        menu = QMenu(cast(QWidget, self))
        menu.addAction(QCoreApplication.translate("FileTreeMixin", "复制绝对路径"), self._on_copy_abs)
        menu.addAction(QCoreApplication.translate("FileTreeMixin", "复制相对路径"), self._on_copy_rel)
        menu.addSeparator()
        menu.addAction(QCoreApplication.translate("FileTreeMixin", "在文件夹中显示"), self._on_reveal_in_file_manager)
        menu.addSeparator()
        menu.addAction(QCoreApplication.translate("FileTreeMixin", "删除"), self._on_delete_files)
        viewport = self._file_tree.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(position))

    def _refresh_files(self) -> None:
        self._files = discover_files(self._repo_root)
        self._rebuild_file_tree()
        # 刷新参数面板中的文件下拉框
        if self._current_script:
            self._rebuild_params_panel(self._current_script)
        # 反馈
        n = len(self._files)
        categories = len({f.category for f in self._files})
        if n > 0:
            self._status_bar.showMessage(QCoreApplication.translate("FileTreeMixin", "已刷新：{} 个文件，{} 个类别").format(n, categories), 5000)
        else:
            self._status_bar.showMessage(QCoreApplication.translate("FileTreeMixin", "未找到输出文件。运行脚本以生成数据。"), 5000)

    def _rebuild_file_tree(self) -> None:
        # 保存当前排序状态
        sort_col = self._file_tree.sortColumn()
        header = self._file_tree.header()
        sort_order = header.sortIndicatorOrder() if header else None
        had_sort = self._file_tree.isSortingEnabled()

        self._file_tree.setSortingEnabled(False)
        self._file_tree.clear()
        categories: dict[str, QTreeWidgetItem] = {}

        # 过滤掉图片文件（只显示 json）
        visible_files = [fi for fi in self._files if fi.file_type != "png"]

        # 空状态提示
        if not visible_files:
            empty = QTreeWidgetItem(
                self._file_tree,
                [QCoreApplication.translate("FileTreeMixin", "尚未生成输出文件。运行脚本以生成轨道数据。")],
            )
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = empty.font(0)
            font.setItalic(True)
            empty.setFont(0, font)
            empty.setForeground(0, Qt.GlobalColor.gray)
            self._file_tree.setSortingEnabled(False)
            return

        for fi in visible_files:
            if fi.category not in categories:
                cat_item = QTreeWidgetItem(self._file_tree, [fi.category])
                cat_item.setExpanded(True)
                cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                categories[fi.category] = cat_item

            parent = categories[fi.category]
            size_str = format_size(fi.size)
            mod_str = fi.modified.strftime("%Y-%m-%d %H:%M")
            item = QTreeWidgetItem(parent, [fi.name, size_str, mod_str, fi.file_type])
            item.setData(0, FILE_PATH_ROLE, fi.abs_path)
            item.setToolTip(0, fi.abs_path)
            item.setData(0, Qt.ItemDataRole.UserRole, fi.name)
            item.setData(1, Qt.ItemDataRole.UserRole, fi.size)
            item.setData(2, Qt.ItemDataRole.UserRole, fi.modified.timestamp())
            item.setData(3, Qt.ItemDataRole.UserRole, fi.file_type)

        self._file_tree.setSortingEnabled(True)
        if had_sort and sort_col >= 0 and sort_order is not None:
            self._file_tree.sortByColumn(sort_col, sort_order)
        else:
            self._file_tree.sortByColumn(2, Qt.SortOrder.DescendingOrder)

        for col in range(4):
            self._file_tree.resizeColumnToContents(col)

    def _highlight_category(self, category: str) -> None:
        """展开并滚动到指定类别。"""
        root = self._file_tree.invisibleRootItem()
        if root is None:
            return
        for i in range(root.childCount()):
            cat_item = root.child(i)
            if cat_item is not None and cat_item.text(0) == category:
                cat_item.setExpanded(True)
                self._file_tree.scrollToItem(cat_item)
                break
