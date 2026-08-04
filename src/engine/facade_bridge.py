"""FacadeBridge -- e2m2e 算法层直调的薄封装。

直接调用 algorithm 层而非 Facade 门面，因为 Facade 返回的 DesignOrbitResponse
剥离了轨道数据（只返回标量汇总），而 GUI 需要完整的 Orbit 对象用于可视化。
详见 docs/adr/0011-algorithm-layer-direct-call.md。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from pydantic import BaseModel


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass
class OrbitDesignResultData:
    """跨线程传递的轨道设计结果 DTO。

    纯数据类，不含 e2m2e 对象引用。
    numpy 数组通过引用传递，零拷贝。
    """

    orbit_type: str
    epoch_utc: str
    duration_day: float
    initial_state: Any  # np.ndarray (6,)
    cr3bp_jacobi: float
    states: Any  # np.ndarray (n, 6) -- 从 cr3bp_orbit.states 提取
    times: Any  # np.ndarray (n,)   -- 从 cr3bp_orbit.times 提取
    correction_converged: bool
    correction_iterations: int


# ---------------------------------------------------------------------------
# ToolSpec + TOOL_REGISTRY
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """工具描述：绑定 Pydantic Request 模型、FacadeBridge 方法名、UI 标签。"""

    request_model: type[BaseModel] | None  # Pydantic 模型（None = 无正式模型）
    facade_method: str  # FacadeBridge 方法名
    label: str  # UI 显示名
    enabled: bool  # 是否启用


def _build_tool_registry() -> dict[str, ToolSpec]:
    """延迟构建 TOOL_REGISTRY，避免在 e2m2e 未安装时 import 失败。"""
    try:
        from e2m2e.api.models import ControlOrbitRequest, DesignOrbitRequest
    except ImportError:
        DesignOrbitRequest = None  # type: ignore[misc,assignment]
        ControlOrbitRequest = None  # type: ignore[misc,assignment]

    return {
        "design_orbit": ToolSpec(
            request_model=DesignOrbitRequest,
            facade_method="design_orbit",
            label="轨道设计",
            enabled=True,
        ),
        "control_orbit": ToolSpec(
            request_model=ControlOrbitRequest,
            facade_method="control_orbit",
            label="轨道保持",
            enabled=False,
        ),
        "orbit_family_generation": ToolSpec(
            request_model=None,
            facade_method="generate_family",
            label="轨道族生成",
            enabled=False,
        ),
        "orbit_stability": ToolSpec(
            request_model=None,
            facade_method="analyze_stability",
            label="稳定性分析",
            enabled=False,
        ),
    }


TOOL_REGISTRY: dict[str, ToolSpec] = _build_tool_registry()


# ---------------------------------------------------------------------------
# FacadeBridge
# ---------------------------------------------------------------------------


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

    def design_orbit(self, **kwargs: Any) -> OrbitDesignResultData:
        """调用 e2m2e.algorithm.design.design_orbit，返回跨线程 DTO。

        所有关键字参数原样转发给 e2m2e（kernel_dir 由本类注入）。
        异常经 translate_exception() 翻译为 OrbitError 后抛出。

        Returns:
            OrbitDesignResultData -- 可安全跨线程传递的纯数据对象。

        Raises:
            OrbitError: 经翻译的结构化错误。
        """
        from e2m2e.algorithm.design import design_orbit

        from src.engine.exceptions import translate_exception

        kwargs.setdefault("kernel_dir", self._kernel_dir)
        try:
            result = design_orbit(**kwargs)
        except Exception as e:
            raise translate_exception(e) from e

        cr3bp_orbit = result.cr3bp_orbit
        return OrbitDesignResultData(
            orbit_type=result.orbit_type,
            epoch_utc=result.epoch_utc,
            duration_day=result.duration_day,
            initial_state=result.initial_state,
            cr3bp_jacobi=result.cr3bp_jacobi,
            states=np.asarray(cr3bp_orbit.states),
            times=np.asarray(cr3bp_orbit.times),
            correction_converged=result.correction.converged,
            correction_iterations=result.correction.iterations,
        )
