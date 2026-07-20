"""并行调度相关的数据结构和 worker 函数。

本模块从 optimize_dro_to_ro.py 拆出，负责 NLP 任务的打包、并行 worker 的执行逻辑。
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from e2m2e.core.orbit import Orbit

@dataclass
class NlpPackConfig:
    """保存 NlpPackConfig 的配置字段。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
    mu: float
    alpha_min: float
    alpha_max: float
    earth_radius: float
    moon_radius: float
    dt: float
    integrator: str
    integrator_rtol: float
    integrator_atol: float
    use_relaxed_velocity: bool
    velocity_angle_tol: float
    use_copt: bool
    fallback_to_scipy: bool

@dataclass
class ThreadNlpParams:

    alpha_min: float
    alpha_max: float
    earth_radius: float
    moon_radius: float
    use_relaxed_velocity: bool
    velocity_angle_tol: float
    use_copt: bool
    fallback_to_scipy: bool

def pack_nlp_task(idx, rec, dro_orbit, ro_orbit, cfg: NlpPackConfig):
    """执行 pack_nlp_task 对应的处理逻辑。
    
    Args:
        idx: 调用方传入的参数值。
        rec: 调用方传入的参数值。
        dro_orbit: 调用方传入的参数值。
        ro_orbit: 调用方传入的参数值。
        cfg: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    return {
        "idx": idx,
        "rec": rec,
        "dro_states": np.array(dro_orbit.states),
        "dro_times": np.array(dro_orbit.times),
        "dro_period": float(dro_orbit.period) if hasattr(dro_orbit, "period") else None,
        "ro_states": np.array(ro_orbit.states),
        "ro_times": np.array(ro_orbit.times),
        "ro_period": float(ro_orbit.period) if hasattr(ro_orbit, "period") else None,
        "cfg": cfg,
    }

def nlp_worker_packed(payload):

    # 延迟 import 避免循环依赖
    from tod.transfers.dro_to_ro.optimize_dro_to_ro import (
        build_dynamics,
        optimize_one_case,
        row_template,
        serialize_nlp_result,
    )
    
    idx = payload["idx"]
    rec = payload["rec"]
    cfg = payload["cfg"]

    system, dynamics = build_dynamics(
        cfg.integrator,
        cfg.integrator_rtol,
        cfg.integrator_atol,
        cfg.dt,
        cfg.mu,
    )
    dro = Orbit(states=payload["dro_states"], times=payload["dro_times"])
    if payload["dro_period"] is not None:
        dro.period = payload["dro_period"]
    ro = Orbit(states=payload["ro_states"], times=payload["ro_times"])
    if payload["ro_period"] is not None:
        ro.period = payload["ro_period"]

    row = row_template(rec, idx)
    try:
        res = optimize_one_case(
            rec,
            dro,
            ro,
            system,
            dynamics,
            verbose=False,
            alpha_min=cfg.alpha_min,
            alpha_max=cfg.alpha_max,
            earth_radius=cfg.earth_radius,
            moon_radius=cfg.moon_radius,
            use_relaxed_velocity=cfg.use_relaxed_velocity,
            velocity_angle_tol=cfg.velocity_angle_tol,
            use_copt=cfg.use_copt,
            fallback_to_scipy=cfg.fallback_to_scipy,
        )
        row["nlp"] = serialize_nlp_result(res)
    # 仅捕获数值意义上的失败（积分发散/优化器数值异常）；编程错误应向上抛
    except (FloatingPointError, ValueError, RuntimeError, np.linalg.LinAlgError):
        row["error"] = traceback.format_exc()
    return row

def worker_run_thread(args):

    # 延迟 import 避免循环依赖
    from tod.transfers.dro_to_ro.optimize_dro_to_ro import (
        optimize_one_case,
        row_template,
        serialize_nlp_result,
    )
    
    rec, idx, dro_orbit, ro_orbit, system, dynamics, params = args
    row = row_template(rec, idx)
    try:
        res = optimize_one_case(
            rec,
            dro_orbit,
            ro_orbit,
            system,
            dynamics,
            verbose=False,
            alpha_min=params.alpha_min,
            alpha_max=params.alpha_max,
            earth_radius=params.earth_radius,
            moon_radius=params.moon_radius,
            use_relaxed_velocity=params.use_relaxed_velocity,
            velocity_angle_tol=params.velocity_angle_tol,
            use_copt=params.use_copt,
            fallback_to_scipy=params.fallback_to_scipy,
        )
        row["nlp"] = serialize_nlp_result(res)
    # 仅捕获数值意义上的失败（积分发散/优化器数值异常）；编程错误应向上抛
    except (FloatingPointError, ValueError, RuntimeError, np.linalg.LinAlgError):
        row["error"] = traceback.format_exc()
    return row
