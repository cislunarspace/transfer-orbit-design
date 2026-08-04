"""Facade / Algorithm API 工作线程 — 原型。

验证点：e2m2e 算法调用在 QThread 中执行不阻塞 GUI，信号正确携带结果或错误。
注意：Facade API 会剥离轨道数据（只返回标量汇总），因此轨道设计用
algorithm 层 design_orbit() 直接调用以获取完整 OrbitDesignResult。
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal


@dataclass
class OrbitDesignResultData:
    """跨线程传递的轨道设计结果（可序列化 + numpy 引用）。"""

    orbit_type: str
    epoch_utc: str
    duration_day: float
    initial_state: Any  # np.ndarray
    cr3bp_jacobi: float
    cr3bp_orbit: Any  # e2m2e Orbit 对象引用
    correction_converged: bool
    correction_iterations: int


class OrbitDesignWorker(QThread):
    """在后台线程中执行 e2m2e 轨道设计。

    Signals:
        log(str):  进度/信息日志。
        finished(OrbitDesignResultData):  成功结果。
        error(str):  错误消息。
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
    ):
        super().__init__(parent)
        self._orbit_type = orbit_type
        self._params = params
        self._kernel_dir = kernel_dir

    def run(self) -> None:
        try:
            self.log.emit(f"开始设计 {self._orbit_type} 轨道...")
            self.log.emit(f"参数: {self._params}")

            from e2m2e.algorithm.design import design_orbit

            result = design_orbit(
                self._orbit_type,
                kernel_dir=self._kernel_dir,
                **self._params,
            )

            data = OrbitDesignResultData(
                orbit_type=result.orbit_type,
                epoch_utc=result.epoch_utc,
                duration_day=result.duration_day,
                initial_state=result.initial_state,
                cr3bp_jacobi=result.cr3bp_jacobi,
                cr3bp_orbit=result.cr3bp_orbit,
                correction_converged=result.correction.converged,
                correction_iterations=result.correction.iterations,
            )

            self.log.emit(
                f"✓ 设计完成: {data.orbit_type}, "
                f"C_J={data.cr3bp_jacobi:.6f}, "
                f"修正{'收敛' if data.correction_converged else '未收敛'}"
                f"({data.correction_iterations} 次迭代)"
            )
            self.finished.emit(data)

        except Exception:
            self.error.emit(traceback.format_exc())
