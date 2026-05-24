"""correct_dro_to_ephemeris 星历转换脚本。

本模块将 CR3BP 轨道状态映射到真实星历模型，依赖 SPICE kernels（de440.bsp、naif0012.tls）和 UTC 参考历元。输入为 DRO/Halo 单轨道或轨道族 JSON，输出为含修正状态、残差和元数据的星历转换结果。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.ephemeris.dro.correct_dro_to_ephemeris --help
"""


from __future__ import annotations

from tod.generates.ephemeris import _conversion


def main(argv: list[str] | None = None):
    """执行脚本主流程。
    
    Args:
        argv: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    return _conversion.main_single("dro", argv)


if __name__ == "__main__":
    main()
