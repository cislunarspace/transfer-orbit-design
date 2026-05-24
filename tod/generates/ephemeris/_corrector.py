# pyright: reportArgumentType=false, reportAssignmentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""_corrector 星历转换脚本。

本模块将 CR3BP 轨道状态映射到真实星历模型，依赖 SPICE kernels（de440.bsp、naif0012.tls）和 UTC 参考历元。输入为 DRO/Halo 单轨道或轨道族 JSON，输出为含修正状态、残差和元数据的星历转换结果。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.ephemeris._corrector --help
"""


from __future__ import annotations

try:
    from e2m2e.algorithms.ephemeris_correction import (
        EphemerisCorrectionResult,
        correct_ephemeris_patch_points as _e2m2e_correct_ephemeris_patch_points,
    )
except ModuleNotFoundError:
    from typing import Any

    EphemerisCorrectionResult = Any

    def _e2m2e_correct_ephemeris_patch_points(*args, **kwargs):
        """报告当前 e2m2e 版本缺少星历修正分发函数。"""
        raise RuntimeError(
            "当前 e2m2e 安装缺少 e2m2e.algorithms.ephemeris_correction；"
            "请更新 e2m2e 或在测试中 patch _e2m2e_correct_ephemeris_patch_points。"
        )


def correct_ephemeris_patch_points(*args, **kwargs) -> EphemerisCorrectionResult:
    """执行 correct_ephemeris_patch_points 对应的处理逻辑。
    
    Args:
        args: 调用方传入的参数值。
        kwargs: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    return _e2m2e_correct_ephemeris_patch_points(*args, **kwargs)
