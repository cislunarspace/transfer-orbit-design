"""参数收集层：把当前控件状态转成 CLI 参数 / 环境变量 / 芯片选择 / 多文件配置。

每个方法都是 ``@staticmethod``，接收所需的 widget 字典与 ``find_cli_param``
回调，避免对 ``ScriptTabWidget`` 类的反向依赖。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QMessageBox, QSpinBox, QTableWidget, QWidget

from tod.gui.script_registry import CliParam, ScriptEntry


class ScriptParamCollector:
    """从控件字典中收集参数。"""

    @staticmethod
    def collect_run_args(
        entry: ScriptEntry,
        cli_widgets: Mapping[str, QWidget],
        cli_row_containers: Mapping[str, QWidget],
        param_defaults: Mapping[QWidget, str],
        factory_defaults: Mapping[QWidget, str],
        to_standard_unit: Callable[[QLineEdit], str],
        unit_combos: Mapping[QLineEdit, QComboBox],
        find_cli_param: Callable[[str], CliParam | None],
    ) -> list[str]:
        """收集 CLI 参数（不含芯片参数展开，由调用方处理）。"""
        extra_args: list[str] = []
        for key, widget in cli_widgets.items():
            cli_param = find_cli_param(key)
            if cli_param is None:
                continue
            container = cli_row_containers.get(key)
            if container is not None and container.isHidden():
                continue

            if isinstance(widget, QCheckBox):
                if widget.isChecked():
                    extra_args.append(cli_param.flag)
            elif isinstance(widget, QSpinBox):
                val = widget.value()
                factory_default = factory_defaults.get(widget, "")
                if factory_default:
                    if abs(val - float(factory_default)) > 1e-9:
                        extra_args.extend([cli_param.flag, str(val)])
                elif val != 0:
                    extra_args.extend([cli_param.flag, str(val)])
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                default = param_defaults.get(widget, "")
                if widget in unit_combos:
                    std_text = to_standard_unit(widget)
                    if std_text and std_text != default:
                        extra_args.extend([cli_param.flag, std_text])
                elif text and text != default:
                    extra_args.extend([cli_param.flag, text])
            elif isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                default = param_defaults.get(widget, "")
                if text and text != default:
                    if cli_param.choice_values and text in cli_param.choice_values:
                        text = cli_param.choice_values[text]
                    extra_args.extend([cli_param.flag, text])

        return extra_args

    @staticmethod
    def collect_env_overrides(
        entry: ScriptEntry,
        env_widgets: Mapping[str, QComboBox],
        cli_widgets: Mapping[str, QWidget],
        param_defaults: Mapping[QWidget, str],
        find_cli_param: Callable[[str], CliParam | None],
    ) -> dict[str, str]:
        """收集环境变量覆盖。"""
        env_overrides: dict[str, str] = {}
        for key, combo in env_widgets.items():
            abs_path = combo.currentData()
            if abs_path and key in entry.env_params:
                env_param = entry.env_params[key]
                env_overrides[env_param.env_var] = abs_path

        # CLI 文件参数的 env 同步
        _CLI_TO_ENV: dict[str, str] = {
            "--dro-file": "DRO_FILE",
            "--ro-file": "RO_FILE",
            "--search-file": "SEARCH_RESULTS_FILE",
        }
        for key, widget in cli_widgets.items():
            cli_param = find_cli_param(key)
            if cli_param is None or not cli_param.file_category:
                continue
            if isinstance(widget, QComboBox):
                text = widget.currentText().strip()
                default = param_defaults.get(widget, "")
                if text and text != default:
                    env_var = _CLI_TO_ENV.get(cli_param.flag)
                    if env_var:
                        env_overrides[env_var] = text

        return env_overrides

    @staticmethod
    def collect_chip_selections(
        entry: ScriptEntry,
        chip_widgets: Mapping[str, QWidget],
    ) -> dict[str, list[str]]:
        """收集芯片参数选择。"""
        selections: dict[str, list[str]] = {}
        for key, container in chip_widgets.items():
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

    @staticmethod
    def collect_multi_file_configs(
        multi_file_widgets: Mapping[str, QWidget],
    ) -> dict[str, list[dict]]:
        """从表格控件收集多文件参数配置。

        遍历每行，读取文件路径（UserRole data）和 per-file 字段值，
        构建与 CLI --json-file 参数兼容的 JSON 列表。
        """
        configs: dict[str, list[dict]] = {}
        for key, widget in multi_file_widgets.items():
            table = widget.findChild(QTableWidget)
            if table is None:
                continue
            per_fields = getattr(table, "_per_file_fields", [])
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

    @staticmethod
    def validate_params(
        parent: QWidget,
        entry: ScriptEntry,
        cli_widgets: Mapping[str, QWidget],
        cli_row_containers: Mapping[str, QWidget],
        find_cli_param: Callable[[str], CliParam | None],
        tr: Callable[[str], str] = lambda s: s,
    ) -> bool:
        """验证参数，返回 True 表示通过。"""
        for key, widget in cli_widgets.items():
            cli_param = find_cli_param(key)
            if cli_param is None:
                continue

            container = cli_row_containers.get(key)
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
                        tr("脚本需要参数 '{}'，但未填写。").format(cli_param.label),
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
                            tr("参数 '{}' 需要数值，当前输入 '{}' 无效。").format(cli_param.label, text),
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
                        tr("参数 '{}' 引用的文件不存在：\n{}\n\n仍然继续？").format(cli_param.label, text),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return False

        return True
