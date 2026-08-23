"""脚本共享的常量、路径与工具。

硬编码常量（M_SUN / OMEGA_SUN / RHO / FAMILY_FILENAME）在模块导入时即可用，不依赖 e2m2e。
CR3BP 派生常量（MU / DU / TU / VU / T_MOON）通过 __getattr__ 惰性计算，首次访问时才
导入 e2m2e 并调用 CR3BP_System.from_known_system("earth_moon")。
"""

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 为类型检查器声明 CR3BP 常量类型，实际值在 __getattr__ 中惰性赋值。
    MU: float
    DU: float
    TU: float
    VU: float
    T_MOON: float

# ============================================================
# 硬编码常量 - 始终可用，不依赖 e2m2e
# ============================================================

# 太阳摄动（BR4BP）
M_SUN: float = 3.28900541e5  # 太阳无量纲质量
OMEGA_SUN: float = 9.25195985e-1  # 太阳无量纲角速度
RHO: float = 3.88811143e2  # 太阳到地月质心无量纲距离

# 文件命名
FAMILY_FILENAME: str = "family.json"

# ============================================================
# CR3BP 派生常量 - 惰性计算（首次访问时导入 e2m2e）
# ============================================================

_cr3bp_initialized: bool = False


def _init_cr3bp() -> None:
    """惰性初始化地月 CR3BP 系统常量。

    仅在首次访问 MU / DU / TU / VU / T_MOON 时调用一次，
    将 CR3BP_System 导入推迟到真正需要时。
    """
    global _cr3bp_initialized, MU, DU, TU, VU, T_MOON
    if _cr3bp_initialized:
        return
    from e2m2e.algorithm.dynamics import CR3BP_System
    from e2m2e.data.templates.seed import EARTH_MOON_MU

    _em = CR3BP_System(mu=EARTH_MOON_MU, primary="Earth", secondary="Moon")._with_default_scales()
    MU = _em.mu  # 0.012150585350562453（e2m2e DE421 基准）
    # TU/VU 单位为 TOD 约定：TU 是天、VU 是 m/s（消费方 * TU 得天数、VU/1000 得 km/s）。
    # 旧注释曾标为 s / km/s，系单位误标。
    DU = _em.DU  # 384400.0 km（e2m2e 5.6.6 起；此前 384405.0）
    TU = _em.TU  # 4.34248 天（e2m2e 5.6.6 起；此前 4.33030 天）
    VU = _em.VU  # 1024.55 m/s（e2m2e 5.6.6 起；此前 1027.30 m/s）
    T_MOON = 2.0 * math.pi  # 月球轨道周期（无量纲）
    _cr3bp_initialized = True


def __getattr__(name: str) -> float:
    """模块级惰性属性访问，仅在 name 不在 globals() 中时触发。"""
    if name in ("MU", "DU", "TU", "VU", "T_MOON"):
        _init_cr3bp()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
