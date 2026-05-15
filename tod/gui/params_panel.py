"""参数面板控件工厂：根据 CliParam 定义创建 Qt 控件。"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

if TYPE_CHECKING:
    from tod.gui.script_registry import CliParam

from tod.gui.file_discovery import FileInfo, filter_files
from tod.gui.script_registry import UNIT_GROUPS


class CliWidgetFactory:
    """根据 CliParam 规范创建 Qt 控件，管理布尔/数值/字符串/文件等类型。"""

    def __init__(
        self,
        files: list[FileInfo],
        on_path_mode_changed,
        on_unit_changed,
    ):
        self._files = files
        self._on_path_mode_changed = on_path_mode_changed
        self._on_unit_changed = on_unit_changed

        self.wrapped_widgets: dict[QWidget, QWidget] = {}
        self.path_mode_toggles: dict[QComboBox, QComboBox] = {}
        self.unit_combos: dict[QLineEdit, QComboBox] = {}
        self.unit_groups: dict[QLineEdit, str] = {}

    def reset(self) -> None:
        self.wrapped_widgets.clear()
        self.path_mode_toggles.clear()
        self.unit_combos.clear()
        self.unit_groups.clear()

    def make_widget(self, cli_param: CliParam) -> tuple[str, QWidget]:
        """根据 CliParam 创建控件，返回 (key, widget)。"""
        key = cli_param.flag.lstrip("-").replace("-", "_")

        if cli_param.param_type == "bool":
            widget: QCheckBox | QLineEdit | QSpinBox | QComboBox = QCheckBox(cli_param.label)
            widget.setToolTip(cli_param.help)
        elif cli_param.choices:
            widget = QComboBox()
            widget.addItems(cli_param.choices)
            if cli_param.default in cli_param.choices:
                widget.setCurrentText(cli_param.default)
            widget.setToolTip(cli_param.help)
            widget.setSizePolicy(
                QWidget().sizePolicy().Policy.Expanding,
                QWidget().sizePolicy().Policy.Fixed,
            )
            widget.setMinimumWidth(80)
        elif cli_param.param_type == "int":
            widget = QSpinBox()
            widget.setRange(-99999, 99999)
            if cli_param.default:
                widget.setValue(int(cli_param.default))
            widget.setToolTip(cli_param.help)
            widget.setSizePolicy(
                QWidget().sizePolicy().Policy.Expanding,
                QWidget().sizePolicy().Policy.Fixed,
            )
            widget.setMinimumWidth(80)
        elif cli_param.param_type == "float":
            widget = QLineEdit()
            validator = QDoubleValidator(-99999.0, 99999.0, 15)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            widget.setValidator(validator)
            if cli_param.default:
                widget.setText(cli_param.default)
            widget.setToolTip(cli_param.help)
            widget.setSizePolicy(
                QWidget().sizePolicy().Policy.Expanding,
                QWidget().sizePolicy().Policy.Fixed,
            )
            widget.setMinimumWidth(100)
        else:  # str
            if cli_param.file_category:
                widget = self._make_file_combo(cli_param)
            else:
                widget = QLineEdit()
                if cli_param.default:
                    widget.setText(cli_param.default)
                widget.setToolTip(cli_param.help)
                widget.setSizePolicy(
                    QWidget().sizePolicy().Policy.Expanding,
                    QWidget().sizePolicy().Policy.Fixed,
                )
                widget.setMinimumWidth(100)

        # 带单位的 float 参数：用单位选择器包裹
        if (
            cli_param.param_type == "float"
            and cli_param.unit_group
            and cli_param.unit_group in UNIT_GROUPS
        ):
            self._wrap_with_unit_selector(cli_param, cast(QLineEdit, widget))

        return key, widget

    def display_widget(self, widget: QWidget) -> QWidget:
        """返回用于布局的显示控件（可能已被包裹）。"""
        return self.wrapped_widgets.get(widget, widget)

    # ── private helpers ──────────────────────────────────────────

    def _make_file_combo(self, cli_param: CliParam) -> QComboBox:
        is_relative = cli_param.path_mode == "relative"
        file_combo = QComboBox()
        file_combo.setEditable(True)
        file_combo.addItem("")
        matching = filter_files(
            self._files,
            category=cli_param.file_category,
            file_type="json",
            name_pattern=cli_param.name_pattern,
        )
        for fi in matching:
            file_combo.addItem(fi.path if is_relative else fi.abs_path)
        if cli_param.default:
            file_combo.setCurrentText(cli_param.default)
        file_combo.setToolTip(cli_param.help)
        file_combo.setSizePolicy(
            QWidget().sizePolicy().Policy.Expanding,
            QWidget().sizePolicy().Policy.Fixed,
        )
        file_combo.setMinimumWidth(100)

        # 路径模式切换
        mode_combo = QComboBox()
        mode_combo.addItems(["绝对", "相对"])
        mode_combo.setCurrentText("相对" if is_relative else "绝对")
        mode_combo.setMinimumContentsLength(2)
        mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        mode_combo.setProperty("file_category", cli_param.file_category)
        mode_combo.setProperty("name_pattern", cli_param.name_pattern)
        mode_combo.currentIndexChanged.connect(
            lambda _, fc=file_combo, mc=mode_combo: self._on_path_mode_changed(fc, mc)
        )

        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(4)
        file_layout.addWidget(file_combo, stretch=1)
        file_layout.addWidget(mode_combo)

        container = QWidget()
        container.setLayout(file_layout)
        self.wrapped_widgets[file_combo] = container
        self.path_mode_toggles[file_combo] = mode_combo

        return file_combo

    def _wrap_with_unit_selector(self, cli_param: CliParam, widget: QLineEdit) -> None:
        ug = cli_param.unit_group
        if ug is None or ug not in UNIT_GROUPS:
            return

        field_layout = QHBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)

        unit_combo = QComboBox()
        unit_combo.addItems(UNIT_GROUPS[ug].keys())
        unit_combo.setMinimumContentsLength(3)
        unit_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        default_idx = 0
        if cli_param.default_unit:
            units = list(UNIT_GROUPS[ug].keys())
            if cli_param.default_unit in units:
                default_idx = units.index(cli_param.default_unit)
        unit_combo.setCurrentIndex(default_idx)
        unit_combo.setProperty("prev_idx", default_idx)

        if default_idx != 0 and cli_param.default:
            try:
                group = UNIT_GROUPS[ug]
                units = list(group.keys())
                std_val = float(cli_param.default)
                display_val = std_val / group[units[default_idx]]
                widget.setText(f"{display_val:.10g}")
            except (ValueError, ZeroDivisionError):
                pass

        unit_combo.currentIndexChanged.connect(
            lambda _, le=widget, uc=unit_combo, g=ug: self._on_unit_changed(le, uc, g)
        )

        field_layout.addWidget(widget)
        field_layout.addWidget(unit_combo)

        self.unit_combos[widget] = unit_combo
        self.unit_groups[widget] = ug

        wrapper = QWidget()
        wrapper.setLayout(field_layout)
        self.wrapped_widgets[widget] = wrapper
