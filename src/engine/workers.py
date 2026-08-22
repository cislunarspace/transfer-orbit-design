"""QThread 工作线程 -- 将 e2m2e 算法调用放入后台线程。

每个 Facade 方法对应一个 Worker 类。Worker 使用 FacadeBridge 薄封装层，
不直接 import e2m2e（延迟 import 留在 FacadeBridge 内部）。
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from src.commons.units import DU_KM
from src.engine.exceptions import OrbitError
from src.engine.facade_bridge import FacadeBridge


class _CancellableWorker(QThread):
    """为同步算法调用提供安全的协作式取消边界。"""

    cancelled = pyqtSignal()

    def _emit_cancelled_if_requested(self) -> bool:
        if not self.isInterruptionRequested():
            return False
        self.cancelled.emit()
        return True


class OrbitDesignWorker(_CancellableWorker):
    """在后台线程中执行 e2m2e 轨道设计。

    Signals:
        log(str):                     进度/信息日志。
        finished(OrbitDesignResultData):  成功结果。
        error(str):                   错误消息（含错误码前缀）。
    """

    log = pyqtSignal(str)
    finished = pyqtSignal(object)  # OrbitDesignResultData
    error = pyqtSignal(str)

    def __init__(
        self,
        orbit_type: str,
        params: dict[str, Any],
        kernel_dir: str | None = None,
        catalog_dir: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._orbit_type = orbit_type
        self._params = params
        self._kernel_dir = kernel_dir
        self._catalog_dir = catalog_dir

    def run(self) -> None:
        try:
            self.log.emit(f"开始设计 {self._orbit_type} 轨道...")
            self.log.emit(f"参数: {self._params}")

            bridge = FacadeBridge(kernel_dir=self._kernel_dir, catalog_dir=self._catalog_dir)
            data = bridge.design_orbit(
                orbit_type=self._orbit_type,
                **self._params,
            )
            if self._emit_cancelled_if_requested():
                return

            self.log.emit(
                f"设计完成: {data.orbit_type}, "
                f"C_J={data.cr3bp_jacobi:.6f}, "
                f"修正{'收敛' if data.correction_converged else '未收敛'}"
                f"({data.correction_iterations} 次迭代)"
            )
            self.finished.emit(data)

        except OrbitError as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            if not self._emit_cancelled_if_requested():
                # Defensive fallback: FacadeBridge translates all exceptions to OrbitError,
                # so this branch should theoretically never execute.
                self.error.emit(f"[UNKNOWN_ERROR] {e}")


class ControlOrbitWorker(_CancellableWorker):
    """后台执行 e2m2e 轨道保持（蒙特卡洛仿真）。

    Signals:
        log(str):                       进度/信息日志。
        finished(ControlResultData):    成功结果。
        error(str):                     错误消息（含错误码前缀）。
    """

    log = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        ephemeris_data: dict | None,
        params: dict[str, Any],
        source_mu: float | None,
        kernel_dir: str | None = None,
        catalog_dir: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ephemeris_data = ephemeris_data
        self._params = params
        self._source_mu = source_mu
        self._kernel_dir = kernel_dir
        self._catalog_dir = catalog_dir

    def run(self) -> None:
        try:
            self.log.emit("开始轨道保持仿真...")
            self.log.emit(f"参数: {self._params}")
            bridge = FacadeBridge(kernel_dir=self._kernel_dir, catalog_dir=self._catalog_dir)
            data = bridge.control_orbit(
                ephemeris_data=self._ephemeris_data,
                source_mu=self._source_mu,
                **self._params,
            )
            if self._emit_cancelled_if_requested():
                return
            total_dv = float(np.sum(data.maneuvers_delta_v_mps))
            self.log.emit(
                f"保持完成: 总Δv={total_dv:.2f} m/s, "
                f"失败 {data.num_failed} 样本, "
                f"{len(data.maneuvers_mjd_tdb)} 次机动"
            )
            self.finished.emit(data)
        except OrbitError as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[UNKNOWN_ERROR] {e}")


class PropagationWorker(_CancellableWorker):
    """后台执行 e2m2e 轨道预报（高精度力模型外推，需 SPICE 内核）。

    Signals:
        log(str):                         进度/信息日志。
        finished(PropagationResultData):  成功结果。
        error(str):                       错误消息（含错误码前缀）。
    """

    log = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        params: dict[str, Any],
        kernel_dir: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._params = params
        self._kernel_dir = kernel_dir

    def run(self) -> None:
        try:
            self.log.emit("开始轨道预报...")
            self.log.emit(f"参数: {self._params}")
            bridge = FacadeBridge(kernel_dir=self._kernel_dir)
            data = bridge.orbit_propagation(**self._params)
            if self._emit_cancelled_if_requested():
                return
            self.log.emit(
                f"轨道预报完成: {data.n_points} 点，时长 {data.duration_sec / 86400.0:.2f} 天"
            )
            self.finished.emit(data)
        except OrbitError as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[UNKNOWN_ERROR] {e}")


#: 各族成员的标志性几何量（用于完成日志）：
#: family_type -> (member_parameters 键, 显示标签, 是否需 DU→km 换算)。
_FAMILY_MEMBER_METRIC = {
    "halo": ("amplitude_z", "z 振幅", True),
    "nrho": ("perilune_height_km", "近月点高度", False),
    "axial": ("amplitude_z_km", "z 振幅", False),
    "lissajous": ("amplitude_out_km", "面外振幅", False),
    "spo": ("amplitude_km", "振幅", False),
    "lpo": ("amplitude_km", "振幅", False),
    "horseshoe": ("amplitude_km", "振幅", False),
}


def _family_metric_summary(data: Any) -> str:
    """从成员参数提取族标志性几何量的范围摘要（如 "，z 振幅 385–19245 km"）。"""
    metric = _FAMILY_MEMBER_METRIC.get(getattr(data, "family_type", ""))
    if metric is None or not data.member_parameters:
        return ""
    key, label, to_km = metric
    values = [float(p[key]) for p in data.member_parameters if key in p]
    if not values:
        return ""
    scale = DU_KM if to_km else 1.0
    return f"，{label} {min(values) * scale:.0f}–{max(values) * scale:.0f} km"


class FamilyOrbitWorker(_CancellableWorker):
    """后台执行 e2m2e 轨道族生成（七族；CR3BP 纯计算，无需 SPICE）。

    Signals:
        log(str):                     进度/信息日志。
        finished(FamilyResultData):   成功结果。
        error(str):                   错误消息（含错误码前缀）。
    """

    log = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        params: dict[str, Any],
        catalog_dir: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._params = params
        self._catalog_dir = catalog_dir

    def run(self) -> None:
        try:
            self.log.emit(f"开始生成 {self._params.get('orbit_type', 'HALO')} 轨道族...")
            self.log.emit(f"参数: {self._params}")
            bridge = FacadeBridge(catalog_dir=self._catalog_dir)
            data = bridge.generate_family(**self._params)
            if self._emit_cancelled_if_requested():
                return
            message = (
                f"轨道族生成完成: {data.n_orbits} 条 {data.orbit_type} 轨道"
                f"（L{data.libration_point}{_family_metric_summary(data)}）"
            )
            if data.status_message:
                # 软失败（部分族）：上游状态消息告知为何未满额
                message += f"；{data.status_message}"
            self.log.emit(message)
            self.finished.emit(data)
        except OrbitError as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[UNKNOWN_ERROR] {e}")


class TransferDesignWorker(_CancellableWorker):
    """后台执行 e2m2e 转移轨道设计。

    Signals:
        log(str):                          进度/信息日志。
        finished(TransferDesignResultData): 成功结果（含未收敛的 INFEASIBLE，
                                          由调用方按 converged 字段区分展示）。
        error(str):                        错误消息（含错误码前缀）。
    """

    log = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        transfer_type: str,
        params: dict[str, Any],
        target_states: Any | None = None,
        kernel_dir: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._transfer_type = transfer_type
        self._params = params
        self._target_states = target_states
        self._kernel_dir = kernel_dir

    def run(self) -> None:
        try:
            self.log.emit(f"开始 {self._transfer_type} 转移轨道设计...")
            self.log.emit(f"参数: {self._params}")
            bridge = FacadeBridge(kernel_dir=self._kernel_dir)
            data = bridge.transfer_design(
                target_states=self._target_states, **self._params
            )
            if self._emit_cancelled_if_requested():
                return
            if data.converged:
                self.log.emit(
                    f"转移设计完成: 总Δv={data.delta_v:.4f} km/s（{data.message}）"
                )
            else:
                self.log.emit(f"转移设计未收敛: {data.message}")
            self.finished.emit(data)
        except OrbitError as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[UNKNOWN_ERROR] {e}")


class StabilityWorker(_CancellableWorker):
    """后台执行 e2m2e 轨道稳定性分析（CR3BP 纯计算，无需 SPICE）。

    Signals:
        log(str):                       进度/信息日志。
        finished(StabilityResultData):  成功结果。
        error(str):                     错误消息（含错误码前缀）。
    """

    log = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        states: Any,
        times: Any,
        mu: float | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._states = states
        self._times = times
        self._mu = mu

    def run(self) -> None:
        try:
            self.log.emit("开始稳定性分析...")
            bridge = FacadeBridge()
            data = bridge.analyze_stability(self._states, self._times, self._mu)
            if self._emit_cancelled_if_requested():
                return
            self.log.emit("稳定性分析完成")
            self.finished.emit(data)
        except OrbitError as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            if not self._emit_cancelled_if_requested():
                self.error.emit(f"[UNKNOWN_ERROR] {e}")
