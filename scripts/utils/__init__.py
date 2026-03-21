"""
通用辅助函数包

每个函数单独一个文件，便于维护和复用。
"""

import json
import numpy as np
from typing import Tuple, Dict, Any, Optional

from .params import (
    MU,
    DU,
    TU,
    VU,
    T_MOON,
    M_SUN,
    OMEGA_SUN,
    RHO,
)


# ============================================================
# 轨道数据加载与保存
# ============================================================
def load_orbit_data(json_path: str) -> dict:
    """加载轨道数据JSON文件

    参数:
        json_path: JSON文件路径

    返回:
        解析后的字典数据
    """
    with open(json_path, "r") as f:
        return json.load(f)


def create_orbit_from_data(
    data: dict, index: int, system: "CR3BP_System"
) -> Tuple["Orbit", np.ndarray]:
    """从JSON数据创建Orbit对象

    参数:
        data: load_orbit_data 返回的字典
        index: 轨道在 data['orbits'] 中的索引
        system: CR3BP_System对象

    返回:
        (orbit, departure_state): Orbit对象和出发点状态
    """
    from e2m2e.core.orbit import Orbit

    orbit_data = data["orbits"][index]
    states = np.array(orbit_data["states"])
    times = np.array(orbit_data["times"])

    orbit = Orbit(states=states, times=times, system=system)
    orbit.period = orbit_data.get("period", times[-1] - times[0])
    orbit.jacobi_constant = orbit_data.get("jacobi")

    # 出发点: 远地点(x最大)
    x_max_idx = np.argmax(states[:, 0])
    departure_state = states[x_max_idx]

    return orbit, departure_state


def save_transfer_result_to_json(
    result: "NLPOptimizationResult",
    dro_orbit: "Orbit",
    ro_orbit: "Orbit",
    output_path: str,
) -> None:
    """保存转移优化结果到JSON文件

    参数:
        result: NLPOptimizationResult对象
        dro_orbit: DRO Orbit对象
        ro_orbit: RO Orbit对象
        output_path: 输出文件路径
    """
    output_data = {
        "success": result.success,
        "message": result.message,
        "transfer_type": result.transfer_type.value,
        "variables": {
            "alpha": result.variables.alpha,
            "transfer_time": result.variables.transfer_time,
            "t_ins": result.variables.t_ins,
        },
        "delta_v": {
            "dv1": result.delta_v1,
            "dv2": result.delta_v2,
            "total": result.objective_value,
        },
        "departure_state": result.departure_state.tolist()
        if result.departure_state is not None
        else None,
        "insertion_state": result.insertion_state.tolist()
        if result.insertion_state is not None
        else None,
        "final_state": result.final_state.tolist()
        if result.final_state is not None
        else None,
        "constraints_violation": result.constraints_violation,
        "dro_period": dro_orbit.period,
        "ro_period": ro_orbit.period,
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)


__all__ = [
    # 参数
    "MU",
    "DU",
    "TU",
    "VU",
    "T_MOON",
    "M_SUN",
    "OMEGA_SUN",
    "RHO",
    # 轨道数据操作
    "load_orbit_data",
    "create_orbit_from_data",
    "save_transfer_result_to_json",
]
