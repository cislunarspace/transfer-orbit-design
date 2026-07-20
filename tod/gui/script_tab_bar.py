"""多脚本 Tab 管理器：QTabBar + QStackedWidget，封装打开/关闭/切换/上下文菜单。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QLabel,
    QMenu,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from tod.gui.files.file_discovery import FileInfo
from tod.scripting import ScriptEntry
from tod.gui.script_tab_widget import ScriptTabWidget

if TYPE_CHECKING:
    pass

class ScriptTabBar(QWidget):
    """管理多脚本 Tab 的容器：顶部 QTabBar + 内容区 QStackedWidget。

    - 打开脚本时复用已有 tab 或新建
    - 关闭 tab 时静默丢弃状态
    - 拖拽排序、右键菜单、Ctrl+W 关闭
    - 全部关闭时显示空白占位
    """

    # NOTE: 用 object 避免 PyQt6 的 isinstance 类型检查。
    tab_switched = pyqtSignal(object)
    tab_cleared = pyqtSignal()  # 所有 tab 关闭
    run_requested = pyqtSignal(ScriptTabWidget)
    doc_link_clicked = pyqtSignal(str)
    doc_link_missing = pyqtSignal(str)  # 文档未构建时发出警告消息
    status_message = pyqtSignal(str, int)
    copy_path_requested = pyqtSignal(str, QWidget)
    defaults_changed = pyqtSignal()

    def __init__(
        self,
        files: list[FileInfo],
        repo_root: Path,
        gui_defaults: dict[str, Any],
        theme_mode: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._files = files
        self._repo_root = repo_root
        self._gui_defaults = gui_defaults
        self._theme_mode = theme_mode

        self._widgets: list[ScriptTabWidget] = []
        self._path_to_index: dict[str, int] = {}

        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tab_bar = QTabBar()
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setUsesScrollButtons(True)
        self._tab_bar.tabCloseRequested.connect(self.close_tab)
        self._tab_bar.currentChanged.connect(self._on_current_changed)
        self._tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tab_bar.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._tab_bar)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._stack, stretch=1)

        self._empty_placeholder = self._create_empty_placeholder()
        self._stack.addWidget(self._empty_placeholder)
        self._stack.setCurrentWidget(self._empty_placeholder)

    def _setup_shortcuts(self) -> None:
        self._ctrl_w = QShortcut(QKeySequence("Ctrl+W"), self)
        self._ctrl_w.activated.connect(self._on_ctrl_w)

    def _create_empty_placeholder(self) -> QWidget:
        placeholder = QWidget()
        p_layout = QVBoxLayout(placeholder)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(self.tr("请从左侧选择工具"))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888; font-size: 13px; padding: 40px;")
        p_layout.addWidget(label)

        return placeholder

    # ── 公开接口 ───────────────────────────────────────────────

    def open_script(self, entry: ScriptEntry) -> ScriptTabWidget:
        """打开脚本 tab（复用已有或新建），返回对应的 ScriptTabWidget。"""
        if entry.script_path in self._path_to_index:
            idx = self._path_to_index[entry.script_path]
            self._tab_bar.setCurrentIndex(idx)
            return self._widgets[idx]

        tab_widget = ScriptTabWidget(
            entry=entry,
            files=self._files,
            repo_root=self._repo_root,
            gui_defaults=self._gui_defaults,
            theme_mode=self._theme_mode,
            parent=self._stack,
        )

        self._stack.addWidget(tab_widget)
        # 必须在 addTab 之前 append：addTab 在空 QTabBar 上会自动切换到
        # index 0 并触发 currentChanged，若 _widgets 尚未包含该 widget，
        # _on_current_changed 会因索引越界而跳过，导致首个 tab 内容不显示。
        self._widgets.append(tab_widget)

        tab_idx = self._tab_bar.addTab(entry.name)
        self._tab_bar.setTabToolTip(tab_idx, entry.script_path)
        self._rebuild_path_index()
        self._tab_bar.setCurrentIndex(tab_idx)

        tab_widget.run_requested.connect(lambda tw=tab_widget: self.run_requested.emit(tw))
        tab_widget.doc_link_clicked.connect(self.doc_link_clicked.emit)
        tab_widget.doc_link_missing.connect(self.doc_link_missing.emit)
        tab_widget.status_message.connect(self.status_message.emit)
        tab_widget.copy_path_requested.connect(self.copy_path_requested.emit)
        tab_widget.defaults_changed.connect(self.defaults_changed.emit)

        return tab_widget

    def close_tab(self, index: int) -> None:
        """关闭指定索引的 tab。"""
        if index < 0 or index >= self._tab_bar.count():
            return

        widget = self._widgets.pop(index)
        self._tab_bar.removeTab(index)
        self._stack.removeWidget(widget)

        # 断开所有信号连接，防止 deleteLater 后信号仍传播
        try:
            widget.run_requested.disconnect()
            widget.doc_link_clicked.disconnect()
            widget.doc_link_missing.disconnect()
            widget.status_message.disconnect()
            widget.copy_path_requested.disconnect()
            widget.defaults_changed.disconnect()
        except (TypeError, RuntimeError):
            pass

        widget.deleteLater()

        self._rebuild_path_index()

        if self._tab_bar.count() == 0:
            self._stack.setCurrentWidget(self._empty_placeholder)
            self.tab_cleared.emit()

    def close_all(self) -> None:
        while self._tab_bar.count() > 0:
            self.close_tab(0)

    def close_others(self, keep_index: int) -> None:
        while self._tab_bar.count() > keep_index + 1:
            self.close_tab(self._tab_bar.count() - 1)
        while self._tab_bar.count() > 1:
            self.close_tab(0)

    def current_widget(self) -> ScriptTabWidget | None:
        idx = self._tab_bar.currentIndex()
        if 0 <= idx < len(self._widgets):
            return self._widgets[idx]
        return None

    def current_entry(self) -> ScriptEntry | None:
        widget = self.current_widget()
        return widget.entry if widget else None

    def all_widgets(self) -> list[ScriptTabWidget]:
        return list(self._widgets)

    def refresh_files(self, files: list[FileInfo]) -> None:
        self._files = files
        for w in self._widgets:
            w.refresh_files(files)

    def update_theme(self, mode: str) -> None:
        self._theme_mode = mode
        for w in self._widgets:
            w.update_theme(mode)

    # ── 内部方法 ───────────────────────────────────────────────

    def _rebuild_path_index(self) -> None:
        self._path_to_index.clear()
        for i, w in enumerate(self._widgets):
            self._path_to_index[w.entry.script_path] = i

    def _on_current_changed(self, index: int) -> None:
        if index < 0:
            self._stack.setCurrentWidget(self._empty_placeholder)
            return

        if 0 <= index < len(self._widgets):
            widget = self._widgets[index]
            self._stack.setCurrentWidget(widget)
            self.tab_switched.emit(widget.entry)

    def _on_ctrl_w(self) -> None:
        idx = self._tab_bar.currentIndex()
        if idx >= 0:
            self.close_tab(idx)

    def _on_context_menu(self, pos) -> None:
        tab_index = self._tab_bar.tabAt(pos)
        if tab_index < 0:
            return

        menu = QMenu(self)
        close_action = menu.addAction(self.tr("关闭"))
        close_others_action = menu.addAction(self.tr("关闭其他"))
        close_all_action = menu.addAction(self.tr("关闭全部"))
        menu.addSeparator()
        move_leftmost_action = menu.addAction(self.tr("移到最左"))
        move_rightmost_action = menu.addAction(self.tr("移到最右"))

        action = menu.exec(self._tab_bar.mapToGlobal(pos))
        if action is None:
            return

        if action == close_action:
            self.close_tab(tab_index)
        elif action == close_others_action:
            self.close_others(tab_index)
        elif action == close_all_action:
            self.close_all()
        elif action == move_leftmost_action:
            self._move_tab(tab_index, 0)
        elif action == move_rightmost_action:
            self._move_tab(tab_index, self._tab_bar.count() - 1)

    def _move_tab(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return
        if from_index < 0 or from_index >= len(self._widgets):
            return

        self._tab_bar.moveTab(from_index, to_index)

        widget = self._widgets.pop(from_index)
        self._widgets.insert(to_index, widget)

        self._rebuild_path_index()
        self._tab_bar.setCurrentIndex(to_index)
