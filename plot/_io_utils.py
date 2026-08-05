"""转移管线搜索结果的共享 IO helper。

提供 ``load_search_results``，供各 plot 脚本统一加载 grid_search 输出的 JSON 结果。
"""

from __future__ import annotations

import json
from pathlib import Path


def load_search_results(path: Path) -> list[dict]:
    """加载 grid_search 输出的搜索结果 JSON。

    支持两种格式：
    - list[dict]（直接列表）
    - dict 含 "results" key（自动提取 results 字段）
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "results" in data:
        return list(data["results"])
    if not isinstance(data, list):
        raise TypeError(f"期望 list 或含 'results' key 的 dict, 实际 {type(data)}")
    return data
