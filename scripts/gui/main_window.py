"""主窗口 — GUI 布局和交互逻辑（多进程 Job 版本）。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
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
from scripts.gui.script_registry import SCRIPTS, CliParam, EnvParam, ScriptEntry

FILE_PATH_ROLE = Qt.ItemDataRole.UserRole + 1


class MainWindow(QMainWindow):
    def __init__(self, repo_root: str, parent=None):
        super().__init__(parent)
        self._repo_root = Path(repo_root)
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

        for category, scripts in SCRIPTS.items():
            header = QLabel(category)
            header.setStyleSheet(
                "font-weight: bold; font-size: 13px; "
                "padding: 8px 4px 4px 4px; color: #555;"
            )
            layout.addWidget(header)

            for entry in scripts:
                btn = QPushButton(entry.name)
                btn.setToolTip(entry.description)
                btn.setStyleSheet(
                    "QPushButton { text-align: left; padding: 4px 8px; }"
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

        # Tab 1: Script Info（含 Run 按钮）
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)

        self._info_name = QLabel("(未选择)")
        self._info_name.setWordWrap(True)
        self._info_desc = QLabel()
        self._info_desc.setWordWrap(True)
        self._info_cmd = QLabel()
        self._info_cmd.setWordWrap(True)
        self._info_cmd.setStyleSheet("font-family: Consolas, Monospace; font-size: 9pt;")
        self._info_output_dir = QLabel()

        form.addRow("名称:", self._info_name)
        form.addRow("描述:", self._info_desc)
        form.addRow("命令:", self._info_cmd)
        form.addRow("输出目录:", self._info_output_dir)

        info_layout.addLayout(form)

        # Run 按钮放在表单下方
        self._run_btn = QPushButton("Run")
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run)
        self._run_btn.setStyleSheet(
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
        info_layout.addWidget(self._run_btn)
        info_layout.addStretch()

        tabs.addTab(info_widget, "Script Info")

        # Tab 2: 运行参数
        self._params_scroll = QScrollArea()
        self._params_scroll.setWidgetResizable(True)
        self._params_container = QWidget()
        self._params_layout = QFormLayout(self._params_container)
        self._params_layout.setContentsMargins(12, 12, 12, 12)
        self._params_layout.setSpacing(8)
        self._params_scroll.setWidget(self._params_container)

        self._env_widgets: dict[str, QComboBox] = {}
        self._cli_widgets: dict[str, QCheckBox | QLineEdit | QSpinBox | QComboBox] = {}

        tabs.addTab(self._params_scroll, "运行参数")

        # Tab 3: File Browser
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
        self._info_name.setText(entry.name)
        self._info_desc.setText(entry.description)
        self._info_cmd.setText(f"python {entry.script_path}")
        self._info_output_dir.setText(entry.output_dir or "—")
        self._run_btn.setEnabled(True)

        # 高亮关联的输出目录
        if entry.output_dir:
            self._highlight_category(Path(entry.output_dir).name)

        # 重建参数面板
        self._rebuild_params_panel(entry)

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
            cli_param = None
            for p in self._current_script.cli_params:
                if p.flag.lstrip("-").replace("-", "_") == key:
                    cli_param = p
                    break
            if cli_param is None:
                continue

            if isinstance(widget, QCheckBox):
                if widget.isChecked():
                    extra_args.append(cli_param.flag)
            elif isinstance(widget, QSpinBox):
                val = widget.value()
                default = cli_param.default
                if default:
                    if abs(val - float(default)) > 1e-9:
                        extra_args.extend([cli_param.flag, str(val)])
                elif abs(val) > 1e-9:
                    extra_args.extend([cli_param.flag, str(val)])
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                default = cli_param.default
                if text and text != default:
                    extra_args.extend([cli_param.flag, text])
            elif isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                default = cli_param.default
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

        self._job_manager.start_job(self._current_script, extra_args, env_overrides)

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
        self._job_outputs[job_id] = output_widget
        tab_idx = self._output_tabs.addTab(output_widget, name)
        self._output_tabs.setCurrentIndex(tab_idx)

        # 创建 Job Card
        card = JobCard(job_id, name)
        card.clicked.connect(self._on_job_card_clicked)
        card.stop_requested.connect(self._job_manager.stop_job)
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

        # 在输出面板追加结束信息
        output = self._job_outputs.get(job_id)
        if output:
            banner = f"\n{'='*60}\n[进程结束] exit code: {exit_code}\n{'='*60}\n"
            output.append_output(banner, "stdout")

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
                self._job_manager.stop_job(job_id)
                break

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
            # 如果 job 还在运行，先停止
            job = self._job_manager.get_job(job_id_to_remove)
            if job and job.status == "running":
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

    # ── Window Events ─────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[override]
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

    def _rebuild_file_tree(self) -> None:
        # 保存当前排序状态
        sort_col = self._file_tree.sortColumn()
        sort_order = self._file_tree.header().sortIndicatorOrder()
        had_sort = self._file_tree.isSortingEnabled()

        self._file_tree.setSortingEnabled(False)
        self._file_tree.clear()
        categories: dict[str, QTreeWidgetItem] = {}

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

    def _rebuild_params_panel(self, entry: ScriptEntry) -> None:
        """根据选中的脚本重建运行参数面板。"""
        # 清空旧控件
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        self._env_widgets.clear()
        self._cli_widgets.clear()

        self._params_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._params_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

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
            section_label = QLabel("命令行选项")
            section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
            self._params_layout.addRow(section_label)

            for cli_param in entry.cli_params:
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

                if cli_param.param_type == "bool":
                    self._params_layout.addRow(widget)
                else:
                    self._params_layout.addRow(f"{cli_param.label}:", widget)

                self._cli_widgets[key] = widget

            has_any = True

        if not has_any:
            label = QLabel("此脚本无可配置参数")
            label.setStyleSheet("color: #999; font-style: italic;")
            self._params_layout.addRow(label)
