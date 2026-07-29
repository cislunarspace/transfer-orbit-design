"""并行调度相关的数据结构和 worker 函数。

本模块从 optimize_dro_to_ro.py 拆出，负责 NLP 任务的打包、并行 worker 的执行逻辑。
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from e2m2e.core.orbit import Orbit
from tod.transfers._common import NlpPackConfig

@dataclass
class ThreadNlpParams:

    pack_config: NlpPackConfig

def pack_nlp_task(idx, rec, dro_orbit, ro_orbit, cfg: NlpPackConfig):
    """将轨道数据和配置打包为可序列化的字典，供进程池 worker 使用。"""
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
        cfg.integrator_rtol,
        cfg.integrator_atol,
        cfg.dt,
        integrator=cfg.integrator,
        mu=cfg.mu,
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
            alpha_min=params.pack_config.alpha_min,
            alpha_max=params.pack_config.alpha_max,
            earth_radius=params.pack_config.earth_radius,
            moon_radius=params.pack_config.moon_radius,
            use_relaxed_velocity=params.pack_config.use_relaxed_velocity,
            velocity_angle_tol=params.pack_config.velocity_angle_tol,
            use_copt=params.pack_config.use_copt,
            fallback_to_scipy=params.pack_config.fallback_to_scipy,
        )
        row["nlp"] = serialize_nlp_result(res)
    # 仅捕获数值意义上的失败（积分发散/优化器数值异常）；编程错误应向上抛
    except (FloatingPointError, ValueError, RuntimeError, np.linalg.LinAlgError):
        row["error"] = traceback.format_exc()
    return row
