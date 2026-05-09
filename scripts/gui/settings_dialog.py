"""设置对话框 — 动态渲染 SETTINGS_SCHEMA 中的所有设置项。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
    type: str  # "choice" | "int" | "bool"
    choices: list[str] | None = None  # 仅 choice 类型
    default: str = ""
    min_value: int = 0
    max_value: int = 999
    on_changed: Callable[[str], None] | None = None


class SettingsDialog(QDialog):
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
                combo.addItems(item.choices or [])
                current = self._settings.get(item.key, item.default)
                if current in (item.choices or []):
                    combo.setCurrentText(current)
                form.addRow(label, combo)
                self._controls[item.key] = combo
            elif item.type == "int":
                spin = QSpinBox()
                spin.setRange(item.min_value, item.max_value)
                current = self._settings.get(item.key, item.default)
                try:
                    spin.setValue(int(float(current)))
                except ValueError:
                    spin.setValue(int(float(item.default or item.min_value)))
                form.addRow(label, spin)
                self._controls[item.key] = spin
            elif item.type == "bool":
                # 暂不使用 checkbox，统一用 choice
                pass

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        for key, control in self._controls.items():
            if isinstance(control, QComboBox):
                self._settings[key] = control.currentText()
            elif isinstance(control, QSpinBox):
                self._settings[key] = str(control.value())
        self.accept()

    def get_settings(self) -> dict[str, str]:
        return self._settings
