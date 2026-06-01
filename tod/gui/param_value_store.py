"""参数值的存储与单位/路径/可见性/高亮逻辑层。

将 ``ScriptTabWidget`` 中"作用于控件字典"的方法抽离到独立的 store 类，
让 ``ScriptParamPanel`` 仅负责 UI 构建、``ScriptParamCollector`` 仅负责收集。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from tod.gui.cli_widget_factory import CliWidgetFactory
from tod.gui.file_discovery import filter_files
from tod.gui.script_registry import UNIT_GROUPS, CliParam, ScriptEntry

if TYPE_CHECKING:
    pass


class ParamValueStore:
    """参数值存储：持有控件字典、默认值、单位/路径/可见性/高亮/默认值持久化逻辑。

    ``_find_cli_param`` 通过构造时注入（lambda）以避免反向依赖 widget。
    """

    _PARAM_BORDER_MODIFIED = "border: 1px solid #4da6ff;"

    def __init__(
        self,
        files: list,
        find_cli_param: Callable[[str], "CliParam | None"],
        on_path_mode_changed: Callable[[QComboBox, QComboBox], None] | None = None,
        on_unit_changed: Callable[[QLineEdit, QComboBox, str], None] | None = None,
    ) -> None:
        self._find_cli_param = find_cli_param

        # 控件字典
        self._cli_widgets: dict[str, QWidget] = {}
        self._env_widgets: dict[str, QComboBox] = {}
        self._chip_widgets: dict[str, QWidget] = {}
        self._multi_file_widgets: dict[str, QWidget] = {}

        # 默认值字典
        self._param_defaults: dict[QWidget, str] = {}
        self._factory_defaults: dict[QWidget, str] = {}

        # 条件可见性用的 row 容器和 label
        self._row_containers: dict[str, QWidget] = {}
        self._row_labels: dict[str, QWidget] = {}

        # 文件列表（用于路径模式过滤等）
        self._files = files

        # 工厂必须最后创建——它需要 on_path_mode_changed / on_unit_changed 回调
        self._widget_factory = CliWidgetFactory(
            files=self._files,
            on_path_mode_changed=on_path_mode_changed or self.on_path_mode_changed,
            on_unit_changed=on_unit_changed or self.on_unit_changed,
        )

    # ── 工厂引用 ───────────────────────────────────────────────

    @property
    def widget_factory(self) -> CliWidgetFactory:
        return self._widget_factory

    # ── getter 属性（保持与原 widget 一致的访问接口） ──────────

    @property
    def cli_widgets(self) -> dict[str, QWidget]:
        return self._cli_widgets

    @property
    def env_widgets(self) -> dict[str, QComboBox]:
        return self._env_widgets

    @property
    def chip_widgets(self) -> dict[str, QWidget]:
        return self._chip_widgets

    @property
    def multi_file_widgets(self) -> dict[str, QWidget]:
        return self._multi_file_widgets

    @property
    def param_defaults(self) -> dict[QWidget, str]:
        return self._param_defaults

    @property
    def factory_defaults(self) -> dict[QWidget, str]:
        return self._factory_defaults

    @property
    def row_containers(self) -> dict[str, QWidget]:
        return self._row_containers

    @property
    def row_labels(self) -> dict[str, QWidget]:
        return self._row_labels

    def cli_params(self, entry: ScriptEntry) -> list[CliParam]:
        return list(entry.cli_params)

    # ── 公共方法：单位转换 / 值写入 / 路径模式 ─────────────────

    def to_standard_unit(self, line_edit: QLineEdit) -> str:
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

    def on_unit_changed(self, line_edit: QLineEdit, combo: QComboBox, group_name: str) -> None:
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

    def set_widget_std_value(self, widget: QWidget, std_val_str: str) -> None:
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

    def on_path_mode_changed(self, file_combo: QComboBox, mode_combo: QComboBox) -> None:
        file_category = mode_combo.property("file_category") or ""
        name_pattern = mode_combo.property("name_pattern") or None
        is_relative = mode_combo.currentIndex() == 1
        current_text = file_combo.currentText()
        file_combo.blockSignals(True)
        file_combo.clear()
        file_combo.addItem("")
        matching = filter_files(
            self._files,
            category=file_category,
            file_type="json",
            name_pattern=name_pattern,
        )
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

    def setup_conditional_visibility(
        self,
        entry: ScriptEntry,
        cli_widgets: dict[str, QWidget] | None = None,
        row_containers: dict[str, QWidget] | None = None,
        row_labels: dict[str, QWidget] | None = None,
    ) -> None:
        """为所有带 hidden_when 的参数挂上信号联动。

        既可从 self 读取（默认），也可显式传入 dict（兼容旧测试 harness 模式）。
        """
        cli_widgets = cli_widgets if cli_widgets is not None else self._cli_widgets
        row_containers = row_containers if row_containers is not None else self._row_containers
        row_labels = row_labels if row_labels is not None else self._row_labels

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
            trigger_widget = cli_widgets.get(trigger_key)
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

            def update_visibility(
                _=None,
                tw=trigger_widget,
                tgts=targets,
                rc=row_containers,
                rl=row_labels,
            ):
                current_val = _get_trigger_value()
                for tk, expected in tgts:
                    if expected is not None:
                        should_hide = current_val == expected
                    else:
                        if isinstance(tw, QCheckBox):
                            should_hide = tw.isChecked()
                        else:
                            should_hide = bool(current_val)
                    container = rc.get(tk)
                    if container is not None:
                        container.setVisible(not should_hide)
                        label = rl.get(tk)
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

    def connect_param_highlight(self, widget: QWidget) -> None:
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _, w=widget: self._update_param_highlight(w))
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(
                lambda _, w=widget: self._update_param_highlight(w)
            )
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
            current = self.to_standard_unit(widget)

        base_ss = widget.styleSheet().replace(self._PARAM_BORDER_MODIFIED, "")
        if current and current != default:
            widget.setStyleSheet(base_ss + self._PARAM_BORDER_MODIFIED)
        else:
            widget.setStyleSheet(base_ss)

    def update_param_highlight(self, widget: QWidget) -> None:
        """公开别名（与旧 widget 接口对齐）。"""
        self._update_param_highlight(widget)

    # ── 默认值持久化 ───────────────────────────────────────────

    def save_defaults(self, entry: ScriptEntry, gui_defaults: dict[str, Any]) -> None:
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
                    saved[cli_param.flag] = self.to_standard_unit(widget)
                else:
                    saved[cli_param.flag] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                if widget in self._widget_factory.path_mode_toggles:
                    mode_combo = self._widget_factory.path_mode_toggles[widget]
                    mode = "relative" if mode_combo.currentIndex() == 1 else "absolute"
                    saved[cli_param.flag] = json.dumps(
                        {"mode": mode, "path": text}, ensure_ascii=False
                    )
                else:
                    saved[cli_param.flag] = text

        gui_defaults[entry.name] = saved

        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue
            if cli_param.flag in saved:
                self._param_defaults[widget] = saved[cli_param.flag]
                self._update_param_highlight(widget)

    def reset_defaults(self, entry: ScriptEntry, gui_defaults: dict[str, Any]) -> None:
        gui_defaults.pop(entry.name, None)

        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue
            factory_default = cli_param.default or ""
            if cli_param.choice_values:
                reverse = {v: k for k, v in cli_param.choice_values.items()}
                if factory_default in reverse:
                    factory_default = reverse[factory_default]
            self.set_widget_std_value(widget, factory_default)
            self._param_defaults[widget] = factory_default
            self._update_param_highlight(widget)

    # ── 主题刷新 / 重置 ────────────────────────────────────────

    def clear(self) -> None:
        """清空所有 dict（用于主题切换时重建 UI）。"""
        self._cli_widgets.clear()
        self._env_widgets.clear()
        self._chip_widgets.clear()
        self._multi_file_widgets.clear()
        self._param_defaults.clear()
        self._factory_defaults.clear()
        self._row_containers.clear()
        self._row_labels.clear()
        self._widget_factory.reset()
        self._widget_factory._files = self._files

    def set_files(self, files: list) -> None:
        """更新文件列表（用于 refresh_files）。"""
        self._files = files
        self._widget_factory._files = files
