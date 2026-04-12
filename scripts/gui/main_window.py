"""主窗口 — GUI 布局和交互逻辑。"""

from __future__ import annotations

import platform
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
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
from scripts.gui.process_runner import ScriptRunner
from scripts.gui.script_registry import SCRIPTS, CliParam, EnvParam, ScriptEntry


class MainWindow(QMainWindow):
    def __init__(self, repo_root: str, parent=None):
        super().__init__(parent)
        self._repo_root = Path(repo_root)
        self._current_script: ScriptEntry | None = None
        self._files: list[FileInfo] = []

        self.setWindowTitle("Transfer Orbit Design")
        self.resize(1200, 800)

        self._runner = ScriptRunner(repo_root, self)
        self._runner.output_received.connect(self._append_output)
        self._runner.script_started.connect(self._on_script_started)
        self._runner.script_finished.connect(self._on_script_finished)
        self._runner.script_error.connect(self._on_script_error)

        self._build_toolbar()
        self._build_central()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        self._refresh_files()

    # ── Toolbar ────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._run_btn = QPushButton("Run")
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run)
        toolbar.addWidget(self._run_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        toolbar.addWidget(self._stop_btn)

        toolbar.addSeparator()

        refresh_btn = QPushButton("Refresh Files")
        refresh_btn.clicked.connect(self._refresh_files)
        toolbar.addWidget(refresh_btn)

        clear_btn = QPushButton("Clear Output")
        clear_btn.clicked.connect(self._clear_output)
        toolbar.addWidget(clear_btn)

    # ── Central Widget ─────────────────────────────────────────

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Upper area: left buttons + right tabs
        upper = QSplitter(Qt.Orientation.Horizontal)

        upper.addWidget(self._build_left_panel())
        upper.addWidget(self._build_right_panel())
        upper.setStretchFactor(0, 1)
        upper.setStretchFactor(1, 2)

        # Output console
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(20000)
        font = self._output.font()
        font.setFamily(
            "Consolas"
            if platform.system() == "Windows"
            else "Menlo"
            if platform.system() == "Darwin"
            else "Monospace"
        )
        font.setPointSize(9)
        self._output.setFont(font)
        self._output.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )

        splitter.addWidget(upper)
        splitter.addWidget(self._output)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

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

        # Tab 1: Script Info
        info_widget = QWidget()
        info_layout = QFormLayout(info_widget)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(8)

        self._info_name = QLabel("(未选择)")
        self._info_name.setWordWrap(True)
        self._info_desc = QLabel()
        self._info_desc.setWordWrap(True)
        self._info_cmd = QLabel()
        self._info_cmd.setWordWrap(True)
        self._info_cmd.setStyleSheet("font-family: Consolas, Monospace; font-size: 9pt;")
        self._info_output_dir = QLabel()
        self._info_status = QLabel("idle")

        info_layout.addRow("名称:", self._info_name)
        info_layout.addRow("描述:", self._info_desc)
        info_layout.addRow("命令:", self._info_cmd)
        info_layout.addRow("输出目录:", self._info_output_dir)
        info_layout.addRow("状态:", self._info_status)

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
        self._cli_widgets: dict[str, QCheckBox | QLineEdit | QSpinBox] = {}

        tabs.addTab(self._params_scroll, "运行参数")

        # Tab 3: File Browser
        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels(["Filename", "Size", "Modified", "Type"])
        self._file_tree.setAlternatingRowColors(True)
        self._file_tree.setRootIsDecorated(True)
        self._file_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        tabs.addTab(self._file_tree, "Files")

        return tabs

    # ── Slots ──────────────────────────────────────────────────

    def _on_script_selected(self, entry: ScriptEntry) -> None:
        self._current_script = entry
        self._info_name.setText(entry.name)
        self._info_desc.setText(entry.description)
        self._info_cmd.setText(f"python {entry.script_path}")
        self._info_output_dir.setText(entry.output_dir or "—")

        if not self._runner.is_running():
            self._run_btn.setEnabled(True)

        # 高亮关联的输出目录
        if entry.output_dir:
            self._highlight_category(Path(entry.output_dir).name)

        # 重建参数面板
        self._rebuild_params_panel(entry)

    def _on_run(self) -> None:
        if self._current_script is None:
            return
        if self._runner.is_running():
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

        # 如果脚本支持 --file 且用户在文件树中选中了文件
        if self._current_script.accepts_file_arg:
            selected = self._file_tree.currentItem()
            if selected:
                abs_path = selected.data(0, Qt.ItemDataRole.UserRole)
                if abs_path:
                    extra_args = ["--file", abs_path] + extra_args

        self._runner.run(self._current_script, extra_args, env_overrides)

    def _on_stop(self) -> None:
        self._runner.stop()

    def _on_script_started(self, name: str) -> None:
        self._run_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._info_status.setText("running")
        self._status_bar.showMessage(f"Running: {name}...")
        assert self._current_script is not None
        self._append_output(f"\n{'='*60}\n> python {self._current_script.script_path}\n{'='*60}\n")

    def _on_script_finished(self, name: str, exit_code: int) -> None:
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        status = "completed" if exit_code == 0 else f"error (exit {exit_code})"
        self._info_status.setText(status)
        self._status_bar.showMessage(f"Done: {name} (exit code {exit_code})")
        self._append_output(f"\n{'='*60}\n[进程结束] exit code: {exit_code}\n{'='*60}\n")

    def _on_script_error(self, msg: str) -> None:
        self._run_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._info_status.setText("error")
        self._status_bar.showMessage("Error")
        self._append_output(f"\n[ERROR] {msg}\n")

    def _on_file_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        abs_path = item.data(0, Qt.ItemDataRole.UserRole)
        if abs_path:
            self._append_output(f"[选中文件] {abs_path}\n")

    # ── Window Events ─────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._runner.is_running():
            self._runner.stop()
        super().closeEvent(event)

    # ── Helpers ────────────────────────────────────────────────

    def _append_output(self, text: str) -> None:
        self._output.moveCursor(self._output.textCursor().MoveOperation.End)
        self._output.insertPlainText(text)
        self._output.moveCursor(self._output.textCursor().MoveOperation.End)

    def _clear_output(self) -> None:
        self._output.clear()

    def _refresh_files(self) -> None:
        self._files = discover_files(self._repo_root)
        self._rebuild_file_tree()
        # 刷新参数面板中的文件下拉框
        if self._current_script:
            self._rebuild_params_panel(self._current_script)

    def _rebuild_file_tree(self) -> None:
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
            item.setData(0, Qt.ItemDataRole.UserRole, fi.abs_path)
            item.setToolTip(0, fi.abs_path)

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
                    widget: QCheckBox | QLineEdit | QSpinBox = QCheckBox(cli_param.label)
                    widget.setToolTip(cli_param.help)
                elif cli_param.param_type == "int":
                    widget = QSpinBox()
                    widget.setRange(-99999, 99999)
                    if cli_param.default:
                        widget.setValue(int(cli_param.default))
                    widget.setToolTip(cli_param.help)
                elif cli_param.param_type == "float":
                    widget = QLineEdit()
                    validator = QDoubleValidator(-99999.0, 99999.0, 15)
                    validator.setNotation(QDoubleValidator.Notation.StandardNotation)
                    widget.setValidator(validator)
                    if cli_param.default:
                        widget.setText(cli_param.default)
                    widget.setToolTip(cli_param.help)
                else:  # str
                    widget = QLineEdit()
                    if cli_param.default:
                        widget.setText(cli_param.default)
                    widget.setToolTip(cli_param.help)

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
