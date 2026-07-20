"""连续性验证相关函数。

本模块从 _conversion.py 拆出，负责轨道片段的连续性检查和位置误差计算。
"""

from __future__ import annotations

from typing import Any

def validate_continuity(
    dynamics: Any,
    corrected_times: list[float],
    corrected_states: list[list[float]],
    include_full_trajectory: bool,
) -> dict[str, Any]:
    """验证轨道片段的连续性。"""
    position_errors = []
    full_states = []
    full_times = []
    for index in range(max(0, len(corrected_states) - 1)):
        propagation = dynamics.propagate(
            corrected_states[index],
            (corrected_times[index], corrected_times[index + 1]),
        )
        propagated_states = to_nested_list(propagation["states"])
        propagated_times = to_list(propagation["time"])
        position_errors.append(
            position_error(propagated_states[-1], corrected_states[index + 1])
        )
        if include_full_trajectory:
            if index > 0:
                propagated_states = propagated_states[1:]
                propagated_times = propagated_times[1:]
            full_states.extend(propagated_states)
            full_times.extend(propagated_times)
    return {
        "position_errors_km": position_errors,
        "full_trajectory_states": full_states,
        "full_trajectory_times_et": full_times,
    }

def position_error(left_state: list[float], right_state: list[float]) -> float:
    """计算两个状态向量的位置误差（欧氏距离）。"""
    return sum(
        (float(left_state[index]) - float(right_state[index])) ** 2 for index in range(3)
    ) ** 0.5

def to_list(values: Any) -> list[float]:
    """将数组或列表转为 float list。"""
    if hasattr(values, "tolist"):
        values = values.tolist()
    return [float(value) for value in values]

def to_nested_list(values: Any) -> list[list[float]]:
    """将二维数组或列表转为 float 嵌套 list。"""
    if hasattr(values, "tolist"):
        values = values.tolist()
    return [[float(item) for item in row] for row in values]

def optional_float(value: Any) -> float | None:
    """安全转 float，None 保持 None。"""
    if value is None:
        return None
    return float(value)

def optional_float_list(values: Any) -> list[float] | None:
    """安全转 float list，None 保持 None。"""
    if values is None:
        return None
    return [float(value) for value in values]
