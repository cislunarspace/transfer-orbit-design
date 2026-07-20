"""参数值的存储与单位/路径/可见性/高亮逻辑层。

将 ``ScriptTabWidget`` 中"作用于控件字典"的方法抽离到独立的 store 类，
让 ``ScriptParamPanel`` 仅负责 UI 构建、``ScriptParamCollector`` 仅负责收集。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from tod.gui.params.cli_widget_factory import CliWidgetFactory
from tod.gui.files.file_discovery import filter_files
from tod.scripting import UNIT_GROUPS, CliParam, ScriptEntry

if TYPE_CHECKING:
    pass

@dataclass(frozen=True)
class CatalogSeedSelectorState:
    """Catalog seed selector 的轻量 UI 状态。"""

    enabled_checkbox: QCheckBox
    selector_widget: QWidget
    preview_label: QWidget
    mode_widget: QWidget
    jacobi_widget: QWidget
    tolerance_widget: QWidget
    manual_keys: tuple[str, ...]

class ParamValueStore:
    """参数值存储：持有控件字典、默认值、单位/路径/可见性/高亮/默认值持久化逻辑。

    ``_find_cli_param`` 通过构造时注入（lambda）以避免反向依赖 widget。
    """

    _PARAM_BORDER_MODIFIED = "border: 1px solid #0078d4;"

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
        self._catalog_seed_selectors: dict[str, CatalogSeedSelectorState] = {}

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
                    self.on_path_mode_changed(widget, mode_combo)
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
        cli_widgets: Mapping[str, QWidget] | None = None,
        row_containers: Mapping[str, QWidget] | None = None,
        row_labels: Mapping[str, QWidget] | None = None,
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

    # ── 参数收集（原 ScriptParamCollector） ─────────────────────

    def collect_run_args(
        self,
        entry: "ScriptEntry",
    ) -> list[str]:
        """收集 CLI 参数（不含芯片参数展开，由调用方处理）。"""
        from tod.scripting import CliParam

        extra_args: list[str] = []
        skip_flags: set[str] = set()
        for selector in entry.catalog_seed_selectors:
            state = self._catalog_seed_selectors.get(selector.key)
            if state is not None and not state.enabled_checkbox.isChecked():
                skip_flags.update(
                    {
                        selector.seed_id_flag,
                        selector.jacobi_flag,
                        selector.jacobi_tolerance_flag,
                        selector.period_multiplier_flag,
                        selector.num_points_flag,
                    }
                )
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None or cli_param.flag in skip_flags:
                continue
            container = self._row_containers.get(key)
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
                    std_text = self.to_standard_unit(widget)
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

        for selector in entry.catalog_seed_selectors:
            state = self._catalog_seed_selectors.get(selector.key)
            if state is None or not state.enabled_checkbox.isChecked():
                continue
            mode_widget = getattr(state, "mode_widget", None)
            if (
                isinstance(mode_widget, QComboBox)
                and mode_widget.currentData() == selector.mode_jacobi_key
            ):
                jacobi_widget = getattr(state, "jacobi_widget", None)
                tolerance_widget = getattr(state, "tolerance_widget", None)
                if isinstance(jacobi_widget, QLineEdit) and jacobi_widget.text().strip():
                    extra_args.extend([selector.jacobi_flag, jacobi_widget.text().strip()])
                if isinstance(tolerance_widget, QLineEdit) and tolerance_widget.text().strip():
                    extra_args.extend([selector.jacobi_tolerance_flag, tolerance_widget.text().strip()])
                continue
            if isinstance(state.selector_widget, QComboBox):
                seed_id = state.selector_widget.currentData()
                if seed_id:
                    extra_args.extend([selector.seed_id_flag, str(seed_id)])

        return extra_args

    def collect_env_overrides(
        self,
        entry: "ScriptEntry",
    ) -> dict[str, str]:
        """收集环境变量覆盖。"""
        env_overrides: dict[str, str] = {}
        for key, combo in self._env_widgets.items():
            abs_path = combo.currentData()
            if abs_path and key in entry.env_params:
                env_param = entry.env_params[key]
                env_overrides[env_param.env_var] = abs_path

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

    def collect_chip_selections(
        self,
        entry: "ScriptEntry",
    ) -> dict[str, list[str]]:
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
                for chip_param in entry.cli_chip_params:
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
        """从表格控件收集多文件参数配置。"""
        from PyQt6.QtWidgets import QTableWidget

        configs: dict[str, list[dict]] = {}
        for key, widget in self._multi_file_widgets.items():
            table = widget.findChild(QTableWidget)
            if table is None:
                continue
            per_fields = getattr(table, "_per_file_fields", [])
            file_configs: list[dict] = []
            for row in range(table.rowCount()):
                name_item = table.item(row, 0)
                if name_item is None:
                    continue
                from PyQt6.QtCore import Qt

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

    def validate_params(
        self,
        parent: QWidget,
        entry: "ScriptEntry",
        tr: Callable[[str], str] = lambda s: s,
    ) -> bool:
        """验证参数，返回 True 表示通过。"""
        from pathlib import Path

        from PyQt6.QtWidgets import QMessageBox

        from tod.gui.i18n import qt_format

        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            container = self._row_containers.get(key)
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
                        parent,
                        tr("参数缺失"),
                        qt_format(tr("工具需要参数 '%1'，但未填写。"), cli_param.label),
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
                            parent,
                            tr("参数无效"),
                            qt_format(tr("参数 '%1' 需要数值，当前输入 '%2' 无效。"), cli_param.label, text),
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
                        parent,
                        tr("文件不存在"),
                        qt_format(tr("参数 '%1' 引用的文件不存在：\n%2\n\n仍然继续？"), cli_param.label, text),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return False

        return True
