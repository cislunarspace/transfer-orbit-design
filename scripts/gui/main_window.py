"""主窗口 — GUI 布局和交互逻辑（多进程 Job 版本）。"""

from __future__ import annotations

import json
from pathlib import Path
import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from scripts.gui.file_discovery import FileInfo, discover_files, filter_files, format_size
from scripts.gui.job_manager import JobManager
from scripts.gui.output_panel import JobCard, StructuredOutputWidget
from scripts.gui.script_registry import SCRIPTS, UNIT_GROUPS, CliParam, EnvParam, ScriptEntry

FILE_PATH_ROLE = Qt.ItemDataRole.UserRole + 1


class MainWindow(QMainWindow):
    def __init__(self, repo_root: str, parent=None):
        super().__init__(parent)
        self._repo_root = Path(repo_root)
        self._gui_defaults = self._load_gui_defaults()
        self._current_script: ScriptEntry | None = None
        self._files: list[FileInfo] = []

        # Job 管理
        self._job_manager = JobManager(repo_root, self)
        self._job_cards: dict[str, JobCard] = {}
        self._job_outputs: dict[str, StructuredOutputWidget] = {}
        self._has_jobs = False

        self.setWindowTitle("Transfer Orbit Design")
        self.resize(1200, 800)

        self._build_toolbar()
        self._build_central()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        # 连接 Job 信号
        self._job_manager.job_started.connect(self._on_job_started)
        self._job_manager.job_output.connect(self._on_job_output)
        self._job_manager.job_finished.connect(self._on_job_finished)
        self._job_manager.job_error.connect(self._on_job_error)

        # 键盘快捷键
        QShortcut(QKeySequence("Ctrl+R"), self, self._on_run)
        QShortcut(QKeySequence("Ctrl+Shift+X"), self, self._on_stop_current)

        self._refresh_files()

    # ── Toolbar ────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        refresh_btn = QPushButton("Refresh Files")
        refresh_btn.clicked.connect(self._refresh_files)
        toolbar.addWidget(refresh_btn)

    # ── Central Widget ─────────────────────────────────────────

    def _build_central(self) -> None:
        # 水平分割：左=脚本选择+参数，右=Job 面板
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：脚本按钮 + 右侧 tabs
        left_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_splitter.addWidget(self._build_left_panel())
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

    # ── Left Panel: Script Buttons ─────────────────────────────

    def _build_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(220)
        scroll.setMaximumWidth(300)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._script_buttons: dict[str, QPushButton] = {}
        self._button_indent: dict[str, str] = {}  # button name -> padding-left value
        self._active_script_btn: QPushButton | None = None
        self._active_script_btn_name: str | None = None

        for category, scripts in SCRIPTS.items():
            header = QLabel(category)
            header.setStyleSheet(
                "font-weight: bold; font-size: 13px; "
                "padding: 8px 4px 4px 4px; color: #555;"
            )
            layout.addWidget(header)

            current_group: str | None = None
            for entry in scripts:
                # Secondary group header
                if entry.group_label and entry.group_label != current_group:
                    current_group = entry.group_label
                    grp_lbl = QLabel(current_group)
                    grp_lbl.setStyleSheet(
                        "font-weight: bold; font-size: 11px; "
                        "padding: 6px 16px 2px 16px; color: #888;"
                    )
                    layout.addWidget(grp_lbl)

                btn = QPushButton(entry.name)
                btn.setToolTip(entry.description)
                indent = "20px" if entry.group_label else "4px"
                self._button_indent[entry.name] = indent
                btn.setStyleSheet(
                    f"QPushButton {{ text-align: left; padding: 4px 8px; "
                    f"padding-left: {indent}; }}"
                    "QPushButton:hover { background-color: #e0e0e0; }"
                )
                btn.clicked.connect(
                    lambda checked, e=entry: self._on_script_selected(e)
                )
                layout.addWidget(btn)
                self._script_buttons[entry.name] = btn

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

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
        self._cli_widgets: dict[str, QCheckBox | QLineEdit | QSpinBox | QComboBox] = {}
        self._param_defaults: dict[QWidget, str] = {}  # 控件 → 默认值（标准单位）
        self._unit_combos: dict[QLineEdit, QComboBox] = {}  # QLineEdit → 单位选择 QComboBox
        self._unit_groups: dict[QLineEdit, str] = {}        # QLineEdit → unit_group 名称
        self._wrapped_widgets: dict[QWidget, QWidget] = {}   # 原始控件 → 单位选择器包裹后的 widget

        merged_layout.addWidget(self._params_scroll, stretch=1)

        # Run 按钮固定在底部（始终可见）
        self._run_btn = QPushButton("Run")
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

        # ── File Browser Tab ────────────────────────────────────
        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels(["Filename", "Size", "Modified", "Type"])
        self._file_tree.setAlternatingRowColors(True)
        self._file_tree.setRootIsDecorated(True)
        self._file_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        tabs.addTab(self._file_tree, "Files")

        return tabs

    # ── Job Panel ──────────────────────────────────────────────

    def _build_job_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 顶部：标题 + Clear All Completed
        header = QHBoxLayout()
        self._job_count_label = QLabel("Jobs")
        self._job_count_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(self._job_count_label)
        header.addStretch()
        self._clear_completed_btn = QPushButton("Clear Completed")
        self._clear_completed_btn.setToolTip("清除所有已完成的任务")
        self._clear_completed_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 11px; }"
        )
        self._clear_completed_btn.clicked.connect(self._clear_completed_jobs)
        header.addWidget(self._clear_completed_btn)
        layout.addLayout(header)

        # Job 卡片列表
        self._job_scroll = QScrollArea()
        self._job_scroll.setWidgetResizable(True)
        self._job_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._job_scroll.setMaximumHeight(200)
        self._job_scroll.setMinimumHeight(60)

        self._job_cards_container = QWidget()
        self._job_cards_layout = QVBoxLayout(self._job_cards_container)
        self._job_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._job_cards_layout.setSpacing(4)
        self._job_cards_layout.addStretch()
        self._job_scroll.setWidget(self._job_cards_container)
        layout.addWidget(self._job_scroll)

        # 输出 Tab 面板
        self._output_tabs = QTabWidget()
        self._output_tabs.setTabsClosable(True)
        self._output_tabs.tabCloseRequested.connect(self._on_output_tab_close)

        # 空状态占位
        self._empty_label = QLabel("No active jobs.\nSelect a script and click Run.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; font-size: 12px; padding: 40px;")
        self._output_tabs.addTab(self._empty_label, "(empty)")

        layout.addWidget(self._output_tabs, stretch=1)
        return panel

    # ── Slots: Script Selection ────────────────────────────────

    def _on_script_selected(self, entry: ScriptEntry) -> None:
        self._current_script = entry
        self._run_btn.setEnabled(True)

        # 高亮选中的脚本按钮
        self._highlight_script_button(entry.name)

        # 高亮关联的输出目录
        if entry.output_dir:
            self._highlight_category(Path(entry.output_dir).name)

        # 重建参数面板（含 Script Info 表头）
        self._rebuild_params_panel(entry)

    _BTN_STYLE_NORMAL = (
        "QPushButton { text-align: left; padding: 4px 8px; "
        "padding-left: %s; }"
        "QPushButton:hover { background-color: #e0e0e0; }"
    )
    _BTN_STYLE_ACTIVE = (
        "QPushButton { text-align: left; padding: 4px 8px; "
        "background-color: #d4e8ff; border-left: 3px solid #0e639c; "
        "padding-left: %s; }"
    )

    def _highlight_script_button(self, name: str) -> None:
        """高亮选中的脚本按钮，取消之前的高亮。"""
        if self._active_script_btn is not None:
            prev_indent = self._button_indent.get(self._active_script_btn_name or "", "4px")
            self._active_script_btn.setStyleSheet(self._BTN_STYLE_NORMAL % prev_indent)
        btn = self._script_buttons.get(name)
        if btn:
            indent = self._button_indent.get(name, "4px")
            btn.setStyleSheet(self._BTN_STYLE_ACTIVE % indent)
        self._active_script_btn = btn
        self._active_script_btn_name = name

    _PARAM_BORDER_MODIFIED = "border: 1px solid #4da6ff;"

    def _update_param_highlight(self, widget: QWidget) -> None:
        """比较控件当前值与默认值，不同时加蓝色边框。"""
        default = self._param_defaults.get(widget, "")
        if isinstance(widget, QLineEdit):
            current = widget.text().strip()
        elif isinstance(widget, QComboBox):
            current = widget.currentText().strip()
        elif isinstance(widget, QSpinBox):
            current = str(widget.value())
        else:
            return

        # 带单位的参数：将当前值转换到标准单位后再与默认值比较
        if isinstance(widget, QLineEdit) and widget in self._unit_groups:
            current = self._to_standard_unit(widget)

        # 先清除旧的高亮边框，再按需添加
        base_ss = widget.styleSheet().replace(self._PARAM_BORDER_MODIFIED, "")
        if current and current != default:
            widget.setStyleSheet(base_ss + self._PARAM_BORDER_MODIFIED)
        else:
            widget.setStyleSheet(base_ss)

    def _to_standard_unit(self, line_edit: QLineEdit) -> str:
        """将 QLineEdit 中的值从当前显示单位转换为标准单位的字符串表示。"""
        text = line_edit.text().strip()
        if not text:
            return text
        group_name = self._unit_groups.get(line_edit)
        if not group_name:
            return text
        unit_combo = self._unit_combos.get(line_edit)
        if not unit_combo:
            return text
        try:
            value = float(text)
        except ValueError:
            return text
        group = UNIT_GROUPS[group_name]
        units = list(group.keys())
        factor = group[units[unit_combo.currentIndex()]]
        return f"{value * factor:.10g}"

    def _on_unit_changed(self, line_edit: QLineEdit, combo: QComboBox, group_name: str) -> None:
        """单位选择器切换时，将已有数值转换到新单位。"""
        text = line_edit.text().strip()
        if not text:
            combo.setProperty("prev_idx", combo.currentIndex())
            return
        try:
            value = float(text)
        except ValueError:
            combo.setProperty("prev_idx", combo.currentIndex())
            return
        old_idx = combo.property("prev_idx") or 0
        new_idx = combo.currentIndex()
        group = UNIT_GROUPS[group_name]
        units = list(group.keys())
        # 从旧单位转到标准单位，再转到新单位
        standard = value * group[units[old_idx]]
        new_value = standard / group[units[new_idx]]
        line_edit.setText(f"{new_value:.10g}")
        combo.setProperty("prev_idx", new_idx)

    def _find_cli_param(self, key: str) -> CliParam | None:
        """根据 key 查找当前脚本的 CliParam。"""
        if self._current_script is None:
            return None
        for p in self._current_script.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None

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
            self.statusBar().showMessage(f"保存默认值失败: {e}", 5000)

    def _on_save_defaults(self) -> None:
        """将当前参数值保存为当前脚本的默认值。"""
        if self._current_script is None:
            return

        saved: dict[str, str] = {}
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            if isinstance(widget, QCheckBox):
                saved[cli_param.flag] = str(widget.isChecked())
            elif isinstance(widget, QSpinBox):
                saved[cli_param.flag] = str(widget.value())
            elif isinstance(widget, QLineEdit):
                # 保存标准单位值（与 _param_defaults / _on_run 一致）
                if widget in self._unit_combos:
                    saved[cli_param.flag] = self._to_standard_unit(widget)
                else:
                    saved[cli_param.flag] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                saved[cli_param.flag] = widget.currentText().strip()

        self._gui_defaults[self._current_script.name] = saved
        self._save_gui_defaults()

        # 更新 _param_defaults 以同步高亮逻辑
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue
            flag = cli_param.flag
            if flag in saved:
                self._param_defaults[widget] = saved[flag]
                self._update_param_highlight(widget)

        self.statusBar().showMessage("默认值已保存", 3000)

    def _on_reset_defaults(self) -> None:
        """恢复为 script_registry 中定义的出厂默认值。"""
        if self._current_script is None:
            return

        # 从持久化存储中移除该脚本的自定义默认值
        self._gui_defaults.pop(self._current_script.name, None)
        self._save_gui_defaults()

        # 将控件恢复为 CliParam.default 并更新 _param_defaults
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            factory_default = cli_param.default or ""

            self._set_widget_std_value(widget, factory_default)
            self._param_defaults[widget] = factory_default
            self._update_param_highlight(widget)

        self.statusBar().showMessage("已恢复出厂默认值", 3000)

    def _on_run(self) -> None:
        if self._current_script is None:
            return

        extra_args: list[str] = []
        env_overrides: dict[str, str] = {}

        # 收集环境变量参数（文件选择）
        for key, combo in self._env_widgets.items():
            abs_path = combo.currentData()
            if abs_path and key in self._current_script.env_params:
                env_param = self._current_script.env_params[key]
                env_overrides[env_param.env_var] = abs_path

        # 收集命令行参数
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            if isinstance(widget, QCheckBox):
                if widget.isChecked():
                    extra_args.append(cli_param.flag)
            elif isinstance(widget, QSpinBox):
                val = widget.value()
                default = self._param_defaults.get(widget, "")
                if default:
                    if abs(val - float(default)) > 1e-9:
                        extra_args.extend([cli_param.flag, str(val)])
                elif abs(val) > 1e-9:
                    extra_args.extend([cli_param.flag, str(val)])
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                default = self._param_defaults.get(widget, "")
                # 带单位的参数：先转到标准单位再比较
                if widget in self._unit_combos:
                    std_text = self._to_standard_unit(widget)
                    if std_text and std_text != default:
                        extra_args.extend([cli_param.flag, std_text])
                elif text and text != default:
                    extra_args.extend([cli_param.flag, text])
            elif isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                default = self._param_defaults.get(widget, "")
                if text and text != default:
                    extra_args.extend([cli_param.flag, text])
                    # 同步设置对应环境变量（兼容脚本内的 os.environ 回退）
                    if cli_param.file_category:
                        _CLI_TO_ENV: dict[str, str] = {
                            "--dro-file": "DRO_FILE",
                            "--ro-file": "RO_FILE",
                            "--search-file": "SEARCH_RESULTS_FILE",
                        }
                        env_var = _CLI_TO_ENV.get(cli_param.flag)
                        if env_var:
                            env_overrides[env_var] = text

        # 如果脚本支持 --file 且用户在文件树中选中了文件
        if self._current_script.accepts_file_arg:
            selected = self._file_tree.currentItem()
            if selected:
                abs_path = selected.data(0, FILE_PATH_ROLE)
                if abs_path:
                    extra_args = ["--file", abs_path] + extra_args

        if not self._validate_params():
            return

        self._job_manager.start_job(self._current_script, extra_args, env_overrides)

    def _validate_params(self) -> bool:
        """验证参数，返回 True 表示通过。"""
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            # 必需文件参数验证
            if cli_param.file_category and not cli_param.default:
                if isinstance(widget, QComboBox):
                    text = widget.currentText().strip()
                    if not text:
                        QMessageBox.warning(
                            self,
                            "参数缺失",
                            f"脚本需要参数 '{cli_param.label}'，但未选择文件。\n"
                            "请从下拉列表中选择一个文件或手动输入路径。",
                        )
                        widget.setFocus()
                        return False

            # float 参数合法性
            if cli_param.param_type == "float" and isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if text:
                    try:
                        float(text)
                    except ValueError:
                        QMessageBox.warning(
                            self,
                            "参数无效",
                            f"参数 '{cli_param.label}' 需要数值，当前输入 '{text}' 无效。",
                        )
                        widget.setFocus()
                        return False

            # 文件存在性预检查
            if cli_param.file_category:
                if isinstance(widget, QComboBox):
                    text = widget.currentText().strip()
                elif isinstance(widget, QLineEdit):
                    text = widget.text().strip()
                else:
                    continue
                if text and not Path(text).is_file():
                    reply = QMessageBox.question(
                        self,
                        "文件不存在",
                        f"参数 '{cli_param.label}' 引用的文件不存在：\n{text}\n\n仍然继续？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return False

        return True

    # ── Slots: Job Lifecycle ───────────────────────────────────

    def _on_job_started(self, job_id: str, name: str) -> None:
        if not job_id:
            return

        # 移除空状态占位
        if not self._has_jobs:
            self._output_tabs.clear()
            self._has_jobs = True

        # 创建输出面板
        output_widget = StructuredOutputWidget()
        output_widget.status_message.connect(
            lambda msg: self._status_bar.showMessage(msg, 5000)
        )
        self._job_outputs[job_id] = output_widget
        tab_idx = self._output_tabs.addTab(output_widget, name)
        self._output_tabs.setCurrentIndex(tab_idx)

        # 创建 Job Card
        card = JobCard(job_id, name)
        card.clicked.connect(self._on_job_card_clicked)
        card.stop_requested.connect(self._on_stop_job_requested)
        self._job_cards[job_id] = card
        # 插入到 stretch 之前
        self._job_cards_layout.insertWidget(
            self._job_cards_layout.count() - 1, card
        )

        self._update_job_count()

    def _on_job_output(self, job_id: str, text: str, stream: str) -> None:
        output = self._job_outputs.get(job_id)
        if output:
            output.append_output(text, stream)

    def _on_job_finished(self, job_id: str, name: str, exit_code: int) -> None:
        card = self._job_cards.get(job_id)
        if card:
            # 查询 JobManager 获取实际状态（区分 killed vs error）
            job = self._job_manager.get_job(job_id)
            status = job.status if job else ("completed" if exit_code == 0 else "error")
            card.set_status(status)

        # 任务栏闪烁通知
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.alert(self)

        # 状态栏详细消息
        if exit_code == 0:
            self._status_bar.showMessage(f"脚本 '{name}' 完成 (exit code: 0)", 5000)
        else:
            self._status_bar.showMessage(
                f"脚本 '{name}' 失败 (exit code: {exit_code})", 8000
            )

        # 在输出面板追加结束信息
        output = self._job_outputs.get(job_id)
        if output:
            banner = f"\n{'='*60}\n[进程结束] exit code: {exit_code}\n{'='*60}\n"
            output.append_output(banner, "stdout")
            output.set_finished()

        self._update_job_count()

    def _on_job_error(self, job_id: str, msg: str) -> None:
        if not job_id:
            # 全局错误（如达到并发上限）
            self._status_bar.showMessage(msg)
            return

        card = self._job_cards.get(job_id)
        if card:
            card.set_status("error")

        output = self._job_outputs.get(job_id)
        if output:
            output.append_output(f"\n[ERROR] {msg}\n", "stderr")

        self._update_job_count()

    def _on_job_card_clicked(self, job_id: str) -> None:
        """双击 JobCard 切换到对应输出 tab。"""
        output = self._job_outputs.get(job_id)
        if output:
            idx = self._output_tabs.indexOf(output)
            if idx >= 0:
                self._output_tabs.setCurrentIndex(idx)

    def _on_stop_current(self) -> None:
        """快捷键停止当前查看的 job。"""
        current_widget = self._output_tabs.currentWidget()
        for job_id, widget in self._job_outputs.items():
            if widget is current_widget:
                self._confirm_and_stop(job_id)
                break

    def _on_stop_job_requested(self, job_id: str) -> None:
        """JobCard 停止按钮 — 长时间运行的作业需要确认。"""
        self._confirm_and_stop(job_id)

    def _confirm_and_stop(self, job_id: str) -> None:
        """停止作业，运行超过 60 秒时弹出确认。"""
        job = self._job_manager.get_job(job_id)
        if job is None:
            return
        elapsed = time.time() - job.started_at
        if elapsed > 60:
            reply = QMessageBox.question(
                self,
                "确认停止",
                f"脚本 '{job.script_entry.name}' 已运行 {int(elapsed)} 秒。\n确定停止？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._job_manager.stop_job(job_id)

    def _on_output_tab_close(self, index: int) -> None:
        """关闭输出 tab。"""
        widget = self._output_tabs.widget(index)
        # 找到对应的 job_id
        job_id_to_remove = None
        for job_id, w in self._job_outputs.items():
            if w is widget:
                job_id_to_remove = job_id
                break

        if job_id_to_remove:
            # 如果 job 还在运行，先确认
            job = self._job_manager.get_job(job_id_to_remove)
            if job and job.status == "running":
                reply = QMessageBox.question(
                    self,
                    "确认关闭",
                    f"脚本 '{job.script_entry.name}' 正在运行。\n停止并关闭？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                self._job_manager.stop_job(job_id_to_remove)
            del self._job_outputs[job_id_to_remove]

        self._output_tabs.removeTab(index)

        # 如果没有 tab 了，恢复空状态
        if self._output_tabs.count() == 0:
            self._output_tabs.addTab(self._empty_label, "(empty)")
            self._has_jobs = False

    def _clear_completed_jobs(self) -> None:
        """清除所有已完成的 job card 和对应的输出 tab。"""
        completed_ids = [
            jid
            for jid, card in self._job_cards.items()
            if not card.is_running
        ]
        for jid in completed_ids:
            # 移除 card
            card = self._job_cards.pop(jid, None)
            if card:
                self._job_cards_layout.removeWidget(card)
                card.deleteLater()

            # 移除输出 tab
            output = self._job_outputs.pop(jid, None)
            if output:
                idx = self._output_tabs.indexOf(output)
                if idx >= 0:
                    self._output_tabs.removeTab(idx)

        if self._output_tabs.count() == 0:
            self._output_tabs.addTab(self._empty_label, "(empty)")
            self._has_jobs = False

        self._update_job_count()

    _RUN_STYLE_READY = (
        "QPushButton {"
        "  padding: 8px 24px;"
        "  font-weight: bold;"
        "  background-color: #0e639c;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 4px;"
        "}"
        "QPushButton:hover { background-color: #1177bb; }"
        "QPushButton:disabled { background-color: #3c3c3c; color: #888; }"
    )
    _RUN_STYLE_FULL = (
        "QPushButton {"
        "  padding: 8px 24px;"
        "  font-weight: bold;"
        "  background-color: #b8860b;"
        "  color: white;"
        "  border: none;"
        "  border-radius: 4px;"
        "}"
        "QPushButton:hover { background-color: #cc9a1a; }"
        "QPushButton:disabled { background-color: #3c3c3c; color: #888; }"
    )

    def _update_job_count(self) -> None:
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

        # 更新运行按钮状态
        if self._current_script is not None:
            if running >= JobManager.MAX_CONCURRENT:
                self._run_btn.setText(f"已达上限 ({JobManager.MAX_CONCURRENT})")
                self._run_btn.setStyleSheet(self._RUN_STYLE_FULL)
                self._run_btn.setEnabled(True)  # 仍可点击以显示错误
            else:
                self._run_btn.setText("Run")
                self._run_btn.setStyleSheet(self._RUN_STYLE_READY)
                self._run_btn.setEnabled(True)

    # ── Window Events ─────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[override]
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

    # ── Helpers ────────────────────────────────────────────────

    def _on_file_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        abs_path = item.data(0, FILE_PATH_ROLE)
        if abs_path:
            self._status_bar.showMessage(f"Selected: {abs_path}")

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
            self._status_bar.showMessage(f"已刷新：{n} 个文件，{categories} 个类别", 5000)
        else:
            self._status_bar.showMessage("未找到输出文件。运行脚本以生成数据。", 5000)

    def _rebuild_file_tree(self) -> None:
        # 保存当前排序状态
        sort_col = self._file_tree.sortColumn()
        sort_order = self._file_tree.header().sortIndicatorOrder()
        had_sort = self._file_tree.isSortingEnabled()

        self._file_tree.setSortingEnabled(False)
        self._file_tree.clear()
        categories: dict[str, QTreeWidgetItem] = {}

        # 空状态提示
        if not self._files:
            empty = QTreeWidgetItem(
                self._file_tree,
                ["尚未生成输出文件。运行脚本以生成轨道数据。"],
            )
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = empty.font(0)
            font.setItalic(True)
            empty.setFont(0, font)
            empty.setForeground(0, Qt.GlobalColor.gray)
            self._file_tree.setSortingEnabled(False)
            return

        for fi in self._files:
            if fi.category not in categories:
                cat_item = QTreeWidgetItem(self._file_tree, [fi.category])
                cat_item.setExpanded(True)
                categories[fi.category] = cat_item

            parent = categories[fi.category]
            size_str = format_size(fi.size)
            mod_str = fi.modified.strftime("%Y-%m-%d %H:%M")
            item = QTreeWidgetItem(parent, [fi.name, size_str, mod_str, fi.file_type])
            item.setData(0, FILE_PATH_ROLE, fi.abs_path)
            item.setToolTip(0, fi.abs_path)
            # 存储原始排序键值（UserRole 为 sortByColumn 默认使用的角色）
            item.setData(0, Qt.ItemDataRole.UserRole, fi.name)
            item.setData(1, Qt.ItemDataRole.UserRole, fi.size)
            item.setData(2, Qt.ItemDataRole.UserRole, fi.modified.timestamp())
            item.setData(3, Qt.ItemDataRole.UserRole, fi.file_type)

        self._file_tree.setSortingEnabled(True)
        if had_sort and sort_col >= 0:
            self._file_tree.sortByColumn(sort_col, sort_order)
        else:
            self._file_tree.sortByColumn(2, Qt.SortOrder.DescendingOrder)

        # 自动调整列宽
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

    # ── 参数面板 ───────────────────────────────────────────────

    def _make_cli_widget(self, cli_param: CliParam) -> tuple[str, QWidget]:
        """根据 CliParam 定义创建对应的控件，返回 (key, widget)。

        widget 是用于读取值的原始控件（QLineEdit/QSpinBox 等），
        可能被单位选择器包裹 — 此时返回的 widget 仍是原始控件。
        调用方需用 _display_widget() 获取用于添加到布局的显示 widget。
        """
        key = cli_param.flag.lstrip("-").replace("-", "_")

        if cli_param.param_type == "bool":
            widget: QCheckBox | QLineEdit | QSpinBox | QComboBox = QCheckBox(cli_param.label)
            widget.setToolTip(cli_param.help)
        elif cli_param.param_type == "int":
            widget = QSpinBox()
            widget.setRange(-99999, 99999)
            if cli_param.default:
                widget.setValue(int(cli_param.default))
            widget.setToolTip(cli_param.help)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            widget.setMinimumWidth(80)
        elif cli_param.param_type == "float":
            widget = QLineEdit()
            validator = QDoubleValidator(-99999.0, 99999.0, 15)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            widget.setValidator(validator)
            if cli_param.default:
                widget.setText(cli_param.default)
            widget.setToolTip(cli_param.help)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            widget.setMinimumWidth(100)
        else:  # str
            if cli_param.file_category:
                widget = QComboBox()
                widget.setEditable(True)
                widget.addItem("")
                matching = filter_files(
                    self._files,
                    category=cli_param.file_category,
                    file_type="json",
                )
                for fi in matching:
                    widget.addItem(fi.abs_path)
                if cli_param.default:
                    widget.setCurrentText(cli_param.default)
                widget.setToolTip(cli_param.help)
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                widget.setMinimumWidth(100)
            else:
                widget = QLineEdit()
                if cli_param.default:
                    widget.setText(cli_param.default)
                widget.setToolTip(cli_param.help)
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                widget.setMinimumWidth(100)

        # 带单位的 float 参数：用单位选择器包裹
        if (cli_param.param_type == "float"
                and cli_param.unit_group and cli_param.unit_group in UNIT_GROUPS):
            field_layout = QHBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(4)

            unit_combo = QComboBox()
            unit_combo.addItems(UNIT_GROUPS[cli_param.unit_group].keys())
            unit_combo.setMinimumContentsLength(3)
            unit_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

            # 根据 default_unit 设置默认选中项
            default_idx = 0
            if cli_param.default_unit:
                units = list(UNIT_GROUPS[cli_param.unit_group].keys())
                if cli_param.default_unit in units:
                    default_idx = units.index(cli_param.default_unit)
            unit_combo.setCurrentIndex(default_idx)
            unit_combo.setProperty("prev_idx", default_idx)

            # 如果默认单位不是标准单位，转换显示值
            if default_idx != 0 and cli_param.default:
                try:
                    group = UNIT_GROUPS[cli_param.unit_group]
                    units = list(group.keys())
                    std_val = float(cli_param.default)
                    display_val = std_val / group[units[default_idx]]
                    widget.setText(f"{display_val:.10g}")
                except (ValueError, ZeroDivisionError):
                    pass
            unit_combo.currentIndexChanged.connect(
                lambda _, le=widget, uc=unit_combo, ug=cli_param.unit_group:
                    self._on_unit_changed(le, uc, ug)
            )

            field_layout.addWidget(widget)
            field_layout.addWidget(unit_combo)

            self._unit_combos[widget] = unit_combo
            self._unit_groups[widget] = cli_param.unit_group

            wrapper = QWidget()
            wrapper.setLayout(field_layout)
            self._wrapped_widgets[widget] = wrapper

        return key, widget

    def _display_widget(self, widget: QWidget) -> QWidget:
        """返回用于添加到布局的 widget（可能已被单位选择器包裹）。"""
        return self._wrapped_widgets.get(widget, widget)

    def _set_widget_std_value(self, widget: QWidget, std_val_str: str) -> None:
        """将标准单位值设置到控件（带单位的 QLineEdit 会自动转换到当前显示单位）。"""
        if isinstance(widget, QCheckBox):
            widget.setChecked(std_val_str.lower() == "true")
        elif isinstance(widget, QSpinBox):
            if std_val_str:
                widget.setValue(int(float(std_val_str)))
        elif isinstance(widget, QLineEdit):
            if widget in self._unit_combos and std_val_str:
                combo = self._unit_combos[widget]
                group = UNIT_GROUPS[self._unit_groups[widget]]
                units = list(group.keys())
                try:
                    std_val = float(std_val_str)
                    display_val = std_val / group[units[combo.currentIndex()]]
                    widget.setText(f"{display_val:.10g}")
                except (ValueError, ZeroDivisionError):
                    widget.setText(std_val_str)
            else:
                widget.setText(std_val_str)
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(std_val_str)

    def _add_cli_param_row(self, cli_param: CliParam) -> None:
        """创建控件并添加到参数面板的当前表单布局中。"""
        key, widget = self._make_cli_widget(cli_param)
        display = self._display_widget(widget)
        self._cli_widgets[key] = widget
        self._param_defaults[widget] = cli_param.default or ""
        self._connect_param_highlight(widget)

        if cli_param.param_type == "bool":
            self._params_layout.addRow(display)
        else:
            self._params_layout.addRow(f"{cli_param.label}:", display)

    def _connect_param_highlight(self, widget: QWidget) -> None:
        """连接控件值变化信号到默认值高亮更新。"""
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(
                lambda _, w=widget: self._update_param_highlight(w)
            )
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(
                lambda _, w=widget: self._update_param_highlight(w)
            )
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(
                lambda _, w=widget: self._update_param_highlight(w)
            )

    def _rebuild_params_panel(self, entry: ScriptEntry) -> None:
        """根据选中的脚本重建运行参数面板。"""
        # 清空旧控件
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        self._env_widgets.clear()
        self._cli_widgets.clear()
        self._param_defaults.clear()
        self._unit_combos.clear()
        self._unit_groups.clear()
        self._wrapped_widgets.clear()

        self._params_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._params_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        title = QLabel(entry.name)
        title.setStyleSheet("font-size: 15px; font-weight: bold; padding: 4px 0;")
        self._params_layout.addRow(title)

        if entry.description:
            desc_label = QLabel(entry.description)
            desc_label.setStyleSheet("color: #555; font-size: 11px; padding: 0 0 8px 0;")
            desc_label.setWordWrap(True)
            self._params_layout.addRow(desc_label)

        cmd_label = QLabel(f"python {entry.script_path}")
        cmd_label.setStyleSheet(
            "font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Liberation Mono', monospace; "
            "font-size: 9pt; color: #666; background-color: #f5f5f5; "
            "padding: 4px 6px; border-radius: 3px;"
        )
        cmd_label.setWordWrap(True)
        cmd_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._params_layout.addRow("命令:", cmd_label)

        if entry.output_dir:
            out_label = QLabel(entry.output_dir)
            out_label.setStyleSheet(
                "font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Liberation Mono', monospace; "
                "font-size: 9pt; color: #666; background-color: #f5f5f5; "
                "padding: 4px 6px; border-radius: 3px;"
            )
            out_label.setWordWrap(True)
            out_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._params_layout.addRow("输出目录:", out_label)

        # 分隔线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("margin: 4px 0 8px 0;")
        self._params_layout.addRow(divider)

        has_any = False

        # 环境变量参数（文件选择下拉框）
        if entry.env_params:
            section_label = QLabel("数据文件")
            section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
            self._params_layout.addRow(section_label)

            for key, env_param in entry.env_params.items():
                combo = QComboBox()
                combo.addItem("（使用脚本默认值）", None)

                # 填充对应类别的文件
                matching = filter_files(self._files, category=env_param.file_category, file_type=env_param.file_type)
                for fi in matching:
                    combo.addItem(fi.name, fi.abs_path)

                combo.setToolTip(env_param.env_var)
                combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                combo.setMinimumWidth(100)
                self._params_layout.addRow(f"{env_param.label}:", combo)
                self._env_widgets[key] = combo

            has_any = True

        # 命令行参数
        if entry.cli_params:
            regular_params = [p for p in entry.cli_params if not p.advanced]
            advanced_params = [p for p in entry.cli_params if p.advanced]

            if regular_params:
                section_label = QLabel("运行参数")
                section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
                self._params_layout.addRow(section_label)

                for cli_param in regular_params:
                    self._add_cli_param_row(cli_param)

            if advanced_params:
                adv_group = QGroupBox("高级选项")
                adv_group.setCheckable(True)
                adv_group.setChecked(False)
                adv_layout = QFormLayout()
                adv_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                adv_layout.setFieldGrowthPolicy(
                    QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
                )

                for cli_param in advanced_params:
                    key, widget = self._make_cli_widget(cli_param)
                    display = self._display_widget(widget)
                    self._cli_widgets[key] = widget
                    self._param_defaults[widget] = cli_param.default or ""
                    self._connect_param_highlight(widget)

                    if cli_param.param_type == "bool":
                        adv_layout.addRow(display)
                    else:
                        adv_layout.addRow(f"{cli_param.label}:", display)

                adv_group.setLayout(adv_layout)
                self._params_layout.addRow(adv_group)

            has_any = True

        # 应用用户保存的自定义默认值（存储为标准单位）
        saved = self._gui_defaults.get(entry.name, {})
        if saved:
            for key, widget in self._cli_widgets.items():
                cli_param = self._find_cli_param(key)
                if cli_param is None or cli_param.flag not in saved:
                    continue
                val = saved[cli_param.flag]
                self._set_widget_std_value(widget, val)
                self._param_defaults[widget] = val

        # 保存/恢复默认值按钮
        if has_any:
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 8, 0, 0)
            save_btn = QPushButton("保存为默认值")
            save_btn.setToolTip("将当前参数值保存为此脚本的默认值")
            save_btn.clicked.connect(self._on_save_defaults)
            reset_btn = QPushButton("恢复出厂默认")
            reset_btn.setToolTip("恢复为系统预设的默认参数值")
            reset_btn.clicked.connect(self._on_reset_defaults)
            btn_layout.addWidget(save_btn)
            btn_layout.addWidget(reset_btn)
            btn_layout.addStretch()
            btn_wrapper = QWidget()
            btn_wrapper.setLayout(btn_layout)
            self._params_layout.addRow(btn_wrapper)

        if not has_any:
            label = QLabel("此脚本无可配置参数")
            label.setStyleSheet("color: #999; font-style: italic;")
            self._params_layout.addRow(label)
