"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from tod.gui.file_discovery import FileInfo, discover_files
from tod.gui.file_tree_mixin import FileTreeMixin
from tod.gui.job_manager import JobManager
from tod.gui.job_panel_mixin import JobPanelMixin
from tod.gui.output_panel import JobCard, StructuredOutputWidget
from tod.gui.run_orchestrator import RunOrchestrator
from tod.gui.script_registry import ScriptEntry
from tod.gui.script_tab_bar import ScriptTabBar
from tod.gui.script_tab_widget import ScriptTabWidget
from tod.gui.settings_schema import SETTINGS_SCHEMA
from tod.gui.sidebar_widget import SidebarWidget
from tod.gui.theme_utils import get_theme_stylesheet as _get_theme_stylesheet

if TYPE_CHECKING:
    from tod.gui.doc_window import DocWindow


class MainWindow(FileTreeMixin, JobPanelMixin, QMainWindow):
    """提供 MainWindow 对应的 GUI 组件。

    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """

    doc_link_clicked = pyqtSignal(str)

    def __init__(self, repo_root: str, parent=None):
        super().__init__(parent)
        self._repo_root = Path(repo_root)
        self._gui_defaults = self._load_gui_defaults()
        self._current_script: ScriptEntry | None = None
        self._right_tabs: QTabWidget | None = None
        self._files: list[FileInfo] = []

        # 多 Tab 脚本面板
        self._script_tab_bar: ScriptTabBar | None = None

        # 任务管理
        self._job_manager = JobManager(repo_root, self)
        self._job_cards: dict[str, JobCard] = {}
        self._job_outputs: dict[str, StructuredOutputWidget] = {}
        self._has_jobs = False

        # 文档窗口
        self._doc_window: DocWindow | None = None

        # 从设置加载主题
        self._current_theme_mode = self._gui_defaults.get("settings", {}).get("theme", "system")
        MainWindow._current_theme_mode = self._current_theme_mode

        # 国际化 — 必须在 UI 构建前加载，使 self.tr() 生效
        from tod.gui.i18n import TranslationLoader
        from tod.gui.script_registry import set_script_translations

        i18n_dir = Path(__file__).parent / "i18n"
        app = QApplication.instance()
        self._translation_loader = TranslationLoader(i18n_dir, app)  # type: ignore[arg-type]
        language = self._gui_defaults.get("settings", {}).get("language", "zh")
        self._translation_loader.load(language)
        set_script_translations(self._translation_loader.script_translations)

        self.setWindowTitle("Transfer Orbit Design")
        self.resize(1200, 800)

        self._build_toolbar()
        self._build_central()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        # 应用初始主题样式
        self.setStyleSheet(_get_theme_stylesheet(self._current_theme_mode))

        # 连接任务信号
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

    # ── 设置 ───────────────────────────────────────────────

    def _on_settings(self) -> None:
        from tod.gui.settings_dialog import SettingsDialog
        current = dict(self._gui_defaults.get("settings", {}))
        old_language = current.get("language", "zh")
        dialog = SettingsDialog(current, SETTINGS_SCHEMA, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            if "settings" not in self._gui_defaults:
                self._gui_defaults["settings"] = {}
            self._gui_defaults["settings"].update(settings)
            self._save_gui_defaults()

            if "theme" in settings and settings["theme"] != self._current_theme_mode:
                self._current_theme_mode = settings["theme"]
                MainWindow._current_theme_mode = settings["theme"]
                self._on_theme_changed()

            new_language = settings.get("language", "zh")
            if new_language != old_language:
                QMessageBox.information(
                    self,
                    self.tr("语言 (Language)"),
                    self.tr("语言设置已保存，下次启动生效。"),
                )

    def _on_theme_changed(self) -> None:
        """主题变化后，重建左侧面板和参数面板的颜色，并应用新样式表。"""
        self.setStyleSheet(_get_theme_stylesheet(self._current_theme_mode))

        # 重建左侧面板
        old_panel = self._left_splitter.widget(0)
        new_left = self._build_left_panel()
        self._left_splitter.replaceWidget(0, new_left)
        if old_panel is not None:
            old_panel.hide()
            old_panel.deleteLater()

        # 更新所有 tab 的主题
        if self._script_tab_bar is not None:
            self._script_tab_bar.update_theme(self._current_theme_mode)

    # ── 工具栏 ────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        refresh_btn = QPushButton(self.tr("刷新文件"))
        refresh_btn.clicked.connect(self._refresh_files)
        toolbar.addWidget(refresh_btn)

        settings_btn = QPushButton(self.tr("设置"))
        settings_btn.clicked.connect(self._on_settings)
        toolbar.addWidget(settings_btn)

        reset_layout_btn = QPushButton(self.tr("恢复默认布局"))
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

    # ── 中央控件 ─────────────────────────────────────────

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter = splitter

        left_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_splitter.addWidget(self._build_left_panel())
        self._left_splitter = left_splitter
        left_splitter.addWidget(self._build_right_panel())
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 2)

        job_panel = self._build_job_panel()

        splitter.addWidget(left_splitter)
        splitter.addWidget(job_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

    # ── 左侧面板：侧边栏树 ───────────────────────────────

    def _build_left_panel(self) -> QWidget:
        sidebar = SidebarWidget()
        sidebar.set_script_selected_callback(self._on_script_selected)
        sidebar.setMinimumWidth(220)
        self._sidebar_widget = sidebar
        return sidebar

    # ── 右侧面板：标签页 ──────────────────────────────────────

    def _build_right_panel(self) -> QTabWidget:
        tabs = QTabWidget()

        self._script_tab_bar = ScriptTabBar(
            files=self._files,
            repo_root=self._repo_root,
            gui_defaults=self._gui_defaults,
            theme_mode=self._current_theme_mode,
        )
        self._script_tab_bar.tab_switched.connect(self._on_tab_switched)
        self._script_tab_bar.tab_cleared.connect(self._on_tab_cleared)
        self._script_tab_bar.run_requested.connect(self._run_from_tab)
        self._script_tab_bar.doc_link_clicked.connect(self._open_doc_window)
        self._script_tab_bar.doc_link_missing.connect(
            lambda msg: self._status_bar.showMessage(msg, 5000)
        )
        self._script_tab_bar.status_message.connect(
            lambda msg, timeout: self._status_bar.showMessage(msg, timeout)
        )
        self._script_tab_bar.copy_path_requested.connect(self._copy_path_to_clipboard)
        self._script_tab_bar.defaults_changed.connect(self._save_gui_defaults)

        tabs.addTab(self._script_tab_bar, self.tr("脚本信息"))
        self._right_tabs = tabs

        self._build_file_browser_tab(tabs)

        return tabs

    # ── 槽：脚本选择（侧边栏 → tab） ──────────────────────────

    def _on_script_selected(self, entry: ScriptEntry) -> None:
        self._current_script = entry

        if entry.output_dir:
            self._highlight_category(Path(entry.output_dir).name)

        if self._script_tab_bar is not None:
            self._script_tab_bar.open_script(entry)

        if self._right_tabs is not None:
            script_info_titles = {self.tr("脚本信息")}
            for i in range(self._right_tabs.count()):
                if self._right_tabs.tabText(i) in script_info_titles:
                    self._right_tabs.setCurrentIndex(i)
                    break

    # ── 槽：tab 切换（tab → 侧边栏同步） ──────────────────────

    def _on_tab_switched(self, entry: ScriptEntry) -> None:
        """ScriptTabBar tab 切换时，同步侧边栏高亮和 _current_script。"""
        self._current_script = entry

        if hasattr(self, "_sidebar_widget"):
            tree = self._sidebar_widget._tree
            tree.blockSignals(True)
            tree.select_script(entry.script_path)
            tree.blockSignals(False)

        if entry.output_dir:
            self._highlight_category(Path(entry.output_dir).name)

    def _on_tab_cleared(self) -> None:
        """所有 tab 关闭后，清空 _current_script。"""
        self._current_script = None

    # ── 运行（从 ScriptTabWidget 委托） ────────────────────────

    def _on_run(self) -> None:
        if self._script_tab_bar is None:
            return
        widget = self._script_tab_bar.current_widget()
        if widget is None:
            return
        self._run_from_tab(widget)

    def _run_from_tab(self, tab: ScriptTabWidget) -> None:
        """从 ScriptTabWidget 收集参数并启动 Job。

        流程（issue #181 / ADR 0003）：参数校验 → 构造 RunPlan → 运行前确认 → dispatch。
        取消时不创建任何 Job（参见 :class:`RunConfirmationDialog`）。
        """
        entry = tab.entry

        if not tab.validate_params():
            return

        file_arg: list[str] | None = None
        if entry.accepts_file_arg:
            selected = self._file_tree.currentItem()
            if selected:
                from tod.gui.file_operations import FILE_PATH_ROLE
                abs_path = selected.data(0, FILE_PATH_ROLE)
                if abs_path:
                    file_arg = ["--file", abs_path]

        from tod.plot.config import body_icon_env_from_settings, plot_font_env_from_settings
        plot_env: dict[str, str] = {}
        plot_env.update(plot_font_env_from_settings(self._gui_defaults.get("settings", {})))
        plot_env.update(body_icon_env_from_settings(self._gui_defaults.get("settings", {})))

        plan = RunOrchestrator.build_run_plan(tab, file_arg, plot_env, self._repo_root)

        if not self._confirm_run(plan):
            self._status_bar.showMessage(self.tr("运行已取消"), 3000)
            return

        RunOrchestrator.dispatch(list(plan.specs), plan.entry, self._job_manager)

    def _confirm_run(self, plan) -> bool:
        """运行前确认入口；测试可通过 ``_confirm_run_provider`` 注入假实现。"""
        provider = getattr(self, "_confirm_run_provider", None)
        if provider is not None:
            return provider(plan)
        from tod.gui.run_confirmation_dialog import RunConfirmationDialog
        return RunConfirmationDialog.show_and_confirm(plan, self)

    # ── 文件刷新（完全覆盖 FileTreeMixin._refresh_files） ─────

    def _refresh_files(self) -> None:
        """刷新文件列表，同步到文件树和所有 tab。"""
        self._files = discover_files(self._repo_root)

        if hasattr(self, "_file_tree"):
            self._rebuild_file_tree()

        # 同步文件列表到 ScriptTabBar
        if hasattr(self, "_script_tab_bar") and self._script_tab_bar is not None:
            self._script_tab_bar.refresh_files(self._files)

        # 反馈
        n = len(self._files)
        categories = len({f.category for f in self._files})
        if n > 0:
            self._status_bar.showMessage(self.tr("已刷新：{} 个文件，{} 个类别").format(n, categories), 5000)
        else:
            self._status_bar.showMessage(self.tr("未找到输出文件。运行脚本以生成数据。"), 5000)

    # ── Job panel run-button 更新（覆盖 JobPanelMixin） ───────

    def _update_job_count(self) -> None:
        """覆盖 JobPanelMixin._update_job_count，改为更新当前 tab 的运行按钮。"""
        running = sum(1 for c in self._job_cards.values() if c.is_running)
        total = len(self._job_cards)
        if total == 0:
            self._job_count_label.setText("Jobs")
        else:
            self._job_count_label.setText(f"Jobs ({running} running, {total} total)")

        self._status_bar.showMessage(
            f"{running} running, {total} total"
            if running > 0
            else "Ready"
        )

        # 更新当前 tab 的运行按钮
        if self._script_tab_bar is not None:
            tab = self._script_tab_bar.current_widget()
            if tab is not None:
                btn = tab._run_btn
                if running >= JobManager.MAX_CONCURRENT:
                    btn.setText(self.tr("已达上限 ({})").format(JobManager.MAX_CONCURRENT))
                    btn.setStyleSheet(self._RUN_STYLE_FULL)
                    btn.setEnabled(True)
                else:
                    btn.setText(self.tr("运行"))
                    btn.setStyleSheet(self._RUN_STYLE_READY)
                    btn.setEnabled(True)

    # ── GUI 默认值持久化 ──────────────────────────────────────────

    _GUI_DEFAULTS_FILE = "gui_defaults.json"

    def _load_gui_defaults(self) -> dict[str, dict[str, str]]:
        path = self._repo_root / self._GUI_DEFAULTS_FILE
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_gui_defaults(self) -> None:
        path = self._repo_root / self._GUI_DEFAULTS_FILE
        try:
            path.write_text(
                json.dumps(self._gui_defaults, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            sb = self.statusBar()
            if sb:
                sb.showMessage(self.tr("保存默认值失败: {}").format(e), 5000)

    def _copy_path_to_clipboard(self, path: str, target_btn: QWidget) -> None:
        from PyQt6.QtWidgets import QApplication, QToolTip

        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(path)
        QToolTip.showText(
            target_btn.mapToGlobal(target_btn.rect().center()),
            self.tr("已复制！"),
            target_btn,
        )
        QTimer.singleShot(1500, QToolTip.hideText)

    # ── 窗口事件 ─────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[override]
        running = self._job_manager.running_jobs()
        if running:
            reply = QMessageBox.question(
                self,
                self.tr("确认关闭"),
                self.tr("仍有 {} 个作业正在运行。\n关闭窗口将停止所有作业。确定关闭？").format(len(running)),
                QMessageBox.StandardButton.Close | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Close:
                event.ignore()
                return
        self._job_manager.stop_all()
        super().closeEvent(event)

    # ── 文档窗口 ─────────────────────────────────────

    def _open_doc_window(self, script_path: str) -> None:
        if self._doc_window is None:
            from tod.gui.doc_window import DocWindow

            self._doc_window = DocWindow(self._repo_root, self)
            self._doc_window.destroyed.connect(self._on_doc_window_closed)

        self._doc_window.load_script_doc(script_path)
        self._doc_window.show()
        self._doc_window.raise_()
        self._doc_window.activateWindow()

    def _on_doc_window_closed(self) -> None:
        self._doc_window = None
