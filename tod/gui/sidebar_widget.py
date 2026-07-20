"""PyQt6 图形界面组件。

"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QStackedLayout, QVBoxLayout, QWidget

from tod.scripting import SCRIPTS
from tod.gui.script_tree import build_tree_from_scripts
from tod.gui.sidebar_tree import SidebarTreeWidget

class SidebarWidget(QWidget):
    """Container widget with search bar and sidebar tree."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 品牌头部：LOGO 和应用名称
        self._setup_brand_header(layout)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(self.tr("搜索工具..."))
        self._search_input.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._search_input)

        stacked = QStackedLayout()
        stacked.setStackingMode(QStackedLayout.StackingMode.StackAll)

        nodes = build_tree_from_scripts(SCRIPTS)
        self._tree = SidebarTreeWidget(nodes)
        stacked.addWidget(self._tree)

        self._empty_label = QLabel(self.tr("无匹配结果"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setObjectName("sidebarEmptyLabel")
        self._empty_label.setVisible(False)
        stacked.addWidget(self._empty_label)

        layout.addLayout(stacked, stretch=1)

    def _connect_signals(self) -> None:
        self._search_input.textChanged.connect(self._on_search_text_changed)

    def _on_search_text_changed(self, text: str) -> None:
        if not text:
            self._tree.clear_search()
            self._empty_label.hide()
            return

        results = self._tree.search(text)
        if len(results) == 0:
            self._empty_label.show()
        else:
            self._empty_label.hide()

    def set_script_selected_callback(self, callback):
        """设置脚本选中时的回调"""
        self._tree.set_script_selected_callback(callback)

    def _setup_brand_header(self, layout: QVBoxLayout) -> None:
        """设置品牌头部：LOGO 和应用名称。"""
        # 从已知路径获取仓库根目录
        logo_path = Path(__file__).parent.parent.parent / "logo.png"

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(4, 8, 4, 8)
        header_layout.setSpacing(8)

        logo_label = QLabel()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled = pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled)
        header_layout.addWidget(logo_label)

        name_label = QLabel("Transfer Orbit Design")
        name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(name_label, stretch=1)

        layout.addWidget(header_widget)
