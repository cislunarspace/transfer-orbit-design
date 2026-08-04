"""OrbitError + e2m2e 异常翻译层。

将 e2m2e 库异常翻译为结构化 OrbitError，Worker 层发射错误码时使用。
"""

from __future__ import annotations


class OrbitError(Exception):
    """结构化错误，包含错误码和用户友好消息。

    Attributes:
        code: 错误码（如 ``"CORRECTION_DIVERGED"``）。
        message: 可读错误信息。
        cause: 原始异常（如有）。
    """

    def __init__(
        self,
        code: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.cause = cause


def translate_exception(e: Exception) -> OrbitError:
    """将 e2m2e 异常翻译为 OrbitError。

    映射规则（按优先级）：
    - DesignNotConvergedError  -> CORRECTION_DIVERGED
    - UnsupportedCorrectorMethodError -> INVALID_CORRECTION_METHOD
    - FileNotFoundError         -> KERNEL_NOT_FOUND
    - NotImplementedError        -> NOT_IMPLEMENTED
    - ValueError                -> INVALID_PARAMS
    - 其他                       -> UNKNOWN_ERROR
    """
    try:
        from e2m2e.algorithm.design.design_orbit import DesignNotConvergedError

        if isinstance(e, DesignNotConvergedError):
            return OrbitError(
                code="CORRECTION_DIVERGED",
                message=f"轨道修正未收敛: {e}",
                cause=e,
            )
    except ImportError:
        pass

    try:
        from e2m2e.algorithm.ephemeris_correction.types import (
            UnsupportedCorrectorMethodError,
        )

        if isinstance(e, UnsupportedCorrectorMethodError):
            return OrbitError(
                code="INVALID_CORRECTION_METHOD",
                message=f"不支持的修正方法: {e}",
                cause=e,
            )
    except ImportError:
        pass

    if isinstance(e, FileNotFoundError):
        return OrbitError(
            code="KERNEL_NOT_FOUND",
            message=f"SPICE 内核文件未找到: {e}",
            cause=e,
        )

    if isinstance(e, NotImplementedError):
        return OrbitError(
            code="NOT_IMPLEMENTED",
            message=f"功能未实现: {e}",
            cause=e,
        )

    if isinstance(e, ValueError):
        return OrbitError(
            code="INVALID_PARAMS",
            message=f"参数无效: {e}",
            cause=e,
        )

    return OrbitError(
        code="UNKNOWN_ERROR",
        message=f"未知错误: {e}",
        cause=e,
    )
