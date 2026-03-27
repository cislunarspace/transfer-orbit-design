"""网格结果与 NLP 输出 JSON 的加载与序列化。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from e2m2e.transfer import NLPOptimizationResult


def load_search_results(path: Path) -> List[Dict[str, Any]]:
    """加载网格 JSON。支持 Python 扩展（NaN / Infinity），与 grid_search 写出格式一致。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def json_safe(x: Any) -> Any:
    """将 numpy 标量/数组及嵌套结构转为可 ``json.dump`` 的 Python 原生类型。"""
    if x is None:
        return None
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, dict):
        return {k: json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(i) for i in x]
    return x


def serialize_nlp_result(r: NLPOptimizationResult) -> Dict[str, Any]:
    """把 ``NLPOptimizationResult`` 打成可写入结果 JSON 的 dict。"""
    return json_safe(
        {
            "success": r.success,
            "message": r.message,
            "alpha": r.alpha,
            "transfer_time": r.transfer_time,
            "t_ins": r.t_ins,
            "objective_value": r.objective_value,
            "delta_v1": r.delta_v1,
            "delta_v2": r.delta_v2,
            "transfer_type": r.transfer_type.value if r.transfer_type else None,
            "constraints_violation": r.constraints_violation,
            "departure_state": r.departure_state,
            "insertion_state": r.insertion_state,
            "final_state": r.final_state,
            "transfer_trajectory": r.transfer_trajectory,
            "transfer_times": r.transfer_times,
        }
    )


def search_snapshot(rec: Dict[str, Any]) -> Dict[str, Any]:
    """单条网格记录在结果 JSON 中的快照字段。"""
    return {
        "alpha": rec.get("alpha"),
        "transfer_time": rec.get("transfer_time"),
        "min_distance": rec.get("min_distance"),
        "is_feasible": rec.get("is_feasible"),
        "status": rec.get("status"),
    }


def row_template(rec: Dict[str, Any], search_index: int) -> Dict[str, Any]:
    """单条结果记录骨架：网格下标、粗搜快照、错误与 NLP 占位。"""
    return {
        "search_index": search_index,
        "search_snapshot": search_snapshot(rec),
        "error": None,
        "nlp": None,
    }
