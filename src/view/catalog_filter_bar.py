"""库过滤栏 -- 项目树顶部的多维过滤（issue #375，ADR 0009 自动表单范式）。

过滤字段与取值域经 ``e2m2e.api.models.CatalogQueryRequest`` 的公开接口生成
（Field description 枚举族名与平动点范围），e2m2e 演进时取值域跟随。
组合维度：族 / 平动点 / Jacobi 区间 / 振幅区间 / 段存在性（逻辑与）。
"""

from __future__ import annotations

import re

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


def _family_options() -> list[str]:
    """从 CatalogQueryRequest.orbit_family 的 description 解析族名取值域。"""
    from e2m2e.api.models import CatalogQueryRequest

    field = CatalogQueryRequest.model_fields.get("orbit_family")
    description = getattr(field, "description", None) or ""
    # 形如 "轨道族（dro/halo/.../elfo 等）"：截到 "等" 前，取连续小写词
    return re.findall(r"[a-z]+", description.split("等")[0])


def _libration_point_options() -> list[int]:
    """从 CatalogQueryRequest.libration_point 的 description 解析编号范围。"""
    from e2m2e.api.models import CatalogQueryRequest

    field = CatalogQueryRequest.model_fields.get("libration_point")
    description = getattr(field, "description", None) or ""
    match = re.search(r"(\d+)\s*[–-]\s*(\d+)", description)
    if match:
        lo, hi = int(match.group(1)), int(match.group(2))
        if 1 <= lo <= hi <= 9:
            return list(range(lo, hi + 1))
    return [1, 2, 3, 4, 5]


class CatalogFilterBar(QWidget):
    """catalog 多维过滤栏。

    Signals:
        filters_changed(dict): 任一控件变化即发出当前过滤条件
            （CatalogQueryRequest 的字段子集，未启用的维度不在 dict 中）。
        export_requested(): 「导出案例包」按钮。
    """

    filters_changed = pyqtSignal(dict)
    export_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._family_combo = QComboBox()
        self._family_combo.addItem("全部族", None)
        for family in _family_options():
            self._family_combo.addItem(family, family)

        self._point_combo = QComboBox()
        self._point_combo.addItem("全部平动点", None)
        for point in _libration_point_options():
            self._point_combo.addItem(f"L{point}", point)

        self._jacobi_check = QCheckBox("Jacobi")
        self._jacobi_min = self._make_spin(1.0, 5.0, 3.0, 0.01, 3)
        self._jacobi_max = self._make_spin(1.0, 5.0, 3.2, 0.01, 3)
        self._amplitude_check = QCheckBox("振幅 km")
        self._amplitude_min = self._make_spin(0.0, 1e6, 0.0, 100.0, 1)
        self._amplitude_max = self._make_spin(0.0, 1e6, 50000.0, 100.0, 1)

        self._cr3bp_combo = self._make_tri_combo("CR3BP 段")
        self._ephemeris_combo = self._make_tri_combo("星历段")

        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self.reset)
        export_btn = QPushButton("导出案例包")
        export_btn.clicked.connect(self.export_requested.emit)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(2)
        grid.addWidget(self._family_combo, 0, 0)
        grid.addWidget(self._point_combo, 0, 1)
        grid.addWidget(self._cr3bp_combo, 0, 2)
        grid.addWidget(self._ephemeris_combo, 0, 3)

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(self._jacobi_check)
        row1.addWidget(self._jacobi_min)
        row1.addWidget(QLabel("–"))
        row1.addWidget(self._jacobi_max)
        grid.addLayout(row1, 1, 0, 1, 2)

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.addWidget(self._amplitude_check)
        row2.addWidget(self._amplitude_min)
        row2.addWidget(QLabel("–"))
        row2.addWidget(self._amplitude_max)
        grid.addLayout(row2, 1, 2, 1, 2)

        grid.addWidget(reset_btn, 2, 0, 1, 2)
        grid.addWidget(export_btn, 2, 2, 1, 2)

        # 任一控件变化即重查（SQLite 索引查询为毫秒级，不需要"应用"按钮）
        for combo in (
            self._family_combo,
            self._point_combo,
            self._cr3bp_combo,
            self._ephemeris_combo,
        ):
            combo.currentIndexChanged.connect(lambda _idx: self._emit())
        for check in (self._jacobi_check, self._amplitude_check):
            check.toggled.connect(lambda _checked: self._emit())
        for spin in (self._jacobi_min, self._jacobi_max, self._amplitude_min, self._amplitude_max):
            spin.valueChanged.connect(lambda _value: self._emit())

    # -- 公共 API -----------------------------------------------------------

    def filters(self) -> dict:
        """收集当前过滤条件（未启用的维度不进 dict，交给模型填默认）。"""
        result: dict = {}
        if self._family_combo.currentData() is not None:
            result["orbit_family"] = self._family_combo.currentData()
        if self._point_combo.currentData() is not None:
            result["libration_point"] = self._point_combo.currentData()
        if self._jacobi_check.isChecked():
            result["jacobi_min"] = self._jacobi_min.value()
            result["jacobi_max"] = self._jacobi_max.value()
        if self._amplitude_check.isChecked():
            result["amplitude_min_km"] = self._amplitude_min.value()
            result["amplitude_max_km"] = self._amplitude_max.value()
        if self._cr3bp_combo.currentData() is not None:
            result["has_cr3bp"] = self._cr3bp_combo.currentData()
        if self._ephemeris_combo.currentData() is not None:
            result["has_ephemeris"] = self._ephemeris_combo.currentData()
        return result

    def reset(self) -> None:
        """恢复默认（全部维度不设限）并发出空过滤。"""
        self._family_combo.setCurrentIndex(0)
        self._point_combo.setCurrentIndex(0)
        self._cr3bp_combo.setCurrentIndex(0)
        self._ephemeris_combo.setCurrentIndex(0)
        self._jacobi_check.setChecked(False)
        self._amplitude_check.setChecked(False)

    # -- 内部 ---------------------------------------------------------------

    @staticmethod
    def _make_spin(
        minimum: float, maximum: float, value: float, step: float, decimals: int
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        return spin

    @staticmethod
    def _make_tri_combo(title: str) -> QComboBox:
        combo = QComboBox()
        combo.setToolTip(title)
        combo.addItem("不限", None)
        combo.addItem("含", True)
        combo.addItem("不含", False)
        return combo

    def _emit(self) -> None:
        self.filters_changed.emit(self.filters())
