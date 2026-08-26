"""OrbitError + e2m2e 异常翻译层。

将 e2m2e 库异常翻译为结构化 OrbitError（错误码 + 用户友好消息）。

English: OrbitError plus the e2m2e exception translation layer. Translates
e2m2e library exceptions into structured OrbitError (error code +
user-friendly message).
"""

from __future__ import annotations


class OrbitError(Exception):
    """结构化错误，包含错误码和用户友好消息。

    Attributes:
        code: 错误码（如 ``"CORRECTION_DIVERGED"``）。
        message: 可读错误信息。
        cause: 原始异常（如有）。

    Structured error carrying an error code and a user-friendly message.
    Attributes: ``code`` — error code (e.g. ``"CORRECTION_DIVERGED"``);
    ``message`` — human-readable error text; ``cause`` — the original
    exception, if any.
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
    - DesignNotConvergedError  -> CORRECTION_DIVERGED（附上游 FailureCause）
    - PropagationFailure       -> PROPAGATION_FAILED（5.6.6 起取代错误消息
      前缀匹配的类型化传播失败，上游 #349）
    - RustExtensionUnavailableError -> BACKEND_UNAVAILABLE（5.6.6 起禁止
      Rust 缺失静默回退 Python，上游 #378）
    - e2m2e.api OrbitError        -> 透传（Facade 接缝的结构化错误，码与消息
      已是用户可读契约，如族生成的 INVALID_PARAMS/DESIGN_FAILED）
    - FileNotFoundError         -> KERNEL_NOT_FOUND
    - NotImplementedError        -> NOT_IMPLEMENTED
    - ValueError                -> INVALID_PARAMS
    - 其他                       -> UNKNOWN_ERROR

    English: translate an e2m2e exception into OrbitError. Mapping rules
    (by priority): DesignNotConvergedError -> CORRECTION_DIVERGED (with
    the upstream FailureCause attached); PropagationFailure ->
    PROPAGATION_FAILED (since 5.6.6 replaces the typed propagation
    failure matched by message prefix, upstream #349);
    RustExtensionUnavailableError -> BACKEND_UNAVAILABLE (since 5.6.6 the
    silent Python fallback on missing Rust is forbidden, upstream #378);
    e2m2e.api OrbitError -> passed through (the structured error of the
    Facade seam; code and message are already a user-readable contract,
    e.g. INVALID_PARAMS/DESIGN_FAILED for family generation);
    FileNotFoundError -> KERNEL_NOT_FOUND; NotImplementedError ->
    NOT_IMPLEMENTED; ValueError -> INVALID_PARAMS; anything else ->
    UNKNOWN_ERROR.
    """
    try:
        from e2m2e.algorithm.design.design_orbit import DesignNotConvergedError

        if isinstance(e, DesignNotConvergedError):
            # 5.6.6 起异常携带 FailureCause（统一结果契约 #351），附上便于定位
            # Since 5.6.6 exceptions carry a FailureCause (unified result contract #351);
            # attach it for pinpointing.
            cause_name = getattr(getattr(e, "cause", None), "name", None)
            detail = f"（{cause_name}）" if cause_name else ""
            return OrbitError(
                code="CORRECTION_DIVERGED",
                message=f"轨道修正未收敛{detail}: {e}",
                cause=e,
            )
    except ImportError:
        pass

    try:
        from e2m2e.exceptions import PropagationFailure, RustExtensionUnavailableError

        if isinstance(e, PropagationFailure):
            return OrbitError(
                code="PROPAGATION_FAILED",
                message=f"轨道传播失败: {e}",
                cause=e,
            )
        if isinstance(e, RustExtensionUnavailableError):
            return OrbitError(
                code="BACKEND_UNAVAILABLE",
                message=f"e2m2e Rust 计算内核不可用: {e}",
                cause=e,
            )
    except ImportError:
        pass

    try:
        # e2m2e api 边界的结构化错误（Facade 接缝抛出，如族生成的
        # INVALID_PARAMS/DESIGN_FAILED）：错误码与消息已是用户可读契约，透传。
        # Structured errors at the e2m2e api boundary (raised at the Facade seam, e.g. family
        # generation's INVALID_PARAMS/DESIGN_FAILED): code and message are already a user-readable
        # contract; pass them through.
        from e2m2e.api.models import OrbitError as E2M2EOrbitError

        if isinstance(e, E2M2EOrbitError):
            return OrbitError(code=e.code, message=e.message, cause=e)
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
