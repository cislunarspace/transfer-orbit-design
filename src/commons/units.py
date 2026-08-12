"""参数单位换算 -- DU/TU 与标准单位（km/年/秒）之间的纯换算。

常量来源对齐 ``e2m2e.data.templates.seed``：``CHAR_LENGTH_KM=384400`` km、
``CHAR_PERIOD_SEC=27.32*86400`` s；``TU = CHAR_PERIOD_SEC / (2π)``。

注意：e2m2e 5.6.6 常数单一来源化（上游 #377）后，``CR3BP_System`` 默认尺度
与 ``set_characteristic_scales(CHAR_LENGTH_KM, CHAR_PERIOD_SEC)`` 已对齐为同一套
值，历史版本两者不一致（差约 0.86 倍）的问题不复存在。GUI 仍以
``e2m2e.data.templates`` 为准，与算法链路保持一致。
"""

from __future__ import annotations

import math

from e2m2e.data.templates import CHAR_LENGTH_KM, CHAR_PERIOD_SEC

DU_KM: float = CHAR_LENGTH_KM  # 384400.0 km
TU_SECONDS: float = CHAR_PERIOD_SEC / (2.0 * math.pi)  # ≈ 375676.97 s
DAYS_PER_YEAR: float = 365.25  # e2m2e design_orbit.DAYS_PER_YEAR
SECONDS_PER_YEAR: float = DAYS_PER_YEAR * 86400.0


def km_to_du(km: float) -> float:
    return km / DU_KM


def du_to_km(du: float) -> float:
    return du * DU_KM


def years_to_tu(years: float) -> float:
    return years * SECONDS_PER_YEAR / TU_SECONDS


def tu_to_years(tu: float) -> float:
    return tu * TU_SECONDS / SECONDS_PER_YEAR


def seconds_to_tu(seconds: float) -> float:
    return seconds / TU_SECONDS


def tu_to_seconds(tu: float) -> float:
    return tu * TU_SECONDS
