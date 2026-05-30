"""参数面板状态管理 Mixin。

提供默认值持久化、单位转换、路径模式、条件可见性等状态管理方法，
由 MainWindow 通过多重继承混入。
"""


from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QStatusBar,
    QWidget,
)

from tod.gui.script_registry import (
    UNIT_GROUPS,
    CliParam,
    ScriptEntry,
)

if TYPE_CHECKING:
    from tod.gui.cli_widget_factory import CliWidgetFactory


class ParamsPanelStateMixin:
    """提供参数面板的状态管理方法，由 MainWindow 通过多重继承混入。"""

    _widget_factory: CliWidgetFactory
    _cli_widgets: dict[str, QWidget]
    _param_defaults: dict[QWidget, str]
    _factory_defaults: dict[QWidget, str]
    _cli_row_containers: dict[str, QWidget]
    _cli_row_labels: dict[str, QWidget]
    _current_script: ScriptEntry | None
    _gui_defaults: dict[str, Any]
    _save_gui_defaults: Callable[..., None]
    _repo_root: Path
    _current_theme_mode: str
    _env_widgets: dict[str, QComboBox]
    _status_bar: QStatusBar

    _PARAM_BORDER_MODIFIED = "border: 1px solid #4da6ff;"

    # ── 参数查找 ───────────────────────────────────────

    def _find_cli_param(self, key: str) -> CliParam | None:
        """根据 key 查找当前脚本的 CliParam。"""
        if self._current_script is None:
            return None
        for p in self._current_script.cli_params:
            if p.flag.lstrip("-").replace("-", "_") == key:
                return p
        return None

    # ── 单位转换 ───────────────────────────────────────

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

    # ── 路径模式 ───────────────────────────────────────

    def _on_path_mode_changed(self, file_combo: QComboBox, mode_combo: QComboBox) -> None:
        """Path mode toggle 切换时：重新填充下拉框（相对路径 vs 绝对路径）。"""
        from tod.gui.file_discovery import filter_files

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
        # 尝试恢复之前选中的项
        if current_text:
            idx = file_combo.findText(current_text)
            if idx >= 0:
                file_combo.setCurrentIndex(idx)
            else:
                file_combo.setEditText(current_text)
        file_combo.blockSignals(False)

    # ── 条件可见性 ─────────────────────────────────────

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

            # 解析触发控件的 CliParam，用于 choice_values 反向映射
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
                current_val = _get_trigger_value()
                for tk, expected in tgts:
                    if expected is not None:
                        should_hide = current_val == expected
                    else:
                        # 旧版模式：当触发控件有非空值（truthy）时隐藏
                        # 对于 QCheckBox，str(False) == "False" 作为字符串是 truthy 的，
                        # 因此我们直接检查控件本身
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

    # ── 参数高亮 ───────────────────────────────────────

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

    # ── 默认值持久化 ───────────────────────────────────

    def _collect_current_param_values(self) -> dict[str, dict[str, str | None]]:
        """收集当前参数面板中的所有参数值（显示值），用于 UI rebuild 时恢复。

        Returns:
            {"env": {key: path_or_none}, "cli": {key: display_value}}
            - env: 从 _env_widgets 收集，值为文件路径或 None
            - cli: 从 _cli_widgets 收集，值为显示值
        """
        collected: dict[str, dict[str, str | None]] = {"env": {}, "cli": {}}

        # 收集环境变量参数（文件选择下拉框）
        for key, widget in self._env_widgets.items():
            combo = widget if isinstance(widget, QComboBox) else None
            collected["env"][key] = combo.currentData() if combo else None

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
            widget = self._env_widgets.get(key)
            if widget is None or not isinstance(widget, QComboBox):
                continue
            combo = widget
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
                widget.setChecked(display_value is not None and display_value.lower() == "true")
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(float(display_value or "0")))
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
                # path_mode_toggles 或普通下拉框
                if display_value and display_value.startswith("{"):
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

        sb = self._status_bar
        if sb:
            sb.showMessage(QCoreApplication.translate("ParamsPanelStateMixin", "默认值已保存"), 3000)

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

        sb = self._status_bar
        if sb:
            sb.showMessage(QCoreApplication.translate("ParamsPanelStateMixin", "已恢复出厂默认值"), 3000)
