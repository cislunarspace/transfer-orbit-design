"""轨道保持对话框 -- 选中轨道后独立执行的模态弹窗。

参数构建复用 params_panel 的通用机制（build_params_from_model /
collect_params / 单位切换），运行逻辑（参数注入、时长校验、Worker
生命周期）自 MainWindow 迁入；产物入库由算法层完成，完成后经信号
回到主窗口重查清单并选中新记录。
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.engine.facade_bridge import TOOL_REGISTRY, ControlResultData
from src.engine.workers import ControlOrbitWorker
from src.model import Artifact
from src.view.log_panel import LogPanel
from src.view.params_panel import (
    build_params_from_model,
    collect_params,
    get_field_units,
    set_spinbox_unit,
)

#: 数字框收紧宽度（与主窗口参数面板一致，见 MainWindow._PARAM_SPINBOX_MAX_WIDTH）
_PARAM_SPINBOX_MAX_WIDTH = 110

# 上游控制器默认覆盖多年星历；GUI 的轨道设计默认输出短弧，因此首次轨道保持
# 使用已验证可覆盖 30 天标称星历的参数。用户仍可在面板中按任务需求调整。
_CONTROL_ORBIT_GUI_DEFAULTS = {
    "control_interval": 0.25,
    "feedback_arc": 0.125,
}

#: 轨道保持字段标签（自 MainWindow._DESIGN_ORBIT_LABELS 迁入；可切换单位字段
#: 的标签以" (标准单位)"结尾，切单位时剥离后缀重拼）。
_CONTROL_FIELD_LABELS: dict[str, str] = {
    "control_mode": "控制模式",
    "is_nrho": "目标为 NRHO",
    "special_mode": "特征点模式",
    "control_interval": "控制间隔 (天)",
    "feedback_arc": "反馈弧段 (天)",
    "special_crossings": "特征点穿越次数",
    "num_controls": "控制次数",
    "num_monte_carlo": "蒙特卡洛样本数",
    "position_accuracy": "测定轨位置误差 (m)",
    "velocity_accuracy": "测定轨速度误差 (m/s)",
    "thrust_angle_err": "推力方向角误差 (度)",
    "thrust_mean": "推力中点值 (m/s)",
    "thrust_rel_err": "推力相对误差",
    "thrust_abs_err": "推力绝对误差 (m/s)",
    "thrust_min": "最小开机推力 (m/s)",
    "thrust_max": "最大开机推力 (m/s)",
    "thrust_total": "累计推力上限 (m/s)",
    "srp_error_level": "光压弧段随机误差",
    "real_perturbation": "真实力模型摄动开关 (JSON)",
    "real_dyb": "真实力模型 DYB 面质比 (JSON)",
    "real_earth_degree": "真实地球引力位阶数",
    "real_moon_degree": "真实月球引力位阶数",
    "engine_layout": "发动机布局 (JSON)",
    "momentum_interval": "角动量卸载间隔 (天)",
    "srp_offset_m": "SRP 压心偏移 (m)",
    "spacecraft_mass": "航天器质量 (kg)",
    "srp_torque": "SRP 力矩 (N·m)",
    "tight_tolerance_km": "严格控制位置容差 (km)",
    "tight_max_iter": "严格控制迭代上限",
    "special_damping_factor": "特征点迭代阻尼因子",
    "output_step": "输出步长 (秒)",
}

#: 参数分组（组标题 + 字段），未分组字段归入自动追加的"其他"组。
_CONTROL_PARAM_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "控制参数",
        (
            "control_mode",
            "is_nrho",
            "special_mode",
            "control_interval",
            "feedback_arc",
            "special_crossings",
            "num_controls",
            "tight_tolerance_km",
            "tight_max_iter",
            "special_damping_factor",
        ),
    ),
    (
        "仿真与误差",
        (
            "num_monte_carlo",
            "output_step",
            "position_accuracy",
            "velocity_accuracy",
            "thrust_angle_err",
            "thrust_mean",
            "thrust_rel_err",
            "thrust_abs_err",
            "thrust_min",
            "thrust_max",
            "thrust_total",
            "srp_error_level",
        ),
    ),
)


def can_control_artifact(artifact: Artifact) -> bool:
    """该产物能否作为轨道保持的输入。

    库中记录含星历段走谱系直连（input_record_id）；无记录的产物回退
    内存星历（extra["ephemeris"]）。两者都不满足（如提升的族成员只有
    CR3BP 段）则无输入，按钮置灰。
    """
    if artifact.artifact_type not in ("orbit", "ephemeris"):
        return False
    return bool(
        (artifact.record_id and artifact.extra.get("has_ephemeris"))
        or artifact.extra.get("ephemeris")
    )


class ControlOrbitDialog(QDialog):
    """轨道保持模态对话框：参数调整、运行/停止、日志与结果摘要。

    Signals:
        control_finished(object): 成功（ControlResultData），主窗口重查清单
            并选中新记录。
        control_failed(str): 失败（含错误码前缀），主窗口记一行日志。
    """

    control_finished = pyqtSignal(object)
    control_failed = pyqtSignal(str)

    def __init__(
        self,
        source: Artifact,
        kernel_dir: str | None,
        catalog_dir: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("轨道保持")
        self._source = source
        self._kernel_dir = kernel_dir
        self._catalog_dir = catalog_dir
        self._worker: ControlOrbitWorker | None = None
        self._stop_requested = False
        self._pending_close = False
        self._param_widgets: dict[str, QWidget] = {}
        self._param_rows: dict[str, tuple[QLabel, QWidget, QComboBox | None]] = {}
        self._group_headers: dict[str, tuple[QLabel, QFrame]] = {}
        self._group_fields: dict[str, list[str]] = {}

        layout = QVBoxLayout(self)
        source_label = QLabel(f"<b>源轨道</b>: {source.label}")
        layout.addWidget(source_label)

        self._param_scroll = QScrollArea()
        self._param_scroll.setWidgetResizable(True)
        self._param_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._param_scroll.setMinimumHeight(320)
        layout.addWidget(self._param_scroll, 2)
        self._build_params()

        self._log = LogPanel()
        self._log.setMaximumHeight(140)
        layout.addWidget(self._log, 1)

        self._run_btn = QPushButton("运行")
        self._stop_btn = QPushButton("停止")
        reset_btn = QPushButton("重置")
        self._run_btn.clicked.connect(self._on_run)
        self._stop_btn.clicked.connect(self._on_stop_run)
        reset_btn.clicked.connect(self._on_reset_params)
        btn_row = QHBoxLayout()
        btn_row.addWidget(reset_btn, 1)
        btn_row.addWidget(self._run_btn, 2)
        btn_row.addWidget(self._stop_btn, 1)
        layout.addLayout(btn_row)
        self._stop_btn.setEnabled(False)

    # -- 参数面板 -----------------------------------------------------------

    def _build_params(self) -> None:
        """构建参数面板（分组展示，逻辑同主窗口工具面板，无分支字段）。"""
        spec = TOOL_REGISTRY["control_orbit"]
        model = spec.request_model
        if model is None:
            return
        self._param_widgets = {}
        self._param_rows = {}
        self._group_headers = {}
        self._group_fields = {}
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setColumnStretch(0, 1)
        self._param_scroll.setWidget(container)

        self._param_widgets = build_params_from_model(model)
        # input_ephemeris / input_record_id 由源 Artifact 注入（后者 issue
        # #375 谱系直连），不在 UI 暴露；mu 同样由源注入（source_mu），面板
        # 编辑无效（ControlOrbitRequest 的 mu 仅为响应透传字段，算法层不
        # 消费）。上游默认控制时长面向多年星历，覆盖不了 GUI 默认设计的
        # 短弧，故在 GUI 层覆盖为短弧默认值。
        for hidden in ("input_ephemeris", "input_record_id", "mu"):
            self._param_widgets.pop(hidden, None)
        for name, default in _CONTROL_ORBIT_GUI_DEFAULTS.items():
            widget = self._param_widgets.get(name)
            if isinstance(widget, QDoubleSpinBox):
                widget.setValue(default)
        self._apply_special_mode()

        grouped = [f for _, fields in _CONTROL_PARAM_GROUPS for f in fields]
        ungrouped = [n for n in self._param_widgets if n not in grouped]
        all_groups: list[tuple[str, tuple[str, ...]]] = list(_CONTROL_PARAM_GROUPS)
        if ungrouped:
            all_groups.append(("其他", tuple(ungrouped)))

        row = 0
        for title, fields in all_groups:
            present = [n for n in fields if n in self._param_widgets]
            if not present:
                continue
            row = self._add_group_header(layout, title, row)
            self._group_fields[title] = present
            for name in present:
                widget = self._param_widgets[name]
                options = get_field_units(name)
                label_text = (
                    self._field_label_with_unit(name, options[0].label)
                    if options
                    else _CONTROL_FIELD_LABELS.get(name, name)
                )
                label_widget = QLabel(label_text)
                layout.addWidget(label_widget, row, 0)
                layout.addWidget(widget, row, 1)
                unit_combo: QComboBox | None = None
                if options:
                    combo = QComboBox()
                    for opt in options:
                        combo.addItem(opt.label)
                    combo.setCurrentIndex(0)
                    combo.currentIndexChanged.connect(
                        lambda _idx, n=name: self._on_unit_combo_changed(n)
                    )
                    layout.addWidget(combo, row, 2)
                    unit_combo = combo
                self._param_rows[name] = (label_widget, widget, unit_combo)
                row += 1

        for sb in container.findChildren(QAbstractSpinBox):
            sb.setMaximumWidth(_PARAM_SPINBOX_MAX_WIDTH)
        layout.setRowStretch(row, 1)

    def _add_group_header(self, layout: QGridLayout, title: str, row: int) -> int:
        header = QLabel(title)
        header.setStyleSheet("font-weight: bold; margin-top: 6px;")
        layout.addWidget(header, row, 0, 1, 3)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep, row + 1, 0, 1, 3)
        self._group_headers[title] = (header, sep)
        return row + 2

    def _base_field_label(self, name: str) -> str:
        options = get_field_units(name)
        if not options:
            return _CONTROL_FIELD_LABELS.get(name, name)
        suffix = f" ({options[0].label})"
        label = _CONTROL_FIELD_LABELS.get(name, name)
        return label[: -len(suffix)] if label.endswith(suffix) else label

    def _field_label_with_unit(self, name: str, unit: str) -> str:
        return f"{self._base_field_label(name)} ({unit})"

    def _on_unit_combo_changed(self, field_name: str) -> None:
        """单位下拉切换：换算控件显示值 + 更新 label 后缀（同主窗口）。"""
        row = self._param_rows.get(field_name)
        if row is None:
            return
        label, widget, unit_combo = row
        if unit_combo is None:
            return
        set_spinbox_unit(widget, field_name, unit_combo.currentText())
        label.setText(self._field_label_with_unit(field_name, unit_combo.currentText()))

    def _apply_special_mode(self) -> None:
        """按源轨道类型锁定特征点模式，Halo/NRHO 使用 xdot=zdot=0。"""
        widget = self._param_widgets.get("special_mode")
        if not isinstance(widget, QComboBox):
            return
        orbit_type = str(
            self._source.orbit_type or self._source.extra.get("orbit_type", "")
        ).upper()
        mode = 2 if orbit_type in {"HALO", "NRHO"} else 1
        widget.setEnabled(False)
        index = widget.findData(mode)
        if index >= 0:
            widget.setCurrentIndex(index)

    def _on_reset_params(self) -> None:
        """重置参数：重建面板（恢复模型默认值 + GUI 短弧默认）。"""
        if self._worker is not None:
            return
        self._build_params()

    # -- 运行 ---------------------------------------------------------------

    def is_busy(self) -> bool:
        """仿真进行中（含停止等待），主窗口据此做任务互斥。"""
        worker = self._worker
        return worker is not None and (worker.isRunning() or self._stop_requested)

    def _set_run_controls(self, *, running: bool, stopping: bool = False) -> None:
        if running and not stopping:
            self._stop_requested = False
        self._run_btn.setEnabled(not running)
        self._run_btn.setText("停止中..." if stopping else "运行中..." if running else "运行")
        self._stop_btn.setEnabled(running and not stopping)

    def _on_run(self) -> None:
        if self._worker is not None:
            return
        source = self._source
        ephemeris_data = source.extra.get("ephemeris")

        spec = TOOL_REGISTRY["control_orbit"]
        model = spec.request_model
        if model is None:
            return
        params = collect_params(self._param_widgets, model)
        params.pop("input_ephemeris", None)  # 防御：理论上已隐藏
        params.pop("input_record_id", None)
        # Issue #375: 库中记录直连站保输入（Facade 取星历段并写谱系
        # source_record_id，design→control 链式不经文件倒手）；无记录的产物
        # 回退 input_ephemeris（内存星历重建 EphemerisTable）。
        if source.record_id and source.extra.get("has_ephemeris"):
            params["input_record_id"] = source.record_id
        elif not ephemeris_data:
            self._log.append_log("所选轨道没有星历数据，需重新设计")
            return

        # 校验仿真时长不超出源星历覆盖：控制律的目标点/反馈弧都取自标称星历，
        # 超出覆盖时控制律无解（默认 30 天/次 × 119 次 + 28 天反馈 ≈ 3598 天，
        # 而 GUI 设计默认星历仅 30 天 → 蒙特卡洛样本必然全部失败、Δv=0）。
        times_et = (ephemeris_data or {}).get("times_et")
        if times_et is not None and len(times_et) > 1:
            span_days = float(times_et[-1] - times_et[0]) / 86400.0
            interval = float(params.get("control_interval", 30.0))
            feedback = float(params.get("feedback_arc", 28.0))
            n_ctrl = int(params.get("num_controls", 120))
            sim_days = (n_ctrl - 2) * interval + feedback
            if sim_days > span_days:
                self._log.append_log(
                    f"参数错误: 仿真时长 {sim_days:.1f} 天（{n_ctrl - 2} 次机动 × "
                    f"{interval} 天/次 + 反馈弧 {feedback} 天）超出源星历覆盖 "
                    f"{span_days:.1f} 天，轨道保持必然全部失败。"
                    f"请减小控制间隔/次数，或设计更长时长的标称轨道。"
                )
                return

        self._log.clear()
        self._log.append_log(f"轨道保持: 源 {source.label}")
        self._set_run_controls(running=True)

        self._worker = ControlOrbitWorker(
            ephemeris_data=ephemeris_data,
            params=params,
            source_mu=source.extra.get("mu"),
            kernel_dir=self._kernel_dir,
            catalog_dir=self._catalog_dir,
            parent=self,
        )
        self._worker.log.connect(self._on_worker_log)
        self._worker.finished.connect(self._on_control_finished)
        self._worker.error.connect(self._on_control_error)
        self._worker.cancelled.connect(self._on_worker_cancelled)
        self._worker.start()

    def _on_stop_run(self) -> None:
        """请求停止；同步算法调用返回前不会强制终止线程。"""
        worker = self._worker
        if worker is None or not self._stop_btn.isEnabled():
            return
        worker.requestInterruption()
        self._stop_requested = True
        self._set_run_controls(running=True, stopping=True)
        self._log.append_log("已请求停止，等待当前数值调用返回...")

    def _consume_stop_request(self) -> bool:
        """在完成或报错信号处理前消费停止请求，阻止结果副作用。"""
        if not self._stop_requested:
            return False
        self._on_worker_cancelled()
        return True

    # -- 结果 ----------------------------------------------------------------

    def _on_worker_log(self, msg: str) -> None:
        self._log.append_log(msg)

    def _on_control_finished(self, result: ControlResultData) -> None:
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)
        self._worker = None

        total_dv = float(np.sum(result.maneuvers_delta_v_mps))
        self._log.append_log(
            f"轨道保持完成: 总Δv={total_dv:.2f} m/s, 失败 {result.num_failed} 样本"
        )
        if result.record_id is None:
            self._log.append_log("站保全样本失败，未产生库记录")
        self.control_finished.emit(result)

    def _on_control_error(self, error_msg: str) -> None:
        if self._consume_stop_request():
            return
        self._set_run_controls(running=False)
        self._worker = None
        self._log.append_log(f"错误:\n{error_msg}")
        self.control_failed.emit(error_msg)

    def _on_worker_cancelled(self) -> None:
        """当前数值调用返回后丢弃已取消任务的结果。"""
        self._stop_requested = False
        self._set_run_controls(running=False)
        self._worker = None
        self._log.append_log("运行已停止，结果未保存")
        if self._pending_close:
            self._pending_close = False
            self.accept()

    # -- 关闭 ----------------------------------------------------------------

    def closeEvent(self, a0) -> None:  # noqa: N802, ANN001 - Qt 覆盖方法签名（同 MainWindow）
        """运行中关闭视为取消任务：请求停止，待取消信号到达后再关。"""
        if self.is_busy():
            if not self._stop_requested:
                self._on_stop_run()
            self._pending_close = True
            a0.ignore()
            return
        super().closeEvent(a0)
