"""FacadeBridge -- e2m2e 算法层直调的薄封装。

直接调用 algorithm 层而非 Facade 门面，因为 Facade 返回的 DesignOrbitResponse
剥离了轨道数据（只返回标量汇总），而 GUI 需要完整的 Orbit 对象用于可视化。
详见 docs/adr/0011-algorithm-layer-direct-call.md。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OrbitDesignResultData:
    """跨线程传递的轨道设计结果 DTO。

    纯数据类，不持有 e2m2e 对象引用以外的资源。
    numpy 数组通过引用传递，零拷贝。
    """

    orbit_type: str
    epoch_utc: str
    duration_day: float
    initial_state: Any  # np.ndarray
    cr3bp_jacobi: float
    cr3bp_orbit: Any  # e2m2e Orbit 对象引用
    correction_converged: bool
    correction_iterations: int


class FacadeBridge:
    """e2m2e 算法层的薄封装。

    职责：
    - 接收 GUI 参数，调用 e2m2e 算法层
    - 将算法层返回的富对象转换为跨线程 DTO
    - 异常翻译（e2m2e 异常 -> 结构化错误消息）

    不负责：
    - 线程管理（由 QThread Worker 处理）
    - 结果持久化（由 persistence 模块处理）
    """

    def __init__(self, kernel_dir: str | None = None) -> None:
        self._kernel_dir = kernel_dir

    def design_orbit(
        self,
        orbit_type: str,
        amplitude: float = 40000.0,
        duration: float = 1.0,
        output_step: float = 3600.0,
    ) -> OrbitDesignResultData:
        """调用 e2m2e.algorithm.design.design_orbit，返回跨线程 DTO。

        Args:
            orbit_type:  轨道类型（DRO / Halo / NRHO / Lissajous / L4 / L5）。
            amplitude:   振幅 (km)。
            duration:    持续时间 (年)。
            output_step: 输出步长 (秒)。

        Returns:
            OrbitDesignResultData — 可安全跨线程传递的纯数据对象。

        Raises:
            Exception:  e2m2e 算法层可能抛出的任何异常（原样传播）。
        """
        from e2m2e.algorithm.design import design_orbit

        result = design_orbit(
            orbit_type,
            amplitude=amplitude,
            duration=duration,
            output_step=output_step,
            kernel_dir=self._kernel_dir,
        )
        return OrbitDesignResultData(
            orbit_type=result.orbit_type,
            epoch_utc=result.epoch_utc,
            duration_day=result.duration_day,
            initial_state=result.initial_state,
            cr3bp_jacobi=result.cr3bp_jacobi,
            cr3bp_orbit=result.cr3bp_orbit,
            correction_converged=result.correction.converged,
            correction_iterations=result.correction.iterations,
        )
