"""轨道索引亚采样工具。"""

from __future__ import annotations

import numpy as np


def subsample_indices(n: int, max_points: int | None, seed: int) -> np.ndarray:
    """对轨道索引进行亚采样（当轨道数超过最大点数时）。

    Args:
        n: 轨道总数。
        max_points: 最大采样点数，None 表示不采样。
        seed: 随机种子。

    Returns:
        排序后的采样索引数组。
    """
    if max_points is None or n <= max_points:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n, size=max_points, replace=False))
