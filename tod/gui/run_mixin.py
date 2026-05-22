"""运行与验证 Mixin — 参数收集、运行和验证逻辑。"""

from __future__ import annotations

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
            cli_param = self._find_cli_param(key)
            if cli_param is None:
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

        self._job_manager.start_job(self._current_script, extra_args, env_overrides)

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
