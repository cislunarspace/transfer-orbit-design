"""转移管线共享工具函数。

各 transfer 子模块（geo_to_dro、dro_to_geo、dro_to_ro 等）的公共实现，
消除跨文件代码重复。不可作为脚本运行。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from e2m2e.core import CR3BP_Dynamics, CR3BP_System
from tod.commons.constants import MU


@dataclass
class NlpPackConfig:
    """NLP 打包配置（各管线共享）。

    核心字段对所有管线通用；管线特有字段给默认值，不传即可。
    """

    alpha_min: float
    alpha_max: float
    earth_radius: float
    moon_radius: float
    mu: float = MU
    t_min: float = 0.0
    t_max: float = 0.0
    dt: float = 0.0
    t_ins_min: float = 0.0
    t_ins_max: float = 0.0
    integrator: str = "DOP853"
    integrator_rtol: float = 1e-12
    integrator_atol: float = 1e-12
    angle_tolerance: float = 0.0
    use_relaxed_velocity: bool = False
    velocity_angle_tol: float = 0.0
    use_copt: bool = False
    fallback_to_scipy: bool = False

def build_dynamics(
    rtol: float,
    atol: float,
    max_step: float,
    *,
    integrator: str = "DOP853",
    mu: float = MU,
) -> tuple["CR3BP_System", "CR3BP_Dynamics"]:
    """构建 CR3BP 地月系动力学模型。

    Args:
        rtol: 积分器相对容差。
        atol: 积分器绝对容差。
        max_step: 最大步长。
        integrator: 积分器名称，默认 "DOP853"。
        mu: CR3BP 质量参数，默认地月系 MU。

    Returns:
        ``(system, dynamics)`` 元组。
    """
    system = CR3BP_System(mu=mu, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = integrator
    dynamics.rtol = rtol
    dynamics.atol = atol
    dynamics.max_step = max_step
    return system, dynamics

def forward_integrate(
    dynamics: "CR3BP_Dynamics",
    initial_state: np.ndarray,
    transfer_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    """前向积分转移轨道。

    根据 dynamics.max_step 计算 t_eval 采样点并调用 dynamics.propagate。

    Args:
        dynamics: CR3BP 动力学对象。
        initial_state: 初始状态 ``(6,)``。
        transfer_time: 积分时长（无量纲）。

    Returns:
        ``(states, times)`` 元组，states 为 ``(n, 6)``，times 为 ``(n,)``。
    """
    step = max(0.01, dynamics.max_step)
    n_steps = int(transfer_time / step) + 1
    t_eval = np.linspace(0.0, transfer_time, n_steps)
    result = dynamics.propagate(
        initial_state=initial_state,
        t_span=(0.0, transfer_time),
        t_eval=t_eval,
        with_stm=False,
        with_jacobi=False,
    )
    return result["states"], result["time"]
