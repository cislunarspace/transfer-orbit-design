"""QThread 工作线程 -- 将 e2m2e 算法调用放入后台线程。

每个 Facade 方法对应一个 Worker 类。Worker 使用 FacadeBridge 薄封装层，
不直接 import e2m2e（延迟 import 留在 FacadeBridge 内部）。
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from src.engine.exceptions import OrbitError
from src.engine.facade_bridge import FacadeBridge


class OrbitDesignWorker(QThread):
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
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._orbit_type = orbit_type
        self._params = params
        self._kernel_dir = kernel_dir

    def run(self) -> None:
        try:
            self.log.emit(f"开始设计 {self._orbit_type} 轨道...")
            self.log.emit(f"参数: {self._params}")

            bridge = FacadeBridge(kernel_dir=self._kernel_dir)
            data = bridge.design_orbit(
                orbit_type=self._orbit_type,
                **self._params,
            )

            self.log.emit(
                f"设计完成: {data.orbit_type}, "
                f"C_J={data.cr3bp_jacobi:.6f}, "
                f"修正{'收敛' if data.correction_converged else '未收敛'}"
                f"({data.correction_iterations} 次迭代)"
            )
            self.finished.emit(data)

        except OrbitError as e:
            self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            # Defensive fallback: FacadeBridge translates all exceptions to OrbitError,
            # so this branch should theoretically never execute.
            self.error.emit(f"[UNKNOWN_ERROR] {e}")


class ControlOrbitWorker(QThread):
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
        ephemeris_data: dict,
        params: dict[str, Any],
        source_mu: float | None,
        kernel_dir: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ephemeris_data = ephemeris_data
        self._params = params
        self._source_mu = source_mu
        self._kernel_dir = kernel_dir

    def run(self) -> None:
        try:
            self.log.emit("开始轨道保持仿真...")
            self.log.emit(f"参数: {self._params}")
            bridge = FacadeBridge(kernel_dir=self._kernel_dir)
            data = bridge.control_orbit(
                ephemeris_data=self._ephemeris_data,
                source_mu=self._source_mu,
                **self._params,
            )
            total_dv = float(np.sum(data.maneuvers_delta_v_mps))
            self.log.emit(
                f"保持完成: 总Δv={total_dv:.2f} m/s, "
                f"失败 {data.num_failed} 样本, "
                f"{len(data.maneuvers_mjd_tdb)} 次机动"
            )
            self.finished.emit(data)
        except OrbitError as e:
            self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            self.error.emit(f"[UNKNOWN_ERROR] {e}")
