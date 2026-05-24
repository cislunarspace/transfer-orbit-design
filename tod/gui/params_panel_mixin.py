"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tod.gui.doc_link_mixin import DocLinkMixin, make_doc_link_label
from tod.gui.file_discovery import filter_files
from tod.gui.script_registry import (
    UNIT_GROUPS,
    CliParam,
    MultiCliParam,
    MultiFileConfig,
    ScriptEntry,
)
from tod.gui.theme_utils import resolve_theme as _resolve_theme


class ParamsPanelMixin(DocLinkMixin):
    """提供参数面板构建和操作方法，由 MainWindow 通过多重继承混入。"""

    _PARAM_BORDER_MODIFIED = "border: 1px solid #4da6ff;"

    def _on_path_mode_changed(self, file_combo: QComboBox, mode_combo: QComboBox) -> None:
        """Path mode toggle 切换时：重新填充下拉框（相对路径 vs 绝对路径）。"""
        file_category = mode_combo.property("file_category") or ""
        name_pattern = mode_combo.property("name_pattern") or None
        is_relative = mode_combo.currentIndex() == 1
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
                    mode_combo.setCurrentIndex(1 if data.get("mode") == "relative" else 0)
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
        self._factory_defaults[widget] = cli_param.default or ""
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
        """设置 hidden_when 条件可见性。

        支持两种格式：
        - "--flag"：当触发控件有非空值时隐藏（旧版，向后兼容）
        - "--flag==value"：当触发控件的当前值等于 value 时隐藏
        """
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

            # Resolve trigger's CliParam for choice_values reverse mapping
            trigger_param = self._find_cli_param(trigger_key)

            def _get_trigger_value(
                tw=trigger_widget,
                tp=trigger_param,
            ) -> str:
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

            def update_visibility(
                _=None,
                tw=trigger_widget,
                tgts=targets,
            ):
                """执行 update_visibility 对应的处理逻辑。
                
                Args:
                    _: 调用方传入的参数值。
                    tw: 调用方传入的参数值。
                    tgts: 调用方传入的参数值。
                
                Returns:
                    None。
                """
                current_val = _get_trigger_value()
                for tk, expected in tgts:
                    if expected is not None:
                        should_hide = current_val == expected
                    else:
                        # Legacy mode: hide when trigger has a "truthy" value.
                        # For QCheckBox, str(False) == "False" is truthy as a
                        # string, so we inspect the widget directly.
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

    def _collect_current_param_values(self) -> dict[str, dict[str, str | None]]:
        """收集当前参数面板中的所有参数值（显示值），用于 UI rebuild 时恢复。

        Returns:
            {"env": {key: path_or_none}, "cli": {key: display_value}}
            - env: 从 _env_widgets 收集，值为文件路径或 None
            - cli: 从 _cli_widgets 收集，值为显示值
        """
        collected: dict[str, dict[str, str | None]] = {"env": {}, "cli": {}}

        # 收集环境变量参数（文件选择下拉框）
        for key, combo in self._env_widgets.items():
            collected["env"][key] = combo.currentData()

        # 收集命令行参数（显示值）
        for key, widget in self._cli_widgets.items():
            if isinstance(widget, QCheckBox):
                collected["cli"][key] = str(widget.isChecked())
            elif isinstance(widget, QSpinBox):
                collected["cli"][key] = str(widget.value())
            elif isinstance(widget, QLineEdit):
                collected["cli"][key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                # path_mode_toggles: 格式化为 {"mode": ..., "path": ...}
                if widget in self._widget_factory.path_mode_toggles:
                    mode_combo = self._widget_factory.path_mode_toggles[widget]
                    mode = "relative" if mode_combo.currentIndex() == 1 else "absolute"
                    collected["cli"][key] = json.dumps(
                        {"mode": mode, "path": widget.currentText()}, ensure_ascii=False
                    )
                else:
                    collected["cli"][key] = widget.currentText().strip()

        return collected

    def _restore_param_values(self, saved: dict[str, dict[str, str | None]]) -> None:
        """将暂存的参数值恢复到控件。

        Args:
            saved: _collect_current_param_values() 返回的值
        """
        # 恢复环境变量参数（文件选择下拉框）
        for key, path in saved.get("env", {}).items():
            combo = self._env_widgets.get(key)
            if combo is None:
                continue
            if path is None:
                combo.setCurrentIndex(0)  # 选中 "（使用脚本默认值）"
            else:
                idx = combo.findData(path)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setCurrentText(str(path))

        # 恢复命令行参数
        for key, display_value in saved.get("cli", {}).items():
            widget = self._cli_widgets.get(key)
            if widget is None:
                continue

            if isinstance(widget, QCheckBox):
                widget.setChecked(display_value.lower() == "true")
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(float(display_value)))
                except ValueError:
                    pass
            elif isinstance(widget, QLineEdit):
                # 带单位的控件：显示值 → 标准单位值 → _set_widget_std_value
                if widget in self._widget_factory.unit_combos and display_value:
                    try:
                        display_val = float(display_value)
                    except ValueError:
                        widget.setText(display_value)
                        continue
                    combo = self._widget_factory.unit_combos[widget]
                    group_name = self._widget_factory.unit_groups[widget]
                    group = UNIT_GROUPS[group_name]
                    units = list(group.keys())
                    factor = group[units[combo.currentIndex()]]
                    std_val = display_val * factor
                    widget.setText(f"{std_val:.10g}")
                else:
                    widget.setText(display_value)
            elif isinstance(widget, QComboBox):
                # path_mode_toggles 或普通 combo
                if display_value.startswith("{"):
                    try:
                        data = json.loads(display_value)
                        mode_combo = self._widget_factory.path_mode_toggles.get(widget)
                        if mode_combo:
                            mode_combo.blockSignals(True)
                            mode_combo.setCurrentIndex(1 if data.get("mode") == "relative" else 0)
                            mode_combo.blockSignals(False)
                            self._on_path_mode_changed(widget, mode_combo)
                        widget.setCurrentText(data.get("path", ""))
                    except (json.JSONDecodeError, KeyError):
                        widget.setCurrentText(display_value)
                else:
                    widget.setCurrentText(display_value)

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
                    mode = "relative" if mode_combo.currentIndex() == 1 else "absolute"
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
            sb.showMessage(QCoreApplication.translate("ParamsPanelMixin", "默认值已保存"), 3000)

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
            sb.showMessage(QCoreApplication.translate("ParamsPanelMixin", "已恢复出厂默认值"), 3000)

    def _add_multi_file_param(self, multi_param: MultiCliParam) -> None:
        """创建多文件参数控件（ListWidget + 索引配置面板）。

        Args:
            multi_param: 多文件参数定义
        """
        key, widget = self._widget_factory.make_multi_file_widget(
            multi_param,
            str(self._repo_root),
        )
        self._multi_file_widgets[key] = widget

        # 索引配置面板（初始为空）
        config_panel = self._create_config_panel(key, multi_param)
        self._multi_file_config_panels[key] = config_panel

        # 连接选择变化信号
        widget.multi_file_selection_changed.connect(
            lambda k, cfg: self._on_multi_file_selection_changed(k, cfg)
        )

        # 垂直布局：ListWidget 在上，配置面板在下
        container = QWidget()
        container.setObjectName(f"multi_file_param_{key}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(widget)
        layout.addWidget(config_panel)

        row_container = QWidget()
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(container)
        self._cli_row_containers[key] = row_container

        self._params_layout.addRow(f"{multi_param.label}:", row_container)
        label = self._params_layout.labelForField(row_container)
        if label is not None:
            self._cli_row_labels[key] = label

    def _create_config_panel(
        self,
        key: str,
        multi_param: MultiCliParam,
    ) -> QWidget:
        """创建索引配置面板。

        Args:
            key: 参数 key
            multi_param: 多文件参数定义

        Returns:
            配置面板 widget
        """
        panel = QWidget()
        panel.setObjectName(f"config_panel_{key}")
        panel.setVisible(False)

        layout = QFormLayout(panel)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 文件信息标签
        file_label = QLabel(QCoreApplication.translate("ParamsPanelMixin", "未选择文件"))
        file_label.setObjectName("file_info_label")
        layout.addRow("", file_label)

        # 起始索引
        start_spin = QSpinBox()
        start_spin.setRange(-99999, 99999)
        start_spin.setValue(-1)
        start_spin.setToolTip(
            QCoreApplication.translate("ParamsPanelMixin", "起始轨道索引，-1 表示从第一条")
        )
        start_spin.setObjectName("start_spin")
        layout.addRow(
            QCoreApplication.translate("ParamsPanelMixin", "起始索引:"), start_spin
        )

        # 结束索引
        end_spin = QSpinBox()
        end_spin.setRange(-99999, 99999)
        end_spin.setValue(-1)
        end_spin.setToolTip(
            QCoreApplication.translate("ParamsPanelMixin", "结束轨道索引（含），-1 表示到最后一条")
        )
        end_spin.setObjectName("end_spin")
        layout.addRow(
            QCoreApplication.translate("ParamsPanelMixin", "结束索引:"), end_spin
        )

        # 绘制间隔
        step_spin = QSpinBox()
        step_spin.setRange(1, 99999)
        step_spin.setValue(1)
        step_spin.setToolTip(
            QCoreApplication.translate("ParamsPanelMixin", "每隔 N 条轨道绘制 1 条，1 表示绘制全部")
        )
        step_spin.setObjectName("step_spin")
        layout.addRow(
            QCoreApplication.translate("ParamsPanelMixin", "绘制间隔:"), step_spin
        )

        # 存储引用到 panel
        panel._file_label = file_label
        panel._start_spin = start_spin
        panel._end_spin = end_spin
        panel._step_spin = step_spin

        return panel

    def _on_multi_file_selection_changed(
        self,
        key: str,
        config: dict | None,
    ) -> None:
        """多文件列表选中项变化时，更新配置面板。

        Args:
            key: 参数 key
            config: 当前选中文件的配置，None 表示未选中
        """
        panel = self._multi_file_config_panels.get(key)
        widget = self._multi_file_widgets.get(key)
        if panel is None or widget is None:
            return

        if config is None:
            panel.setVisible(False)
            return

        # 断开旧连接
        try:
            panel._start_spin.valueChanged.disconnect()
            panel._end_spin.valueChanged.disconnect()
            panel._step_spin.valueChanged.disconnect()
        except Exception:
            pass

        # 更新面板内容
        panel.setVisible(True)
        file_label = panel._file_label
        path = config.get("path", "")

        # 尝试获取文件中的轨道数量
        orbit_count = ""
        try:
            from e2m2e.core import OrbitFamily
            from tod.commons.constants import MU
            from e2m2e.core import CR3BP_System

            system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
            family = OrbitFamily.load_from_file(Path(path), system)
            orbit_count = QCoreApplication.translate(
                "ParamsPanelMixin", " ({n} 条轨道)"
            ).format(n=len(family))
        except Exception:
            pass

        file_label.setText(f"{Path(path).name}{orbit_count}")

        # 更新控件值
        panel._start_spin.setValue(config.get("start", -1))
        panel._end_spin.setValue(config.get("end", -1))
        panel._step_spin.setValue(config.get("step", 1))

        # 连接 spin box 变化，更新 list widget 数据
        def _update_config() -> None:
            list_widget = widget.findChild(QListWidget)  # type: ignore
            if list_widget is None:
                return
            current_item = list_widget.currentItem()
            if current_item is None:
                return
            path = current_item.data(Qt.ItemDataRole.UserRole)
            if path in list_widget._file_items:
                list_widget._file_items[path]["start"] = panel._start_spin.value()
                list_widget._file_items[path]["end"] = panel._end_spin.value()
                list_widget._file_items[path]["step"] = panel._step_spin.value()

        panel._start_spin.valueChanged.connect(_update_config)
        panel._end_spin.valueChanged.connect(_update_config)
        panel._step_spin.valueChanged.connect(_update_config)

    def _rebuild_params_panel(self, entry: ScriptEntry) -> None:
        """Handle click on the documentation link."""
        if doc_url is None:
            sb = self.statusBar()
            if sb:
                sb.showMessage(QCoreApplication.translate("ParamsPanelMixin", "⚠ 文档未构建：运行 sphinx-build 生成文档后再试"), 5000)
            return
        self.doc_link_clicked.emit(entry.script_path)

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
        self._chip_widgets.clear()
        self._multi_file_widgets.clear()
        self._multi_file_config_panels.clear()
        self._param_defaults.clear()
        self._factory_defaults.clear()
        self._cli_row_containers.clear()
        self._cli_row_labels.clear()
        self._widget_factory.reset()
        self._widget_factory._files = self._files

        self._params_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._params_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Get doc URL for clickable title
        doc_url = self._get_doc_url(entry.script_path)
        title = make_doc_link_label(entry.name, doc_url)
        # Always connect clicked signal - doc_url determines if doc exists, not clickability
        title.clicked.connect(lambda ep=entry, du=doc_url: self._on_doc_link_clicked(ep, du))
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
        cmd_abs_btn = QPushButton(QCoreApplication.translate("ParamsPanelMixin", "复制路径"))
        cmd_abs_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_abs_btn.setToolTip(QCoreApplication.translate("ParamsPanelMixin", "复制绝对路径"))
        abs_cmd_path = str(self._repo_root / entry.script_path)
        cmd_abs_btn.clicked.connect(
            lambda _, p=abs_cmd_path, b=cmd_abs_btn: self._copy_path_to_clipboard(p, b)
        )

        # 相对路径复制按钮
        cmd_rel_btn = QPushButton(QCoreApplication.translate("ParamsPanelMixin", "复制相对路径"))
        cmd_rel_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 9pt; }"
            "QPushButton:flat { border: none; }"
        )
        cmd_rel_btn.setToolTip(QCoreApplication.translate("ParamsPanelMixin", "复制相对路径（相对于项目根目录）"))
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

        self._params_layout.addRow(QCoreApplication.translate("ParamsPanelMixin", "命令:"), cmd_row_widget)

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

            out_abs_btn = QPushButton(QCoreApplication.translate("ParamsPanelMixin", "复制路径"))
            out_abs_btn.setStyleSheet(
                "QPushButton { padding: 2px 8px; font-size: 9pt; }"
                "QPushButton:flat { border: none; }"
            )
            out_abs_btn.setToolTip(QCoreApplication.translate("ParamsPanelMixin", "复制绝对路径"))
            abs_out_path = str(self._repo_root / entry.output_dir)
            out_abs_btn.clicked.connect(
                lambda _, p=abs_out_path, b=out_abs_btn: self._copy_path_to_clipboard(p, b)
            )

            out_rel_btn = QPushButton(QCoreApplication.translate("ParamsPanelMixin", "复制相对路径"))
            out_rel_btn.setStyleSheet(
                "QPushButton { padding: 2px 8px; font-size: 9pt; }"
                "QPushButton:flat { border: none; }"
            )
            out_rel_btn.setToolTip(QCoreApplication.translate("ParamsPanelMixin", "复制相对路径（相对于项目根目录）"))
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

            self._params_layout.addRow(QCoreApplication.translate("ParamsPanelMixin", "输出目录:"), out_row_widget)

        # 分隔线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("margin: 4px 0 8px 0;")
        self._params_layout.addRow(divider)

        has_any = False

        # 多选芯片参数（位于参数面板顶部，如平动点、Halo类别）
        if entry.cli_chip_params:
            for chip_param in entry.cli_chip_params:
                key, widget = self._widget_factory.make_chip_widget(chip_param)
                self._chip_widgets[key] = widget
                self._params_layout.addRow(f"{chip_param.label}:", widget)
            has_any = True

        # 多文件参数（ListWidget + 索引配置面板）
        if entry.multi_cli_params:
            for multi_param in entry.multi_cli_params:
                self._add_multi_file_param(multi_param)
            has_any = True

        # 环境变量参数（文件选择下拉框）
        if entry.env_params:
            section_label = QLabel(QCoreApplication.translate("ParamsPanelMixin", "数据文件"))
            section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
            self._params_layout.addRow(section_label)

            for key, env_param in entry.env_params.items():
                combo = QComboBox()
                combo.addItem(QCoreApplication.translate("ParamsPanelMixin", "（使用脚本默认值）"), None)

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
                section_label = QLabel(QCoreApplication.translate("ParamsPanelMixin", "运行参数"))
                section_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px 0;")
                self._params_layout.addRow(section_label)

                for cli_param in regular_params:
                    self._add_cli_param_row(cli_param)

            if advanced_params:
                adv_group = QGroupBox(QCoreApplication.translate("ParamsPanelMixin", "高级选项"))
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
            save_btn = QPushButton(QCoreApplication.translate("ParamsPanelMixin", "保存为默认值"))
            save_btn.setToolTip(QCoreApplication.translate("ParamsPanelMixin", "将当前参数值保存为此脚本的默认值"))
            save_btn.clicked.connect(self._on_save_defaults)
            reset_btn = QPushButton(QCoreApplication.translate("ParamsPanelMixin", "恢复出厂默认"))
            reset_btn.setToolTip(QCoreApplication.translate("ParamsPanelMixin", "恢复为系统预设的默认参数值"))
            reset_btn.clicked.connect(self._on_reset_defaults)
            btn_layout.addWidget(save_btn)
            btn_layout.addWidget(reset_btn)
            btn_layout.addStretch()
            btn_wrapper = QWidget()
            btn_wrapper.setLayout(btn_layout)
            self._params_layout.addRow(btn_wrapper)

        if not has_any:
            label = QLabel(QCoreApplication.translate("ParamsPanelMixin", "此脚本无可配置参数"))
            label.setStyleSheet("color: #999; font-style: italic;")
            self._params_layout.addRow(label)
