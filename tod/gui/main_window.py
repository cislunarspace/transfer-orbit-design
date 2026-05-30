"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

import json
from itertools import product
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
    QVBoxLayout,
    QWidget,
)

from tod.gui.file_discovery import FileInfo
from tod.gui.file_tree_mixin import FileTreeMixin
from tod.gui.job_manager import JobManager
from tod.gui.job_panel_mixin import JobPanelMixin
from tod.gui.output_panel import JobCard, StructuredOutputWidget
from tod.gui.run_mixin import RunMixin
from tod.gui.script_registry import SCRIPTS, ScriptEntry
from tod.gui.script_tab_bar import ScriptTabBar
from tod.gui.script_tab_widget import ScriptTabWidget
from tod.gui.settings_schema import SETTINGS_SCHEMA
from tod.gui.sidebar_widget import SidebarWidget
from tod.gui.theme_utils import get_theme_stylesheet as _get_theme_stylesheet

if TYPE_CHECKING:
    from tod.gui.doc_window import DocWindow


class MainWindow(FileTreeMixin, JobPanelMixin, RunMixin, QMainWindow):
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

        # ── Tab 1: Script Tab Bar (多脚本面板) ─────────────────
        self._script_tab_bar = ScriptTabBar(
            files=self._files,
            repo_root=self._repo_root,
            gui_defaults=self._gui_defaults,
            theme_mode=self._current_theme_mode,
        )
        self._script_tab_bar.tab_switched.connect(self._on_tab_switched)
        self._script_tab_bar.run_requested.connect(self._run_from_tab)
        self._script_tab_bar.doc_link_clicked.connect(self._open_doc_window)
        self._script_tab_bar.status_message.connect(
            lambda msg, timeout: self._status_bar.showMessage(msg, timeout)
        )
        self._script_tab_bar.copy_path_requested.connect(self._copy_path_to_clipboard)
        self._script_tab_bar.defaults_changed.connect(self._save_gui_defaults)

        tabs.addTab(self._script_tab_bar, self.tr("脚本信息"))
        self._right_tabs = tabs

        # ── Tab 2: File Browser ────────────────────────────────
        self._build_file_browser_tab(tabs)

        return tabs

    # ── 槽：脚本选择（侧边栏 → tab） ──────────────────────────

    def _on_script_selected(self, entry: ScriptEntry) -> None:
        self._current_script = entry

        if entry.output_dir:
            self._highlight_category(Path(entry.output_dir).name)

        # 通过 ScriptTabBar 打开/切换到该脚本
        if self._script_tab_bar is not None:
            self._script_tab_bar.open_script(entry)

        # 自动切换回脚本信息标签页
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

        # 同步侧边栏高亮
        if hasattr(self, "_sidebar_widget"):
            tree = self._sidebar_widget._tree
            tree.blockSignals(True)
            tree.select_script(entry.script_path)
            tree.blockSignals(False)

        # 高亮输出目录
        if entry.output_dir:
            self._highlight_category(Path(entry.output_dir).name)

    # ── 运行（从 ScriptTabWidget 委托） ────────────────────────

    def _on_run(self) -> None:
        """快捷键 Ctrl+R：运行当前 tab 的脚本。"""
        if self._script_tab_bar is None:
            return
        widget = self._script_tab_bar.current_widget()
        if widget is None:
            return
        self._run_from_tab(widget)

    def _run_from_tab(self, tab: ScriptTabWidget) -> None:
        """从 ScriptTabWidget 收集参数并启动 Job。"""
        entry = tab.entry

        if not tab.validate_params():
            return

        chip_selections = tab.collect_chip_selections()
        multi_file_configs = tab.collect_multi_file_configs()

        env_overrides = tab.collect_env_overrides()
        extra_args = tab.collect_run_args()

        # 如果脚本支持 --file 且用户在文件树中选中了文件
        if entry.accepts_file_arg:
            selected = self._file_tree.currentItem()
            if selected:
                from tod.gui.file_operations import FILE_PATH_ROLE
                abs_path = selected.data(0, FILE_PATH_ROLE)
                if abs_path:
                    extra_args = ["--file", abs_path] + extra_args

        from tod.plot.config import body_icon_env_from_settings, plot_font_env_from_settings
        env_overrides.update(plot_font_env_from_settings(self._gui_defaults.get("settings", {})))
        env_overrides.update(body_icon_env_from_settings(self._gui_defaults.get("settings", {})))

        # 展开芯片参数组合
        all_args_combinations = self._expand_chip_combinations(entry, extra_args, chip_selections)

        # 添加多文件参数
        for args in all_args_combinations:
            for key, configs in multi_file_configs.items():
                if not configs:
                    continue
                flag = None
                for multi_param in entry.multi_cli_params:
                    multi_key = multi_param.flag.lstrip("-").replace("-", "_")
                    if multi_key == key:
                        flag = multi_param.flag
                        break
                if flag:
                    args.extend([flag, json.dumps(configs)])

        for args in all_args_combinations:
            self._job_manager.start_job(entry, args, env_overrides.copy())

    def _expand_chip_combinations(
        self,
        entry: ScriptEntry,
        base_args: list[str],
        chip_selections: dict[str, list[str]],
    ) -> list[list[str]]:
        """展开芯片参数选择的所有组合。"""
        if not chip_selections:
            return [base_args]

        chip_params_list: list[tuple[str, str, list[str]]] = []
        for key, values in chip_selections.items():
            flag = None
            for chip_param in entry.cli_chip_params:
                chip_key = chip_param.flag.lstrip("-").replace("-", "_")
                if chip_key == key:
                    flag = chip_param.flag
                    break
            if flag and values:
                chip_params_list.append((key, flag, values))

        if not chip_params_list:
            return [base_args]

        combinations: list[list[str]] = []
        for combo in product(*[vals for _, _, vals in chip_params_list]):
            args = base_args.copy()
            for (_, flag, _), value in zip(chip_params_list, combo):
                args.extend([flag, value])
            combinations.append(args)

        return combinations

    # ── 文件刷新（覆盖 FileTreeMixin 的回调） ──────────────────

    def _refresh_files(self) -> None:
        """刷新文件列表，同步到所有 tab。"""
        super()._refresh_files()

        # 同步文件列表到 ScriptTabBar
        if hasattr(self, "_script_tab_bar") and self._script_tab_bar is not None:
            self._script_tab_bar.refresh_files(self._files)

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
