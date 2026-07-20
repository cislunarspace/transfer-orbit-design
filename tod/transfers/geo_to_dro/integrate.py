"""积分和动力学相关函数。

本模块从 optimize_geo_to_dro.py 拆出，负责动力学构建、前向积分、DRO 状态插值。
"""

from __future__ import annotations

import numpy as np

from e2m2e.core import CR3BP_Dynamics
from e2m2e.core.orbit import Orbit
from tod.commons.orbits import compute_departure_velocity
from tod.transfers._common import build_dynamics, forward_integrate


def get_dro_state_at_time(dro_orbit: Orbit, t_ins: float) -> np.ndarray:
    """获取 DRO 轨道上在 t_ins 时刻的状态。

    使用 CR3BP_Dynamics 从 DRO 初始状态前向积分到 t_ins（对周期取模）。
    """
    period = dro_orbit.period
    if period is None or period <= 0:
        # 无周期信息，直接用最近的采样点
        idx = int(t_ins / (dro_orbit.times[-1] / len(dro_orbit.times))) % len(dro_orbit.times)
        return dro_orbit.states[idx]

    t_mod = t_ins % period
    # 在已有采样点中插值
    times = dro_orbit.times
    states = dro_orbit.states

    # 找到 t_mod 两侧的索引
    idx = np.searchsorted(times, t_mod, side="right") - 1
    idx = max(0, min(idx, len(times) - 2))

    t0, t1 = times[idx], times[idx + 1]
    s0, s1 = states[idx], states[idx + 1]

    if abs(t1 - t0) < 1e-15:
        return s0.copy()

    frac = (t_mod - t0) / (t1 - t0)
    return s0 + frac * (s1 - s0)


def find_closest_approach(departure_state, alpha, max_time, dro_orbit, dynamics):
    """重新积分转移轨迹，找到最接近 DRO 轨道的时刻。

    Returns:
        (t_closest, t_dro_closest, min_distance)
        t_closest: 转移轨迹上的时间（作为 T 初值）
        t_dro_closest: DRO 轨道上的时间（作为 t_ins 初值）
        min_distance: 最近距离 (DU)
    """
    v_dep = compute_departure_velocity(departure_state, alpha)
    s0 = np.concatenate([departure_state[:3], v_dep])

    step = max(0.01, dynamics.max_step)
    n_steps = int(max_time / step) + 1
    t_eval = np.linspace(0.0, max_time, n_steps)

    try:
        result = dynamics.propagate(
            initial_state=s0, t_span=(0.0, max_time),
            t_eval=t_eval, with_stm=False, with_jacobi=False,
        )
        states = result["states"]
        times = result["time"]
    # 仅捕获数值意义上的失败（积分发散/线性代数奇异）；编程错误应向上抛
    except (FloatingPointError, ValueError, RuntimeError, np.linalg.LinAlgError):
        return max_time * 0.5, 0.0, 1e10

    if len(states) == 0:
        return max_time * 0.5, 0.0, 1e10

    # DRO 轨道采样
    dro_states = dro_orbit.states
    dro_times = dro_orbit.times

    # 对每个转移轨迹点，找最近的 DRO 点
    min_dist_sq = float("inf")
    best_t_idx = 0
    best_dro_idx = 0

    # 分块处理避免内存爆炸
    chunk = 500
    for i_start in range(0, len(states), chunk):
        i_end = min(i_start + chunk, len(states))
        # (chunk, 1, 3) - (1, n_dro, 3) → (chunk, n_dro, 3)
        diff = states[i_start:i_end, np.newaxis, :3] - dro_states[np.newaxis, :, :3]
        dist_sq = np.sum(diff ** 2, axis=2)  # (chunk, n_dro)
        flat_idx = np.argmin(dist_sq)
        ci, di = np.unravel_index(flat_idx, dist_sq.shape)
        if dist_sq[ci, di] < min_dist_sq:
            min_dist_sq = dist_sq[ci, di]
            best_t_idx = i_start + ci
            best_dro_idx = di

    t_closest = float(times[best_t_idx])
    min_dist = float(np.sqrt(min_dist_sq))

    # DRO 时间
    if best_dro_idx < len(dro_times):
        t_dro_closest = float(dro_times[best_dro_idx])
    else:
        t_dro_closest = 0.0

    return t_closest, t_dro_closest, min_dist
