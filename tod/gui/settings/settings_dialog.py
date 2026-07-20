"""PyQt6 图形界面组件。

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

@dataclass
class SettingItem:
    """单个设置项的定义。"""
    key: str
    label: str
    type: str  # "choice" | "int" | "float" | "bool"
    choices: list[str] | None = None  # 仅 choice 类型
    choice_labels: list[str] | None = None  # 选项的显示标签；省略则直接用 choices 值
    default: str = ""
    min_value: float = 0  # int 与 float 共用；类型由 type 字段决定
    max_value: float = 999
    decimals: int = 2  # 仅 float 类型生效
    step: float = 0.05  # 仅 float 类型生效
    on_changed: Callable[[str], None] | None = None

class SettingsDialog(QDialog):
    """设置对话框。
    
    用于编辑应用设置项，支持选择/整数/浮点数等类型。
    """
    def __init__(self, settings: dict[str, str], schema: list[SettingItem], parent=None):
        super().__init__(parent)
        self._settings = settings
        self._schema = schema
        self._controls: dict[str, QWidget] = {}

        self.setWindowTitle("Settings")
        self.setMinimumWidth(300)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        for item in self._schema:
            label = QLabel(item.label)
            if item.type == "choice":
                combo = QComboBox()
                display_labels = item.choice_labels or item.choices or []
                combo.addItems(display_labels)
                current = self._settings.get(item.key, item.default)
                choices = item.choices or []
                if current in choices:
                    idx = choices.index(current)
                    combo.setCurrentIndex(idx)
                form.addRow(label, combo)
                self._controls[item.key] = combo
            elif item.type == "int":
                spin = QSpinBox()
                spin.setRange(int(item.min_value), int(item.max_value))
                current = self._settings.get(item.key, item.default)
                try:
                    spin.setValue(int(float(current)))
                except ValueError:
                    spin.setValue(int(float(item.default or item.min_value)))
                form.addRow(label, spin)
                self._controls[item.key] = spin
            elif item.type == "float":
                dspin = QDoubleSpinBox()
                dspin.setRange(float(item.min_value), float(item.max_value))
                dspin.setDecimals(item.decimals)
                dspin.setSingleStep(item.step)
                current = self._settings.get(item.key, item.default)
                try:
                    dspin.setValue(float(current))
                except ValueError:
                    dspin.setValue(float(item.default or item.min_value))
                form.addRow(label, dspin)
                self._controls[item.key] = dspin
            elif item.type == "bool":
                # 暂不使用复选框，统一用选择框
                pass

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        for key, control in self._controls.items():
            if isinstance(control, QComboBox):
                item = next((s for s in self._schema if s.key == key), None)
                idx = control.currentIndex()
                choices = (item.choices or []) if item else []
                if 0 <= idx < len(choices):
                    self._settings[key] = choices[idx]
            elif isinstance(control, QDoubleSpinBox):
                # 必须先于 QSpinBox 判断：QDoubleSpinBox 不是 QSpinBox 子类，
                # 此顺序明确表达 float 优先于 int 的语义
                self._settings[key] = f"{control.value():g}"
            elif isinstance(control, QSpinBox):
                self._settings[key] = str(control.value())
        self.accept()

    def get_settings(self) -> dict[str, str]:
        """获取当前设置值。
        
        Returns:
            设置键值对字典。
        """
        return self._settings
