"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from tod.gui.file_discovery import FileInfo
from tod.gui.file_tree_mixin import FileTreeMixin
from tod.gui.job_manager import JobManager
from tod.gui.job_panel_mixin import JobPanelMixin
from tod.gui.output_panel import JobCard, StructuredOutputWidget
from tod.gui.params_panel import CliWidgetFactory
from tod.gui.params_panel_mixin import ParamsPanelMixin
from tod.gui.run_mixin import RunMixin
from tod.gui.script_registry import SCRIPTS, ScriptEntry
from tod.gui.settings_schema import SETTINGS_SCHEMA
from tod.gui.sidebar_widget import SidebarWidget
from tod.gui.theme_utils import resolve_theme as _resolve_theme
from tod.gui.theme_utils import get_theme_stylesheet as _get_theme_stylesheet

if TYPE_CHECKING:
    from tod.gui.doc_window import DocWindow


class MainWindow(FileTreeMixin, JobPanelMixin, RunMixin, ParamsPanelMixin, QMainWindow):
    """提供 MainWindow 对应的 GUI 组件。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    def __init__(self, repo_root: str, parent=None):
        super().__init__(parent)
        self._repo_root = Path(repo_root)
        self._gui_defaults = self._load_gui_defaults()
        self._current_script: ScriptEntry | None = None
        self._right_tabs: QTabWidget | None = None
        self._files: list[FileInfo] = []

        # Job 管理
        self._job_manager = JobManager(repo_root, self)
        self._job_cards: dict[str, JobCard] = {}
        self._job_outputs: dict[str, StructuredOutputWidget] = {}
        self._has_jobs = False

        # Documentation window
        self._doc_window: DocWindow | None = None

        # 从设置加载 theme
        self._current_theme_mode = self._gui_defaults.get("settings", {}).get("theme", "system")
        MainWindow._current_theme_mode = self._current_theme_mode

        self.setWindowTitle("Transfer Orbit Design")
        self.resize(1200, 800)

        self._build_toolbar()
        self._build_central()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        # 应用初始主题样式表
        self.setStyleSheet(_get_theme_stylesheet(self._current_theme_mode))

        # 连接 Job 信号
        self._job_manager.job_started.connect(self._on_job_started)
        self._job_manager.job_output.connect(self._on_job_output)
        self._job_manager.job_finished.connect(self._on_job_finished)
        self._job_manager.job_error.connect(self._on_job_error)

        # 连接文档链接信号
        self.doc_link_clicked.connect(self._open_doc_window)

        # 键盘快捷键
        QShortcut(QKeySequence("Ctrl+R"), self, self._on_run)
        QShortcut(QKeySequence("Ctrl+Shift+X"), self, self._on_stop_current)

        self._refresh_files()

    # ── Settings ───────────────────────────────────────────────

    def _on_settings(self) -> None:
        from tod.gui.settings_dialog import SettingsDialog
        current = dict(self._gui_defaults.get("settings", {}))
        dialog = SettingsDialog(current, SETTINGS_SCHEMA, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            if "settings" not in self._gui_defaults:
                self._gui_defaults["settings"] = {}
            self._gui_defaults["settings"].update(settings)
            self._save_gui_defaults()

            # 只有 theme 实际改变时才 rebuild UI
            if "theme" in settings and settings["theme"] != self._current_theme_mode:
                self._current_theme_mode = settings["theme"]
                MainWindow._current_theme_mode = settings["theme"]
                self._on_theme_changed()

    def _on_theme_changed(self) -> None:
        """主题变化后，重建左侧面板和参数面板的颜色，并应用新样式表。"""
        # 暂存当前参数值（用于 rebuild 后恢复）
        saved_params = self._collect_current_param_values() if self._current_script else None

        # 应用新样式表
        self.setStyleSheet(_get_theme_stylesheet(self._current_theme_mode))

        # 重建左侧面板
        old_panel = self._left_splitter.widget(0)
        new_left = self._build_left_panel()
        self._left_splitter.replaceWidget(0, new_left)
        if old_panel is not None:
            old_panel.hide()
            old_panel.deleteLater()

        # 重建参数面板（如果当前有选中脚本）
        if self._current_script is not None:
            self._rebuild_params_panel(self._current_script)
            # 恢复暂存的参数值
            if saved_params:
                self._restore_param_values(saved_params)

    # ── Toolbar ────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        refresh_btn = QPushButton("刷新文件")
        refresh_btn.clicked.connect(self._refresh_files)
        toolbar.addWidget(refresh_btn)

        settings_btn = QPushButton("设置")
        settings_btn.clicked.connect(self._on_settings)
        toolbar.addWidget(settings_btn)

        reset_layout_btn = QPushButton("恢复默认布局")
        reset_layout_btn.clicked.connect(self._on_reset_layout)
        toolbar.addWidget(reset_layout_btn)

    def _on_reset_layout(self) -> None:
        """按初始 stretchFactor 比例重置 splitter 分割大小。"""
        main_width = self._main_splitter.width()
        if main_width > 0:
            left_total = main_width * 2 // 5
            self._main_splitter.setSizes([left_total, main_width - left_total])

        left_width = self._left_splitter.width()
        if left_width > 0:
            sidebar_w = left_width // 3
            self._left_splitter.setSizes([sidebar_w, left_width - sidebar_w])

    # ── Central Widget ─────────────────────────────────────────

    def _build_central(self) -> None:
        # 水平分割：左=脚本选择+参数，右=Job 面板
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter = splitter

        # 左侧：脚本按钮 + 右侧 tabs
        left_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_splitter.addWidget(self._build_left_panel())
        self._left_splitter = left_splitter
        left_splitter.addWidget(self._build_right_panel())
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 2)

        # 右侧：Job 面板
        job_panel = self._build_job_panel()

        splitter.addWidget(left_splitter)
        splitter.addWidget(job_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

    # ── Left Panel: Sidebar Tree ───────────────────────────────

    def _build_left_panel(self) -> QWidget:
        sidebar = SidebarWidget()
        sidebar.set_script_selected_callback(self._on_script_selected)
        sidebar.setMinimumWidth(220)
        return sidebar

    # ── Right Panel: Tabs ──────────────────────────────────────

    def _build_right_panel(self) -> QTabWidget:
        tabs = QTabWidget()

        # ── Merged Tab: Script Info + Params ───────────────────
        merged_widget = QWidget()
        merged_layout = QVBoxLayout(merged_widget)
        merged_layout.setContentsMargins(0, 0, 0, 0)
        merged_layout.setSpacing(0)

        # Scrollable params area (script info prepended at top by _rebuild_params_panel)
        self._params_scroll = QScrollArea()
        self._params_scroll.setWidgetResizable(True)
        self._params_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._params_container = QWidget()
        self._params_layout = QFormLayout(self._params_container)
        self._params_layout.setContentsMargins(12, 12, 12, 12)
        self._params_layout.setSpacing(8)
        self._params_scroll.setWidget(self._params_container)

        self._env_widgets: dict[str, QComboBox] = {}
        self._cli_widgets: dict[str, QWidget] = {}
        self._param_defaults: dict[QWidget, str] = {}  # 控件 → 默认值（标准单位）
        self._factory_defaults: dict[QWidget, str] = {}  # 控件 → 出厂默认值（用于 CLI 参数比较）
        self._cli_row_containers: dict[str, QWidget] = {}  # key → row container (for hidden_when)
        self._cli_row_labels: dict[str, QWidget] = {}  # key → row label (for hidden_when)
        self._widget_factory = CliWidgetFactory(
            files=self._files,
            on_path_mode_changed=self._on_path_mode_changed,
            on_unit_changed=self._on_unit_changed,
        )

        merged_layout.addWidget(self._params_scroll, stretch=1)

        # Run 按钮固定在底部（始终可见）
        self._run_btn = QPushButton("运行")
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run)
        self._run_btn.setStyleSheet(self._RUN_STYLE_READY)
        self._run_btn.setMinimumHeight(36)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        btn_layout.addWidget(self._run_btn)
        merged_layout.addWidget(btn_container)

        tabs.addTab(merged_widget, "Script Info")
        self._right_tabs: QTabWidget = tabs

        # ── File Browser Tab ────────────────────────────────────
        self._build_file_browser_tab(tabs)

        return tabs

    # ── Slots: Script Selection ────────────────────────────────

    def _on_script_selected(self, entry: ScriptEntry) -> None:
        self._current_script = entry
        self._run_btn.setEnabled(True)

        # 高亮关联的输出目录
        if entry.output_dir:
            self._highlight_category(Path(entry.output_dir).name)

        # 重建参数面板（含 Script Info 表头）
        self._rebuild_params_panel(entry)

        # 自动切换回 Script Info 标签页
        if self._right_tabs is not None:
            script_info_titles = {"Script Info", "脚本信息"}
            for i in range(self._right_tabs.count()):
                if self._right_tabs.tabText(i) in script_info_titles:
                    self._right_tabs.setCurrentIndex(i)
                    break

    # ── GUI 默认值持久化 ────────────────────────────────────────────

    _GUI_DEFAULTS_FILE = "gui_defaults.json"

    def _load_gui_defaults(self) -> dict[str, dict[str, str]]:
        """从 gui_defaults.json 加载用户自定义默认值。"""
        path = self._repo_root / self._GUI_DEFAULTS_FILE
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_gui_defaults(self) -> None:
        """将当前 _gui_defaults 写入 gui_defaults.json。"""
        path = self._repo_root / self._GUI_DEFAULTS_FILE
        try:
            path.write_text(
                json.dumps(self._gui_defaults, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            sb = self.statusBar()
            if sb:
                sb.showMessage(f"保存默认值失败: {e}", 5000)

    def _copy_path_to_clipboard(self, path: str, target_btn: QWidget) -> None:
        """将路径复制到剪贴板，显示复制确认 tooltip。"""
        from PyQt6.QtWidgets import QApplication, QToolTip

        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(path)
        QToolTip.showText(
            target_btn.mapToGlobal(target_btn.rect().center()),
            "已复制！",
            target_btn,
        )
        QTimer.singleShot(1500, QToolTip.hideText)

    # ── Window Events ─────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """执行 closeEvent 对应的处理逻辑。
        
        Args:
            event: 调用方传入的参数值。
        
        Returns:
            None。
        """
        running = self._job_manager.running_jobs()
        if running:
            reply = QMessageBox.question(
                self,
                "确认关闭",
                f"仍有 {len(running)} 个作业正在运行。\n关闭窗口将停止所有作业。确定关闭？",
                QMessageBox.StandardButton.Close | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Close:
                event.ignore()
                return
        self._job_manager.stop_all()
        super().closeEvent(event)

    # ── Documentation Window ─────────────────────────────────────

    def _open_doc_window(self, script_path: str) -> None:
        """Open or raise the documentation window for the given script."""
        if self._doc_window is None:
            from tod.gui.doc_window import DocWindow

            self._doc_window = DocWindow(self._repo_root, self)
            self._doc_window.destroyed.connect(self._on_doc_window_closed)

        self._doc_window.load_script_doc(script_path)
        self._doc_window.show()
        self._doc_window.raise_()
        self._doc_window.activateWindow()

    def _on_doc_window_closed(self) -> None:
        """Called when the documentation window is closed."""
        self._doc_window = None
