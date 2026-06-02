# pyright: reportAttributeAccessIssue=false, reportUndefinedVariable=false, reportOptionalMemberAccess=false
"""PyQt6 图形界面组件。

本模块为 Transfer Orbit Design 的脚本化工作流提供辅助类型、函数或入口。
"""


from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from tod.gui.script_registry import CliChipParam, CliParam

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
        """执行 reset 对应的处理逻辑。
        
        Returns:
            None。
        """
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
            # For step parameter, enforce minimum=1 to match range() semantics
            if cli_param.flag == "--step":
                widget.setMinimum(1)
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
        mode_combo.addItems([
            QCoreApplication.translate("CliWidgetFactory", "绝对"),
            QCoreApplication.translate("CliWidgetFactory", "相对"),
        ])
        mode_combo.setCurrentIndex(1 if is_relative else 0)
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

    def make_chip_widget(self, chip_param: CliChipParam) -> tuple[str, QWidget]:
        """创建多选芯片控件，返回 (key, container_widget)。

        Args:
            chip_param: 芯片参数定义

        Returns:
            (key, widget): key 是去掉前缀的 flag 名，widget 是包含芯片按钮的容器
        """
        key = chip_param.flag.lstrip("-").replace("-", "_")

        # 容器 widget
        container = QWidget()
        container.setObjectName(f"chip_container_{key}")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 存储芯片按钮的引用，用于状态切换
        chip_buttons: dict[str, QPushButton] = {}

        def _get_selected() -> set[str]:
            return {opt for opt, btn in chip_buttons.items() if btn.property("_selected")}

        def _update_button_style(btn: QPushButton, is_selected: bool) -> None:
            if is_selected:
                btn.setStyleSheet(
                    "QPushButton { "
                    "background-color: #4da6ff; color: white; border: 1px solid #4da6ff; "
                    "border-radius: 4px; padding: 4px 12px; font-weight: bold; "
                    "} "
                    "QPushButton:hover { background-color: #3d8fd9; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { "
                    "background-color: transparent; color: #666666; border: 1px solid #cccccc; "
                    "border-radius: 4px; padding: 4px 12px; "
                    "} "
                    "QPushButton:hover { background-color: #f0f0f0; border-color: #999999; }"
                )

        def _on_chip_clicked(option_label: str) -> None:
            btn = chip_buttons[option_label]
            current = btn.property("_selected")
            new_state = not current
            btn.setProperty("_selected", new_state)
            _update_button_style(btn, new_state)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        for option_label, option_value in chip_param.options.items():
            btn = QPushButton(option_label)
            btn.setCheckable(False)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # 检查是否默认选中
            is_selected = option_label == chip_param.default or option_value == chip_param.default
            btn.setProperty("_selected", is_selected)
            _update_button_style(btn, is_selected)

            btn.clicked.connect(lambda _, ol=option_label: _on_chip_clicked(ol))
            chip_buttons[option_label] = btn
            layout.addWidget(btn)

        layout.addStretch()

        container._chip_buttons = chip_buttons  # 用于外部访问按钮状态

        return key, container

    def make_multi_file_widget(
        self,
        multi_param,
        repo_root: str,
    ) -> tuple[str, QWidget]:
        """创建多文件控件（表格 + 添加按钮），每行显示文件名 + per-file 字段。

        Args:
            multi_param: MultiCliParam 实例（含 per_file_fields）
            repo_root: 项目根目录路径

        Returns:
            (key, container_widget)
        """
        key = multi_param.flag.lstrip("-").replace("-", "_")
        per_fields = multi_param.per_file_fields

        # 主容器
        container = QWidget()
        container.setObjectName(f"multi_file_container_{key}")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # 表头：文件名 | per-file 字段... | 删除
        headers = [QCoreApplication.translate("CliWidgetFactory", "文件名")]
        for f in per_fields:
            headers.append(f.label)
        headers.append("")  # 删除按钮列

        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        table.setMinimumHeight(0)
        table.setMaximumHeight(250)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(28)

        # 列宽策略：文件名拉伸，per-field 自适应，删除列固定
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(headers) - 1):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        delete_col = len(headers) - 1
        header.setSectionResizeMode(delete_col, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(delete_col, 60)

        # 存储引用，供 collect_multi_file_configs 读取
        table._per_file_fields = per_fields
        table._delete_col = delete_col

        # 添加文件按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        add_btn = QPushButton(QCoreApplication.translate("CliWidgetFactory", "添加文件"))
        add_btn.setToolTip(QCoreApplication.translate("CliWidgetFactory", "添加 JSON 文件到列表"))

        btn_layout.addWidget(add_btn)
        btn_layout.addStretch()

        # 添加文件回调
        def _on_add_clicked() -> None:
            filters = "JSON Files (*.json)"
            paths, _ = QFileDialog.getOpenFileNames(
                container,
                QCoreApplication.translate("CliWidgetFactory", "选择 JSON 文件"),
                repo_root,
                filters,
            )
            for path in paths:
                _add_file_row(table, path, per_fields, delete_col)

        add_btn.clicked.connect(_on_add_clicked)

        main_layout.addWidget(table)
        main_layout.addLayout(btn_layout)

        return key, container


def _add_file_row(
    table: QTableWidget,
    file_path: str,
    fields: list,
    delete_col: int,
) -> None:
    """向表格中添加一行文件配置。"""
    row = table.rowCount()
    table.insertRow(row)

    # Column 0: 文件名（只读）
    name_item = QTableWidgetItem(Path(file_path).name)
    name_item.setData(Qt.ItemDataRole.UserRole, file_path)
    name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    name_item.setToolTip(file_path)
    table.setItem(row, 0, name_item)

    # Column 1..N: per-file 字段
    for col, field_def in enumerate(fields, start=1):
        if field_def.field_type == "int":
            widget = QSpinBox()
            widget.setRange(
                int(field_def.min_value) if field_def.min_value is not None else -99999,
                int(field_def.max_value) if field_def.max_value is not None else 99999,
            )
            widget.setValue(int(field_def.default) if field_def.default else 0)
            widget.setToolTip(field_def.help)
            widget.setMinimumWidth(70)
        elif field_def.field_type == "float":
            widget = QLineEdit()
            validator = QDoubleValidator(-99999.0, 99999.0, 15)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            widget.setValidator(validator)
            if field_def.default:
                widget.setText(field_def.default)
            widget.setToolTip(field_def.help)
            widget.setMinimumWidth(70)
        else:
            widget = QLineEdit()
            if field_def.default:
                widget.setText(field_def.default)
            widget.setToolTip(field_def.help)
            widget.setMinimumWidth(70)
        table.setCellWidget(row, col, widget)

    # 最后一列：删除按钮
    del_btn = QPushButton(QCoreApplication.translate("CliWidgetFactory", "移除"))
    del_btn.setFixedWidth(50)

    def _on_delete(_checked, clicked_btn=del_btn, col_idx=delete_col) -> None:
        for r in range(table.rowCount()):
            if table.cellWidget(r, col_idx) is clicked_btn:
                table.removeRow(r)
                break
        table.updateGeometry()

    del_btn.clicked.connect(_on_delete)
    table.setCellWidget(row, delete_col, del_btn)
    table.updateGeometry()
