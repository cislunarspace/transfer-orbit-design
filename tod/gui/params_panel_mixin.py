"""参数面板 Mixin — 参数面板构建和操作逻辑。"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QWidget,
)

from tod.gui.file_discovery import filter_files
from tod.gui.params_panel import UNIT_GROUPS, CliWidgetFactory
from tod.gui.script_registry import CliParam, ScriptEntry
from tod.gui.theme_utils import resolve_theme as _resolve_theme


class ParamsPanelMixin:
    """提供参数面板构建和操作方法，由 MainWindow 通过多重继承混入。"""

    _PARAM_BORDER_MODIFIED = "border: 1px solid #4da6ff;"

    def _on_path_mode_changed(self, file_combo: QComboBox, mode_combo: QComboBox) -> None:
        """Path mode toggle 切换时：重新填充下拉框（相对路径 vs 绝对路径）。"""
        file_category = mode_combo.property("file_category") or ""
        name_pattern = mode_combo.property("name_pattern") or None
        is_relative = mode_combo.currentText() == "相对"
        current_text = file_combo.currentText()
        file_combo.blockSignals(True)
        file_combo.clear()
        file_combo.addItem("")
        matching = filter_files(self._files, category=file_category, file_type="json", name_pattern=name_pattern)
        for fi in matching:
            if is_relative:
                file_combo.addItem(fi.path)
            else:
                file_combo.addItem(fi.abs_path)
        # Try to restore previous selection
        if current_text:
            idx = file_combo.findText(current_text)
            if idx >= 0:
                file_combo.setCurrentIndex(idx)
            else:
                file_combo.setEditText(current_text)
        file_combo.blockSignals(False)

    def _make_cli_widget(self, cli_param: CliParam) -> tuple[str, QWidget]:
        return self._widget_factory.make_widget(cli_param)

    def _display_widget(self, widget: QWidget) -> QWidget:
        return self._widget_factory.display_widget(widget)

    def _set_widget_std_value(self, widget: QWidget, std_val_str: str) -> None:
        """将标准单位值设置到控件（带单位的 QLineEdit 会自动转换到当前显示单位）。"""
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
            # 查找 cli_param 以支持 choice_values 反向映射
            cli_param = None
            for k, w in self._cli_widgets.items():
                if w is widget:
                    cli_param = self._find_cli_param(k)
                    break
            # 文件下拉框：尝试解析 {"mode": ..., "path": ...} 格式
            if widget in self._widget_factory.path_mode_toggles and std_val_str.startswith("{"):
                try:
                    data = json.loads(std_val_str)
                    mode_combo = self._widget_factory.path_mode_toggles[widget]
                    mode_combo.blockSignals(True)
                    mode_combo.setCurrentText("相对" if data.get("mode") == "relative" else "绝对")
                    mode_combo.blockSignals(False)
                    self._on_path_mode_changed(widget, mode_combo)
                    widget.setCurrentText(data.get("path", ""))
                    return
                except (json.JSONDecodeError, KeyError):
                    pass
            # choice_values 反向映射：CLI 值 → 显示标签
            if cli_param and cli_param.choice_values:
                reverse = {v: k for k, v in cli_param.choice_values.items()}
                if std_val_str in reverse:
                    std_val_str = reverse[std_val_str]
            widget.setCurrentText(std_val_str)

    def _add_cli_param_row(self, cli_param: CliParam) -> None:
        """创建控件并添加到参数面板的当前表单布局中。"""
        key, widget = self._make_cli_widget(cli_param)
        display = self._display_widget(widget)
        self._cli_widgets[key] = widget
        self._param_defaults[widget] = cli_param.default or ""
        self._connect_param_highlight(widget)

        # Wrap in container for hidden_when support
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
        if isinstance(widget, QLineEdit) and widget in self._widget_factory.unit_groups:
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

    def _setup_conditional_visibility(self, entry: ScriptEntry) -> None:
        """设置 hidden_when 条件可见性：当触发控件有值时隐藏目标控件行。"""
        hidden_map: dict[str, list[str]] = {}
        for p in entry.cli_params:
            if p.hidden_when:
                trigger_key = p.hidden_when.lstrip("-").replace("-", "_")
                target_key = p.flag.lstrip("-").replace("-", "_")
                hidden_map.setdefault(trigger_key, []).append(target_key)

        for trigger_key, target_keys in hidden_map.items():
            trigger_widget = self._cli_widgets.get(trigger_key)
            if trigger_widget is None:
                continue

            def update_visibility(
                _=None,
                tw=trigger_widget,
                tks=target_keys,
            ):
                has_value = False
                if isinstance(tw, QComboBox):
                    has_value = bool(tw.currentText().strip())
                elif isinstance(tw, QLineEdit):
                    has_value = bool(tw.text().strip())

                for tk in tks:
                    container = self._cli_row_containers.get(tk)
                    if container is not None:
                        container.setVisible(not has_value)
                        label = self._cli_row_labels.get(tk)
                        if label is not None:
                            label.setVisible(not has_value)

            if isinstance(trigger_widget, QComboBox):
                trigger_widget.currentTextChanged.connect(update_visibility)
            elif isinstance(trigger_widget, QLineEdit):
                trigger_widget.textChanged.connect(update_visibility)

            update_visibility()

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
                if widget in self._widget_factory.unit_combos:
                    saved[cli_param.flag] = self._to_standard_unit(widget)
                else:
                    saved[cli_param.flag] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                if widget in self._widget_factory.path_mode_toggles:
                    mode_combo = self._widget_factory.path_mode_toggles[widget]
                    mode = "relative" if mode_combo.currentText() == "相对" else "absolute"
                    saved[cli_param.flag] = json.dumps({"mode": mode, "path": text}, ensure_ascii=False)
                else:
                    saved[cli_param.flag] = text

        self._gui_defaults[self._current_script.name] = saved
        self._save_gui_defaults()

        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue
            flag = cli_param.flag
            if flag in saved:
                self._param_defaults[widget] = saved[flag]
                self._update_param_highlight(widget)

        sb = self.statusBar()
        if sb:
            sb.showMessage("默认值已保存", 3000)

    def _on_reset_defaults(self) -> None:
        """恢复为 script_registry 中定义的出厂默认值。"""
        if self._current_script is None:
            return

        self._gui_defaults.pop(self._current_script.name, None)
        self._save_gui_defaults()

        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            factory_default = cli_param.default or ""

            # choice_values 反向映射：CLI 值 → 显示标签
            if cli_param.choice_values:
                reverse = {v: k for k, v in cli_param.choice_values.items()}
                if factory_default in reverse:
                    factory_default = reverse[factory_default]

            self._set_widget_std_value(widget, factory_default)
            self._param_defaults[widget] = factory_default
            self._update_param_highlight(widget)

        sb = self.statusBar()
        if sb:
            sb.showMessage("已恢复出厂默认值", 3000)

    def _rebuild_params_panel(self, entry: ScriptEntry) -> None:
        """根据选中的脚本重建运行参数面板。"""
        # 清空旧控件
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.setParent(None)

        self._env_widgets.clear()
        self._cli_widgets.clear()
        self._param_defaults.clear()
        self._cli_row_containers.clear()
        self._cli_row_labels.clear()
        self._widget_factory.reset()
        self._widget_factory._files = self._files

        self._params_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._params_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        title = QLabel(entry.name)
        title.setStyleSheet("font-size: 15px; font-weight: bold; padding: 4px 0;")
        self._params_layout.addRow(title)

        if entry.description:
            desc_label = QLabel(entry.description)
            if _resolve_theme(self._current_theme_mode) == "dark":
                desc_label.setStyleSheet(
                    "font-size: 12px; padding: 6px 10px; border-radius: 4px; color: #aaaaaa;"
                    "background-color: #252525;"
                )
            else:
                desc_label.setStyleSheet(
                    "font-size: 12px; padding: 6px 10px; border-radius: 4px; color: #444444;"
                    "background-color: #f0f0f0;"
                )
            desc_label.setWordWrap(True)
            self._params_layout.addRow(desc_label)

        # 命令行容器（含 label + 复制按钮）
        cmd_label = QLabel(f"python {entry.script_path}")
        if _resolve_theme() == "dark":
            cmd_bg = "#2d2d2d"
            cmd_color = "#bbbbbb"
            cmd_accent = "#4da6ff"
        else:
            cmd_bg = "#e8e8e8"
            cmd_color = "#333333"
            cmd_accent = "#1976d2"

        cmd_label.setStyleSheet(
            f"font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Liberation Mono', monospace; "
            f"font-size: 9pt; color: {cmd_color}; background-color: {cmd_bg}; "
            f"padding: 6px 10px; border-radius: 4px; border-left: 3px solid {cmd_accent};"
        )
        cmd_label.setWordWrap(False)
        cmd_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # 绝对路径复制按钮
        cmd_abs_btn = QPushButton("复制路径")
        cmd_abs_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_abs_btn.setToolTip("复制绝对路径")
        abs_cmd_path = str(self._repo_root / entry.script_path)
        cmd_abs_btn.clicked.connect(
            lambda _, p=abs_cmd_path, b=cmd_abs_btn: self._copy_path_to_clipboard(p, b)
        )

        # 相对路径复制按钮
        cmd_rel_btn = QPushButton("复制相对路径")
        cmd_rel_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_rel_btn.setToolTip("复制相对路径（相对于项目根目录）")
        cmd_rel_btn.clicked.connect(
            lambda _, p=entry.script_path, b=cmd_rel_btn: self._copy_path_to_clipboard(p, b)
        )

        # 水平布局：label + 按钮组
        cmd_row_widget = QWidget()
        cmd_row_layout = QHBoxLayout(cmd_row_widget)
        cmd_row_layout.setContentsMargins(0, 0, 0, 0)
        cmd_row_layout.setSpacing(4)
        cmd_row_layout.addWidget(cmd_label)
        cmd_row_layout.addWidget(cmd_abs_btn)
        cmd_row_layout.addWidget(cmd_rel_btn)
        cmd_row_layout.addStretch()

        self._params_layout.addRow("命令:", cmd_row_widget)

        if entry.output_dir:
            out_label = QLabel(entry.output_dir)
            if _resolve_theme(self._current_theme_mode) == "dark":
                out_bg = "#2d2d2d"
                out_color = "#bbbbbb"
                out_accent = "#4caf50"
            else:
                out_bg = "#e8e8e8"
                out_color = "#333333"
                out_accent = "#388e3c"

            out_label.setStyleSheet(
                f"font-family: 'Cascadia Code', 'Consolas', 'Menlo', 'DejaVu Sans Mono', 'Liberation Mono', monospace; "
                f"font-size: 9pt; color: {out_color}; background-color: {out_bg}; "
                f"padding: 6px 10px; border-radius: 4px; border-left: 3px solid {out_accent};"
            )
            out_label.setWordWrap(False)
            out_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            out_abs_btn = QPushButton("复制路径")
            out_abs_btn.setStyleSheet(
                "QPushButton { padding: 2px 8px; font-size: 9pt; }"
                "QPushButton:flat { border: none; }"
            )
            out_abs_btn.setToolTip("复制绝对路径")
            abs_out_path = str(self._repo_root / entry.output_dir)
            out_abs_btn.clicked.connect(
                lambda _, p=abs_out_path, b=out_abs_btn: self._copy_path_to_clipboard(p, b)
            )

            out_rel_btn = QPushButton("复制相对路径")
            out_rel_btn.setStyleSheet(
                "QPushButton { padding: 2px 8px; font-size: 9pt; }"
                "QPushButton:flat { border: none; }"
            )
            out_rel_btn.setToolTip("复制相对路径（相对于项目根目录）")
            out_rel_btn.clicked.connect(
                lambda _, p=entry.output_dir, b=out_rel_btn: self._copy_path_to_clipboard(p, b)
            )

            out_row_widget = QWidget()
            out_row_layout = QHBoxLayout(out_row_widget)
            out_row_layout.setContentsMargins(0, 0, 0, 0)
            out_row_layout.setSpacing(4)
            out_row_layout.addWidget(out_label)
            out_row_layout.addWidget(out_abs_btn)
            out_row_layout.addWidget(out_rel_btn)
            out_row_layout.addStretch()

            self._params_layout.addRow("输出目录:", out_row_widget)

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

        # 设置条件可见性（hidden_when）
        self._setup_conditional_visibility(entry)

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
