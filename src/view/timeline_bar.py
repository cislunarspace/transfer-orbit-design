"""时间轴控件（ADR-0014）——画布下方的时刻选择滑块。

纯 UI 控件：滑块（0.._STEPS 线性映射到 et 区间）+ UTC 时刻标签。
拖动经 100ms 单次节流定时器发射 ``et_changed``（拖动中约 10 Hz 重绘），
信号由 main_window 连接，写入 CanvasState.current_et 并触发 render()。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QSlider, QVBoxLayout, QWidget

_STEPS = 1000
_THROTTLE_MS = 100


class TimelineBar(QWidget):
    """时刻选择滑块 + UTC 标签。

    Attributes:
        et_changed: 节流后的当前时刻（ET 秒）。
        slider: 底层滑块（main_window 灰显经 set_unavailable）。
        time_label: 当前时刻 UTC 显示。
    """

    et_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._et_min = 0.0
        self._et_max = 0.0

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, _STEPS)
        self.time_label = QLabel("时间轴")
        self.time_label.setMinimumWidth(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)
        layout.addWidget(self.slider)
        layout.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 10 Hz 周期节流（ADR 0014 决策 5）：按住拖动期间周期发射，
        # 松手后补发最终值并停止——拖动中画布持续刷新，不是静止后才动
        self._timer = QTimer(self)
        self._timer.setInterval(_THROTTLE_MS)
        self._timer.timeout.connect(lambda: self.et_changed.emit(self.current_et()))
        self.slider.sliderPressed.connect(self._timer.start)
        self.slider.sliderReleased.connect(self._release)
        self.slider.valueChanged.connect(lambda _v: self._update_label(self.current_et()))
        self.setEnabled(False)

    # -- 区间与状态 ---------------------------------------------------------

    def set_time_range(self, et_min: float, et_max: float) -> None:
        """设置时刻区间并启用滑块，默认停在起点（issue #395）。"""
        self._et_min = float(et_min)
        self._et_max = float(et_max)
        self.slider.blockSignals(True)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._update_label(self._et_min)
        self.setEnabled(True)

    def range_is(self, et_min: float, et_max: float) -> bool:
        """当前区间是否已是给定值（避免重复重置滑块位置）。"""
        return self.isEnabled() and self._et_min == et_min and self._et_max == et_max

    def set_unavailable(self) -> None:
        """无星历产物可见：灰显（ADR-0014 决策 2）。"""
        self._timer.stop()
        self.setEnabled(False)
        self.time_label.setText("时间轴（无星历数据）")

    def current_et(self) -> float:
        return self._slider_to_et(self.slider.value())

    def set_et(self, et: float) -> None:
        """程序化设置时刻（不发射信号、不动节流定时器）。"""
        if et < self._et_min or et > self._et_max:
            return
        self.slider.blockSignals(True)
        self.slider.setValue(self._et_to_slider(et))
        self.slider.blockSignals(False)
        self._update_label(et)

    # -- 内部 ---------------------------------------------------------------

    def _release(self) -> None:
        """松手：停止周期发射并补发最终值。"""
        self._timer.stop()
        self.et_changed.emit(self.current_et())

    def _slider_to_et(self, value: int) -> float:
        if self._et_max <= self._et_min:
            return self._et_min
        return self._et_min + (self._et_max - self._et_min) * value / _STEPS

    def _et_to_slider(self, et: float) -> int:
        if self._et_max <= self._et_min:
            return 0
        return round((et - self._et_min) / (self._et_max - self._et_min) * _STEPS)

    def _update_label(self, et: float) -> None:
        from src.engine.viz_adapter import et_to_utc_label

        self.time_label.setText(et_to_utc_label(et))

    def _flush(self) -> None:
        """立即触发一次周期发射（测试用，模拟节流周期到期）。"""
        self.et_changed.emit(self.current_et())
