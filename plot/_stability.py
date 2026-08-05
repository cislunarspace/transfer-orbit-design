"""Jacobi / 稳定性分析。"""

from __future__ import annotations

from e2m2e.algorithm.stability import StabilityAnalysis
from e2m2e.data.types.orbit import OrbitFamily


def compute_stability_indices(family: OrbitFamily) -> list[float]:
    """计算轨道族的 Broucke 稳定性指数。"""
    values: list[float] = []
    for i in range(len(family)):
        orbit = family[i]
        analysis = StabilityAnalysis(orbit=orbit)
        indices = analysis.compute_stability_index()
        values.append(indices.get("broucke") or 0.0)
    return values
