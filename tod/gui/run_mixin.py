"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

from itertools import product
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QSpinBox,
)

from tod.plot.config import body_icon_env_from_settings, plot_font_env_from_settings
from tod.gui.file_operations import FILE_PATH_ROLE


class RunMixin:
    """提供参数收集、运行和验证方法，由 MainWindow 通过多重继承混入。"""

    def _collect_chip_selections(self) -> dict[str, list[str]]:
        """收集所有多选芯片参数的当前选择值。

        Returns:
            {flag_key: [selected_values]}，如 {"libration_point": ["L1", "L2"], "halo_class": ["0"]}
        """
        selections: dict[str, list[str]] = {}
        for key, container in self._chip_widgets.items():
            # 从容器中获取芯片按钮的状态
            if hasattr(container, "_chip_buttons"):
                selected = []
                for label, btn in container._chip_buttons.items():
                    if btn.property("_selected"):
                        selected.append(label)
                if selected:
                    # 查找对应的 flag
                    if self._current_script:
                        for chip_param in self._current_script.cli_chip_params:
                            chip_key = chip_param.flag.lstrip("-").replace("-", "_")
                            if chip_key == key:
                                # 将显示标签转换为 CLI 值
                                cli_values = []
                                for sel in selected:
                                    if sel in chip_param.options:
                                        cli_values.append(chip_param.options[sel])
                                selections[key] = cli_values
                                break
        return selections

    def _collect_multi_file_configs(self) -> dict[str, list[dict]]:
        """收集所有多文件参数的当前配置。

        Returns:
            {key: [config_dicts]}，如 {"json_file": [{"path": "a.json", "start": 0, "end": 10, "step": 1}, ...]}
        """
        from PyQt6.QtWidgets import QListWidget

        configs: dict[str, list[dict]] = {}
        for key, widget in self._multi_file_widgets.items():
            # 找到 ListWidget
            list_widget = widget.findChild(QListWidget)
            if list_widget is None:
                continue
            file_configs = []
            for path, config in list_widget._file_items.items():
                file_configs.append(config.copy())
            if file_configs:
                configs[key] = file_configs
        return configs

    def _expand_combinations(
        self,
        base_args: list[str],
        chip_selections: dict[str, list[str]],
    ) -> list[list[str]]:
        """展开芯片选择的所有组合。

        Args:
            base_args: 基础命令行参数（不含芯片参数）
            chip_selections: {key: [values]}，如 {"libration_point": ["L1", "L2"], "halo_class": ["0", "1"]}

        Returns:
            [args1, args2, ...]，每个 args 是完整的一组命令行参数
        """
        if not chip_selections:
            return [base_args]

        # 构建芯片参数列表
        chip_params_list: list[tuple[str, list[str]]] = []
        for key, values in chip_selections.items():
            # 查找对应的 flag
            flag = None
            if self._current_script:
                for chip_param in self._current_script.cli_chip_params:
                    chip_key = chip_param.flag.lstrip("-").replace("-", "_")
                    if chip_key == key:
                        flag = chip_param.flag
                        break
            if flag and values:
                chip_params_list.append((flag, values))

        if not chip_params_list:
            return [base_args]

        # 生成所有组合
        combinations: list[list[str]] = []
        for combo in product(*[vals for _, vals in chip_params_list]):
            args = base_args.copy()
            for (flag, _), value in zip(chip_params_list, combo):
                args.extend([flag, value])
            combinations.append(args)

        return combinations

    def _on_run(self) -> None:
        if self._current_script is None:
            return

        # 收集芯片参数的选择
        chip_selections = self._collect_chip_selections()

        # 收集多文件参数配置
        multi_file_configs = self._collect_multi_file_configs()

        # 收集环境变量参数（文件选择）
        env_overrides: dict[str, str] = {}
        for key, combo in self._env_widgets.items():
            abs_path = combo.currentData()
            if abs_path and key in self._current_script.env_params:
                env_param = self._current_script.env_params[key]
                env_overrides[env_param.env_var] = abs_path

        # 收集命令行参数（跳过被 hidden_when 隐藏的控件）
        extra_args: list[str] = []
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            # Skip widgets whose row container is hidden
            container = self._cli_row_containers.get(key)
            if container is not None and not container.isVisible():
                continue

            if isinstance(widget, QCheckBox):
                if widget.isChecked():
                    extra_args.append(cli_param.flag)
            elif isinstance(widget, QSpinBox):
                val = widget.value()
                # Use factory default (not saved UI default) for CLI emission decision
                factory_default = self._factory_defaults.get(widget, "")
                if factory_default:
                    if abs(val - float(factory_default)) > 1e-9:
                        extra_args.extend([cli_param.flag, str(val)])
                elif abs(val) > 1e-9:
                    extra_args.extend([cli_param.flag, str(val)])
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                default = self._param_defaults.get(widget, "")
                # 带单位的参数：先转到标准单位再比较
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
                    # 显示标签 → CLI 值映射
                    if cli_param.choice_values and text in cli_param.choice_values:
                        text = cli_param.choice_values[text]
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

        env_overrides.update(plot_font_env_from_settings(self._gui_defaults.get("settings", {})))
        env_overrides.update(body_icon_env_from_settings(self._gui_defaults.get("settings", {})))

        # 展开芯片参数组合
        all_args_combinations = self._expand_combinations(extra_args, chip_selections)

        # 添加多文件参数到每个参数组合
        for args in all_args_combinations:
            for key, configs in multi_file_configs.items():
                if not configs:
                    continue
                # 查找对应的 flag
                flag = None
                if self._current_script:
                    for multi_param in self._current_script.multi_cli_params:
                        multi_key = multi_param.flag.lstrip("-").replace("-", "_")
                        if multi_key == key:
                            flag = multi_param.flag
                            break
                if flag and configs:
                    # JSON 序列化配置
                    import json as _json

                    args.extend([flag, _json.dumps(configs)])

        # 对每个组合启动一个 Job
        for args in all_args_combinations:
            self._job_manager.start_job(self._current_script, args, env_overrides.copy())

    def _validate_params(self) -> bool:
        """验证参数，返回 True 表示通过。"""
        for key, widget in self._cli_widgets.items():
            cli_param = self._find_cli_param(key)
            if cli_param is None:
                continue

            # 必需文件参数验证
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
                        "参数缺失",
                        f"脚本需要参数 '{cli_param.label}'，但未填写。",
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
