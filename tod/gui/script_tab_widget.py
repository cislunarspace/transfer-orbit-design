"""自包含的脚本参数面板，每个打开的脚本对应一个 ScriptTabWidget 实例。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import QCoreApplication, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tod.gui.cli_widget_factory import CliWidgetFactory
from tod.gui.doc_link_mixin import make_doc_link_label
from tod.gui.file_discovery import FileInfo, filter_files
from tod.gui.script_registry import (
    UNIT_GROUPS,
    CliParam,
    MultiCliParam,
    ScriptEntry,
)
from tod.gui.theme_utils import resolve_theme as _resolve_theme

if TYPE_CHECKING:
    from tod.gui.script_registry import CliChipParam


class ScriptTabWidget(QWidget):
    """单个脚本的完整参数面板：标题、描述、参数控件、运行按钮。

    每个实例独立持有 CliWidgetFactory、全部控件 dicts 和默认值，
    切换 tab 时通过 show/hide 保留全部运行时状态。
    """

    run_requested = pyqtSignal()
    doc_link_clicked = pyqtSignal(str)
    doc_link_missing = pyqtSignal(str)  # 文档未构建时发出警告消息
    status_message = pyqtSignal(str, int)  # (message, timeout_ms)
    copy_path_requested = pyqtSignal(str, QWidget)  # (path, target_btn)
    defaults_changed = pyqtSignal()  # 保存/恢复默认值后通知持久化

    _PARAM_BORDER_MODIFIED = "border: 1px solid #4da6ff;"

    def __init__(
        self,
        entry: ScriptEntry,
        files: list[FileInfo],
        repo_root: Path,
        gui_defaults: dict[str, Any],
        theme_mode: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.entry = entry
        self._files = files
        self._repo_root = repo_root
        self._gui_defaults = gui_defaults
        self._theme_mode = theme_mode

        self._cli_widgets: dict[str, QWidget] = {}
        self._env_widgets: dict[str, QComboBox] = {}
        self._chip_widgets: dict[str, QWidget] = {}
        self._multi_file_widgets: dict[str, QWidget] = {}
        self._param_defaults: dict[QWidget, str] = {}
        self._factory_defaults: dict[QWidget, str] = {}
        self._cli_row_containers: dict[str, QWidget] = {}
        self._cli_row_labels: dict[str, QWidget] = {}

        self._widget_factory = CliWidgetFactory(
            files=self._files,
            on_path_mode_changed=self._on_path_mode_changed,
            on_unit_changed=self._on_unit_changed,
        )

        self._setup_ui()

    # ── UI 构建 ───────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._params_container = QWidget()
        self._params_layout = QFormLayout(self._params_container)
        self._params_layout.setContentsMargins(12, 12, 12, 12)
        self._params_layout.setSpacing(8)
        scroll.setWidget(self._params_container)
        self._scroll_area = scroll

        layout.addWidget(scroll, stretch=1)

        self._run_btn = QPushButton(self.tr("运行"))
        self._run_btn.setEnabled(True)
        self._run_btn.clicked.connect(self._on_run_clicked)
        self._run_btn.setStyleSheet(self._RUN_STYLE_READY)
        self._run_btn.setMinimumHeight(36)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        btn_layout.addWidget(self._run_btn)
        layout.addWidget(btn_container)

        self._build_params()

    def _build_params(self) -> None:
        entry = self.entry
        self._params_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._params_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # 标题（可点击文档链接）
        doc_url = self._get_doc_url(entry.script_path)
        title = make_doc_link_label(entry.name, doc_url)
        title.clicked.connect(lambda du=doc_url: self._on_doc_link_clicked(du))
        self._params_layout.addRow(title)

        # 描述
        if entry.description:
            desc_label = QLabel(entry.description)
            if _resolve_theme(self._theme_mode) == "dark":
                desc_label.setStyleSheet(
                    "font-size: 12px; padding: 6px 10px; border-radius: 4px; "
                    "color: #aaaaaa; background-color: #252525;"
                )
            else:
                desc_label.setStyleSheet(
                    "font-size: 12px; padding: 6px 10px; border-radius: 4px; "
                    "color: #444444; background-color: #f0f0f0;"
                )
            desc_label.setWordWrap(True)
            self._params_layout.addRow(desc_label)

        # 命令行
        self._add_command_row(entry)

        # 输出目录
        if entry.output_dir:
            self._add_output_dir_row(entry)

        # 分隔线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("margin: 4px 0 8px 0;")
        self._params_layout.addRow(divider)

        has_any = False

        # 芯片参数
        if entry.cli_chip_params:
            for chip_param in entry.cli_chip_params:
                key, widget = self._widget_factory.make_chip_widget(chip_param)
                self._chip_widgets[key] = widget
                self._params_layout.addRow(f"{chip_param.label}:", widget)
            has_any = True

        # 多文件参数
        if entry.multi_cli_params:
            for multi_param in entry.multi_cli_params:
                self._add_multi_file_param(multi_param)
            has_any = True

        # 环境变量参数
        if entry.env_params:
            section_label = QLabel(self.tr("数据文件"))
            section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
            self._params_layout.addRow(section_label)
            for key, env_param in entry.env_params.items():
                self._add_env_param(key, env_param)
            has_any = True

        # 命令行参数
        if entry.cli_params:
            regular = [p for p in entry.cli_params if not p.advanced]
            advanced = [p for p in entry.cli_params if p.advanced]

            if regular:
                section_label = QLabel(self.tr("运行参数"))
                section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
                self._params_layout.addRow(section_label)
                for p in regular:
                    self._add_cli_param_row(p)

            if advanced:
                self._add_advanced_group(advanced)

            has_any = True

        # 用户保存的默认值
        saved = self._gui_defaults.get(entry.name, {})
        if saved:
            for key, widget in self._cli_widgets.items():
                cli_param = self._find_cli_param(key)
                if cli_param is None or cli_param.flag not in saved:
                    continue
                val = saved[cli_param.flag]
                self._set_widget_std_value(widget, val)
                self._param_defaults[widget] = val

        # 条件可见性
        self._setup_conditional_visibility(entry)

        # 保存/恢复按钮
        if has_any:
            self._add_defaults_buttons()

        if not has_any:
            label = QLabel(self.tr("此脚本无可配置参数"))
            label.setStyleSheet("color: #999; font-style: italic;")
            self._params_layout.addRow(label)

    def _add_command_row(self, entry: ScriptEntry) -> None:
        cmd_label = QLabel(f"python {entry.script_path}")
        if _resolve_theme(self._theme_mode) == "dark":
            cmd_bg, cmd_color, cmd_accent = "#2d2d2d", "#bbbbbb", "#4da6ff"
        else:
            cmd_bg, cmd_color, cmd_accent = "#e8e8e8", "#333333", "#1976d2"

        cmd_label.setStyleSheet(
            f"font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', "
            f"'Liberation Mono', monospace; font-size: 9pt; color: {cmd_color}; "
            f"background-color: {cmd_bg}; padding: 6px 10px; border-radius: 4px; "
            f"border-left: 3px solid {cmd_accent};"
        )
        cmd_label.setWordWrap(False)
        cmd_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        abs_cmd_path = str(self._repo_root / entry.script_path)

        cmd_abs_btn = QPushButton(self.tr("复制路径"))
        cmd_abs_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_abs_btn.clicked.connect(
            lambda _, p=abs_cmd_path, b=cmd_abs_btn: self.copy_path_requested.emit(p, b)
        )

        cmd_rel_btn = QPushButton(self.tr("复制相对路径"))
        cmd_rel_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_rel_btn.clicked.connect(
            lambda _, p=entry.script_path, b=cmd_rel_btn: self.copy_path_requested.emit(p, b)
        )

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row_layout.addWidget(cmd_label)
        row_layout.addWidget(cmd_abs_btn)
        row_layout.addWidget(cmd_rel_btn)
        row_layout.addStretch()

        self._params_layout.addRow(self.tr("命令:"), row)

    def _add_output_dir_row(self, entry: ScriptEntry) -> None:
        out_label = QLabel(entry.output_dir)
        if _resolve_theme(self._theme_mode) == "dark":
            out_bg, out_color, out_accent = "#2d2d2d", "#bbbbbb", "#4caf50"
        else:
            out_bg, out_color, out_accent = "#e8e8e8", "#333333", "#388e3c"

        out_label.setStyleSheet(
            f"font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', "
            f"'Liberation Mono', monospace; font-size: 9pt; color: {out_color}; "
            f"background-color: {out_bg}; padding: 6px 10px; border-radius: 4px; "
            f"border-left: 3px solid {out_accent};"
        )
        out_label.setWordWrap(False)
        out_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        abs_out_path = str(self._repo_root / entry.output_dir)

        out_abs_btn = QPushButton(self.tr("复制路径"))
        out_abs_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        out_abs_btn.clicked.connect(
            lambda _, p=abs_out_path, b=out_abs_btn: self.copy_path_requested.emit(p, b)
        )

        out_rel_btn = QPushButton(self.tr("复制相对路径"))
        out_rel_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        out_rel_btn.clicked.connect(
            lambda _, p=entry.output_dir, b=out_rel_btn: self.copy_path_requested.emit(p, b)
        )

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row_layout.addWidget(out_label)
        row_layout.addWidget(out_abs_btn)
        row_layout.addWidget(out_rel_btn)
        row_layout.addStretch()

        self._params_layout.addRow(self.tr("输出目录:"), row)

    def _add_env_param(self, key: str, env_param) -> None:
        combo = QComboBox()
        combo.addItem(self.tr("（使用脚本默认值）"), None)
        matching = filter_files(
            self._files,
            category=env_param.file_category,
            file_type=env_param.file_type,
            name_pattern=env_param.name_pattern,
        )
        for fi in matching:
            combo.addItem(fi.name, fi.abs_path)
        combo.setToolTip(env_param.env_var)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setMinimumWidth(100)
        self._params_layout.addRow(f"{env_param.label}:", combo)
        self._env_widgets[key] = combo

    def _add_cli_param_row(self, cli_param: CliParam) -> None:
        key, widget = self._widget_factory.make_widget(cli_param)
        display = self._widget_factory.display_widget(widget)
        self._cli_widgets[key] = widget
        self._param_defaults[widget] = cli_param.default or ""
        self._factory_defaults[widget] = cli_param.default or ""
        self._connect_param_highlight(widget)

        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(display)
        self._cli_row_containers[key] = row_container

        if cli_param.param_type == "bool":
            self._params_layout.addRow(row_container)
        else:
            self._params_layout.addRow(f"{cli_param.label}:", row_container)
            label = self._params_layout.labelForField(row_container)
            if label is not None:
                self._cli_row_labels[key] = label

    def _add_advanced_group(self, advanced_params: list[CliParam]) -> None:
        adv_group = QGroupBox(self.tr("高级选项"))
        adv_group.setCheckable(True)
        adv_group.setChecked(False)
        adv_layout = QFormLayout()
        adv_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        adv_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        for cli_param in advanced_params:
            key, widget = self._widget_factory.make_widget(cli_param)
            display = self._widget_factory.display_widget(widget)
            self._cli_widgets[key] = widget
            self._param_defaults[widget] = cli_param.default or ""
            self._factory_defaults[widget] = cli_param.default or ""
            self._connect_param_highlight(widget)

            row_container = QWidget()
            row_layout = QHBoxLayout(row_container)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(display)
            self._cli_row_containers[key] = row_container

            if cli_param.param_type == "bool":
                adv_layout.addRow(row_container)
            else:
                adv_layout.addRow(f"{cli_param.label}:", row_container)
                label = adv_layout.labelForField(row_container)
                if label is not None:
                    self._cli_row_labels[key] = label

        adv_group.setLayout(adv_layout)
        self._params_layout.addRow(adv_group)

    def _add_multi_file_param(self, multi_param: MultiCliParam) -> None:
        """创建多文件参数控件（表格，每行含文件名 + per-file 字段）。"""
        key, widget = self._widget_factory.make_multi_file_widget(
            multi_param, str(self._repo_root)
        )
        self._multi_file_widgets[key] = widget

        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(widget)
        self._cli_row_containers[key] = row_container

        self._params_layout.addRow(f"{multi_param.label}:", row_container)
        label = self._params_layout.labelForField(row_container)
        if label is not None:
            self._cli_row_labels[key] = label

    def _add_defaults_buttons(self) -> None:
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)
        save_btn = QPushButton(self.tr("保存为默认值"))
        save_btn.clicked.connect(self._on_save_defaults)
        reset_btn = QPushButton(self.tr("恢复出厂默认"))
        reset_btn.clicked.connect(self._on_reset_defaults)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        wrapper = QWidget()
        wrapper.setLayout(btn_layout)
        self._params_layout.addRow(wrapper)

    # ── 参数查找 ───────────────────────────────────────────────

    def _find_cli_param(self, key: str) -> CliParam | None:
        for p in self.entry.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None

    # ── 单位转换 ───────────────────────────────────────────────

    def _to_standard_unit(self, line_edit: QLineEdit) -> str:
        text = line_edit.text().strip()
        if not text:
            return text
        group_name = self._widget_factory.unit_groups.get(line_edit)
        if not group_name:
            return text
        unit_combo = self._widget_factory.unit_combos.get(line_edit)
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
        standard = value * group[units[old_idx]]
        new_value = standard / group[units[new_idx]]
        line_edit.setText(f"{new_value:.10g}")
        combo.setProperty("prev_idx", new_idx)

    def _set_widget_std_value(self, widget: QWidget, std_val_str: str) -> None:
        if isinstance(widget, QCheckBox):
            widget.setChecked(std_val_str.lower() == "true")
        elif isinstance(widget, QSpinBox):
            if std_val_str:
                widget.setValue(int(float(std_val_str)))
        elif isinstance(widget, QLineEdit):
            if widget in self._widget_factory.unit_combos and std_val_str:
                combo = self._widget_factory.unit_combos[widget]
                group = UNIT_GROUPS[self._widget_factory.unit_groups[widget]]
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
            cli_param = None
            for k, w in self._cli_widgets.items():
                if w is widget:
                    cli_param = self._find_cli_param(k)
                    break
            if widget in self._widget_factory.path_mode_toggles and std_val_str.startswith("{"):
                try:
                    data = json.loads(std_val_str)
                    mode_combo = self._widget_factory.path_mode_toggles[widget]
                    mode_combo.blockSignals(True)
                    mode_combo.setCurrentIndex(1 if data.get("mode") == "relative" else 0)
                    mode_combo.blockSignals(False)
                    self._on_path_mode_changed(widget, mode_combo)
                    widget.setCurrentText(data.get("path", ""))
                    return
                except (json.JSONDecodeError, KeyError):
                    pass
            if cli_param and cli_param.choice_values:
                reverse = {v: k for k, v in cli_param.choice_values.items()}
                if std_val_str in reverse:
                    std_val_str = reverse[std_val_str]
            widget.setCurrentText(std_val_str)

    # ── 路径模式 ───────────────────────────────────────────────

    def _on_path_mode_changed(self, file_combo: QComboBox, mode_combo: QComboBox) -> None:
        file_category = mode_combo.property("file_category") or ""
        name_pattern = mode_combo.property("name_pattern") or None
        is_relative = mode_combo.currentIndex() == 1
        current_text = file_combo.currentText()
        file_combo.blockSignals(True)
        file_combo.clear()
        file_combo.addItem("")
        matching = filter_files(self._files, category=file_category, file_type="json", name_pattern=name_pattern)
        for fi in matching:
            file_combo.addItem(fi.path if is_relative else fi.abs_path)
        if current_text:
            idx = file_combo.findText(current_text)
            if idx >= 0:
                file_combo.setCurrentIndex(idx)
            else:
                file_combo.setEditText(current_text)
        file_combo.blockSignals(False)

    # ── 条件可见性 ─────────────────────────────────────────────

    def _setup_conditional_visibility(self, entry: ScriptEntry) -> None:
        hidden_map: dict[str, list[tuple[str, str | None]]] = {}
        for p in entry.cli_params:
            if p.hidden_when:
                raw = p.hidden_when
                expected_value: str | None = None
                if "==" in raw:
                    raw, expected_value = raw.split("==", 1)
                trigger_key = raw.lstrip("-").replace("-", "_")
                target_key = p.flag.lstrip("-").replace("-", "_")
                hidden_map.setdefault(trigger_key, []).append((target_key, expected_value))

        for trigger_key, targets in hidden_map.items():
            trigger_widget = self._cli_widgets.get(trigger_key)
            if trigger_widget is None:
                continue

            trigger_param = self._find_cli_param(trigger_key)

            def _get_trigger_value(tw=trigger_widget, tp=trigger_param) -> str:
                if isinstance(tw, QCheckBox):
                    return str(tw.isChecked())
                if isinstance(tw, QComboBox):
                    text = tw.currentText().strip()
                    if tp and tp.choice_values and text in tp.choice_values:
                        return tp.choice_values[text]
                    return text
                if isinstance(tw, QLineEdit):
                    return tw.text().strip()
                if isinstance(tw, QSpinBox):
                    return str(tw.value())
                return ""

            def update_visibility(_=None, tw=trigger_widget, tgts=targets):
                current_val = _get_trigger_value()
                for tk, expected in tgts:
                    if expected is not None:
                        should_hide = current_val == expected
                    else:
                        if isinstance(tw, QCheckBox):
                            should_hide = tw.isChecked()
                        else:
                            should_hide = bool(current_val)
                    container = self._cli_row_containers.get(tk)
                    if container is not None:
                        container.setVisible(not should_hide)
                        label = self._cli_row_labels.get(tk)
                        if label is not None:
                            label.setVisible(not should_hide)

            if isinstance(trigger_widget, QComboBox):
                trigger_widget.currentTextChanged.connect(update_visibility)
            elif isinstance(trigger_widget, QLineEdit):
                trigger_widget.textChanged.connect(update_visibility)
            elif isinstance(trigger_widget, QCheckBox):
                trigger_widget.stateChanged.connect(update_visibility)

            update_visibility()

    # ── 参数高亮 ───────────────────────────────────────────────

    def _connect_param_highlight(self, widget: QWidget) -> None:
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _, w=widget: self._update_param_highlight(w))
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(lambda _, w=widget: self._update_param_highlight(w))
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(lambda _, w=widget: self._update_param_highlight(w))

    def _update_param_highlight(self, widget: QWidget) -> None:
        default = self._param_defaults.get(widget, "")
        if isinstance(widget, QLineEdit):
            current = widget.text().strip()
        elif isinstance(widget, QComboBox):
            current = widget.currentText().strip()
        elif isinstance(widget, QSpinBox):
            current = str(widget.value())
        else:
            return

        if isinstance(widget, QLineEdit) and widget in self._widget_factory.unit_groups:
            current = self._to_standard_unit(widget)

        base_ss = widget.styleSheet().replace(self._PARAM_BORDER_MODIFIED, "")
        if current and current != default:
            widget.setStyleSheet(base_ss + self._PARAM_BORDER_MODIFIED)
        else:
            widget.setStyleSheet(base_ss)

    # ── 默认值持久化 ───────────────────────────────────────────

    def _on_save_defaults(self) -> None:
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
                if widget in self._widget_factory.unit_combos:
                    saved[cli_param.flag] = self._to_standard_unit(widget)
                else:
                    saved[cli_param.flag] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                if widget in self._widget_factory.path_mode_toggles:
                    mode_combo = self._widget_factory.path_mode_toggles[widget]
                    mode = "relative" if mode_combo.currentIndex() == 1 else "absolute"
                    saved[cli_param.flag] = json.dumps({"mode": mode, "path": text}, ensure_ascii=False)
                else:
                    saved[cli_param.flag] = text

        self._gui_defaults[self.entry.name] = saved
        self.defaults_changed.emit()
        self.status_message.emit(self.tr("默认值已保存"), 3000)

        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue
            if cli_param.flag in saved:
                self._param_defaults[widget] = saved[cli_param.flag]
                self._update_param_highlight(widget)

    def _on_reset_defaults(self) -> None:
        self._gui_defaults.pop(self.entry.name, None)

        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue
            factory_default = cli_param.default or ""
            if cli_param.choice_values:
                reverse = {v: k for k, v in cli_param.choice_values.items()}
                if factory_default in reverse:
                    factory_default = reverse[factory_default]
            self._set_widget_std_value(widget, factory_default)
            self._param_defaults[widget] = factory_default
            self._update_param_highlight(widget)

        self.defaults_changed.emit()
        self.status_message.emit(self.tr("已恢复出厂默认值"), 3000)

    # ── 公开接口：参数收集 ─────────────────────────────────────

    def collect_run_args(self) -> list[str]:
        """收集 CLI 参数（不含芯片参数展开，由调用方处理）。"""
        extra_args: list[str] = []
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue
            container = self._cli_row_containers.get(key)
            if container is not None and container.isHidden():
                continue

            if isinstance(widget, QCheckBox):
                if widget.isChecked():
                    extra_args.append(cli_param.flag)
            elif isinstance(widget, QSpinBox):
                val = widget.value()
                factory_default = self._factory_defaults.get(widget, "")
                if factory_default:
                    if abs(val - float(factory_default)) > 1e-9:
                        extra_args.extend([cli_param.flag, str(val)])
                elif val != 0:
                    extra_args.extend([cli_param.flag, str(val)])
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                default = self._param_defaults.get(widget, "")
                if widget in self._widget_factory.unit_combos:
                    std_text = self._to_standard_unit(widget)
                    if std_text and std_text != default:
                        extra_args.extend([cli_param.flag, std_text])
                elif text and text != default:
                    extra_args.extend([cli_param.flag, text])
            elif isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                default = self._param_defaults.get(widget, "")
                if text and text != default:
                    if cli_param.choice_values and text in cli_param.choice_values:
                        text = cli_param.choice_values[text]
                    extra_args.extend([cli_param.flag, text])

        return extra_args

    def collect_env_overrides(self) -> dict[str, str]:
        """收集环境变量覆盖。"""
        env_overrides: dict[str, str] = {}
        for key, combo in self._env_widgets.items():
            abs_path = combo.currentData()
            if abs_path and key in self.entry.env_params:
                env_param = self.entry.env_params[key]
                env_overrides[env_param.env_var] = abs_path

        # CLI 文件参数的 env 同步
        _CLI_TO_ENV: dict[str, str] = {
            "--dro-file": "DRO_FILE",
            "--ro-file": "RO_FILE",
            "--search-file": "SEARCH_RESULTS_FILE",
        }
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None or not cli_param.file_category:
                continue
            if isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                default = self._param_defaults.get(widget, "")
                if text and text != default:
                    env_var = _CLI_TO_ENV.get(cli_param.flag)
                    if env_var:
                        env_overrides[env_var] = text

        return env_overrides

    def collect_chip_selections(self) -> dict[str, list[str]]:
        """收集芯片参数选择。"""
        selections: dict[str, list[str]] = {}
        for key, container in self._chip_widgets.items():
            if not hasattr(container, "_chip_buttons"):
                continue
            selected: list[str] = []
            chip_buttons: dict[str, QWidget] = container._chip_buttons  # type: ignore[assignment]
            for label, btn in chip_buttons.items():
                if btn.property("_selected"):
                    selected.append(label)
            if selected:
                for chip_param in self.entry.cli_chip_params:
                    chip_key = chip_param.flag.lstrip("-").replace("-", "_")
                    if chip_key == key:
                        cli_values = []
                        for sel in selected:
                            if sel in chip_param.options:
                                cli_values.append(chip_param.options[sel])
                        selections[key] = cli_values
                        break
        return selections

    def collect_multi_file_configs(self) -> dict[str, list[dict]]:
        """从表格控件收集多文件参数配置。

        遍历每行，读取文件路径（UserRole data）和 per-file 字段值，
        构建与 CLI --json-file 参数兼容的 JSON 列表。
        """
        from PyQt6.QtWidgets import QTableWidget, QSpinBox

        configs: dict[str, list[dict]] = {}
        for key, widget in self._multi_file_widgets.items():
            table = widget.findChild(QTableWidget)
            if table is None:
                continue
            per_fields = getattr(table, '_per_file_fields', [])
            file_configs: list[dict] = []
            for row in range(table.rowCount()):
                name_item = table.item(row, 0)
                if name_item is None:
                    continue
                path = name_item.data(Qt.ItemDataRole.UserRole)
                if not path:
                    continue
                config: dict = {"path": path}
                for col, field_def in enumerate(per_fields, start=1):
                    cell_widget = table.cellWidget(row, col)
                    if cell_widget is None:
                        continue
                    if isinstance(cell_widget, QSpinBox):
                        config[field_def.key] = cell_widget.value()
                    elif isinstance(cell_widget, QLineEdit):
                        text = cell_widget.text().strip()
                        if field_def.field_type == "float" and text:
                            try:
                                config[field_def.key] = float(text)
                            except ValueError:
                                config[field_def.key] = text
                        else:
                            config[field_def.key] = text if text else field_def.default
                file_configs.append(config)
            if file_configs:
                configs[key] = file_configs
        return configs

    def validate_params(self) -> bool:
        """验证参数，返回 True 表示通过。"""
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            container = self._cli_row_containers.get(key)
            if container is not None and container.isHidden():
                continue

            required = (
                cli_param.required
                if cli_param.required is not None
                else bool(cli_param.file_category and not cli_param.default)
            )
            if required:
                if isinstance(widget, QComboBox):
                    text = widget.currentText().strip()
                elif isinstance(widget, QLineEdit):
                    text = widget.text().strip()
                else:
                    text = ""
                if not text:
                    QMessageBox.warning(
                        self,
                        self.tr("参数缺失"),
                        self.tr("脚本需要参数 '{}'，但未填写。").format(cli_param.label),
                    )
                    widget.setFocus()
                    return False

            if cli_param.param_type == "float" and isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if text:
                    try:
                        float(text)
                    except ValueError:
                        QMessageBox.warning(
                            self,
                            self.tr("参数无效"),
                            self.tr("参数 '{}' 需要数值，当前输入 '{}' 无效。").format(cli_param.label, text),
                        )
                        widget.setFocus()
                        return False

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
                        self.tr("文件不存在"),
                        self.tr("参数 '{}' 引用的文件不存在：\n{}\n\n仍然继续？").format(cli_param.label, text),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return False

        return True

    # ── 公开接口：主题 & 文件刷新 ───────────────────────────────

    def update_theme(self, mode: str) -> None:
        """更新主题相关的样式——重新构建整个参数面板。"""
        self._theme_mode = mode

        # 清空旧布局
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.setParent(None)

        self._cli_widgets.clear()
        self._env_widgets.clear()
        self._chip_widgets.clear()
        self._multi_file_widgets.clear()
        self._param_defaults.clear()
        self._factory_defaults.clear()
        self._cli_row_containers.clear()
        self._cli_row_labels.clear()
        self._widget_factory.reset()
        self._widget_factory._files = self._files

        self._build_params()

    def refresh_files(self, files: list[FileInfo]) -> None:
        """更新文件列表并刷新所有文件下拉框。"""
        self._files = files
        self._widget_factory._files = files

        # 刷新环境变量参数下拉框
        for key, env_param in self.entry.env_params.items():
            combo = self._env_widgets.get(key)
            if combo is None:
                continue
            current_data = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(self.tr("（使用脚本默认值）"), None)
            matching = filter_files(
                self._files,
                category=env_param.file_category,
                file_type=env_param.file_type,
                name_pattern=env_param.name_pattern,
            )
            for fi in matching:
                combo.addItem(fi.name, fi.abs_path)
            # 尝试恢复之前选中的文件
            if current_data:
                idx = combo.findData(current_data)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def _on_doc_link_clicked(self, doc_url: str | None) -> None:
        """处理文档链接点击：文档存在时打开，不存在时发出警告。"""
        if doc_url is None:
            self.doc_link_missing.emit(
                self.tr("⚠ 文档未构建：运行 sphinx-build 生成文档后再试")
            )
            return
        self.doc_link_clicked.emit(self.entry.script_path)

    # ── 文档 URL ───────────────────────────────────────────────

    def _get_doc_url(self, script_path: str) -> str | None:
        doc_rel = script_path
        if doc_rel.endswith(".py"):
            doc_rel = doc_rel[:-3]
        doc_path = self._repo_root / "docs" / "build" / "html" / f"{doc_rel}.html"
        if doc_path.exists():
            return doc_path.absolute().as_uri()
        return None

    # ── 运行按钮 ───────────────────────────────────────────────

    def _on_run_clicked(self) -> None:
        self.run_requested.emit()

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
