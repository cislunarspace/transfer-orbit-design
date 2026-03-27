"""线程池 / 多进程池 worker：须为模块级可 pickle 函数（Windows ``spawn``）。"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np
import e2m2e

from scripts.transfer.optimize_io import row_template, serialize_nlp_result
from scripts.transfer.optimize_nlp import optimize_one_case


@dataclass(frozen=True)
class ThreadNlpParams:
    """线程池路径：与主进程脚本常量一致的 NLP 标量参数（无轨道/动力学对象）。"""

    alpha_min: float
    alpha_max: float
    earth_radius: float
    moon_radius: float
    use_relaxed_velocity: bool
    velocity_angle_tol: float
    use_copt: bool
    fallback_to_scipy: bool


@dataclass(frozen=True)
class NlpPackConfig:
    """与主进程 ``build_dynamics`` / 脚本常量一致的打包参数。"""

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


def pack_nlp_task(
    search_index: int,
    rec: Dict[str, Any],
    dro_orbit: Any,
    ro_orbit: Any,
    cfg: NlpPackConfig,
) -> Tuple[Any, ...]:
    """打包为可 pickle 元组，供 ``nlp_worker_packed`` 在子进程重建轨道与动力学。

    顺序为：search_index、rec、DRO 状态/时间/周期、RO 状态/时间/周期、μ、α 范围、
    撞球半径、占位 DT、积分器名、rtol、atol、max_step、松弛速度/COPT 开关等。
    """
    return (
        int(search_index),
        rec,
        np.asarray(dro_orbit.states, dtype=float),
        np.asarray(dro_orbit.times, dtype=float),
        float(dro_orbit.period),
        np.asarray(ro_orbit.states, dtype=float),
        np.asarray(ro_orbit.times, dtype=float),
        float(ro_orbit.period),
        float(cfg.mu),
        float(cfg.alpha_min),
        float(cfg.alpha_max),
        float(cfg.earth_radius),
        float(cfg.moon_radius),
        float(cfg.dt),
        str(cfg.integrator),
        float(cfg.integrator_rtol),
        float(cfg.integrator_atol),
        float(cfg.dt),
        bool(cfg.use_relaxed_velocity),
        float(cfg.velocity_angle_tol),
        bool(cfg.use_copt),
        bool(cfg.fallback_to_scipy),
    )


def nlp_worker_packed(packed: Tuple[Any, ...]) -> Dict[str, Any]:
    """子进程入口：解包 ``pack_nlp_task`` 元组，重建 ``Orbit``/动力学后调用 ``optimize_one_case``。

    须为模块级函数，便于 Windows ``spawn`` 下 pickle。
    """
    (
        search_index,
        rec,
        dro_states,
        dro_times,
        dro_period,
        ro_states,
        ro_times,
        ro_period,
        mu,
        alpha_min,
        alpha_max,
        earth_radius,
        moon_radius,
        _dt_unused,
        integrator,
        rtol,
        atol,
        max_step,
        use_relaxed_velocity,
        velocity_angle_tol,
        use_copt,
        fallback_to_scipy,
    ) = packed

    from e2m2e.core.orbit import Orbit  # 子进程内再导入，避免部分 fork 场景问题

    dro_orbit = Orbit(
        states=np.asarray(dro_states, dtype=float),
        times=np.asarray(dro_times, dtype=float),
    )
    dro_orbit.period = float(dro_period)
    ro_orbit = Orbit(
        states=np.asarray(ro_states, dtype=float),
        times=np.asarray(ro_times, dtype=float),
    )
    ro_orbit.period = float(ro_period)

    system = e2m2e.core.system.CR3BP_System(mu=float(mu), primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = str(integrator)
    dynamics.rtol = float(rtol)
    dynamics.atol = float(atol)
    dynamics.max_step = float(max_step)

    out = row_template(rec, int(search_index))
    try:
        result = optimize_one_case(
            rec,
            dro_orbit,
            ro_orbit,
            system,
            dynamics,
            verbose=False,
            alpha_min=float(alpha_min),
            alpha_max=float(alpha_max),
            earth_radius=float(earth_radius),
            moon_radius=float(moon_radius),
            use_relaxed_velocity=bool(use_relaxed_velocity),
            velocity_angle_tol=float(velocity_angle_tol),
            use_copt=bool(use_copt),
            fallback_to_scipy=bool(fallback_to_scipy),
        )
        out["nlp"] = serialize_nlp_result(result)
    except Exception:
        out["error"] = traceback.format_exc()
    return out


def worker_run_thread(
    args: Tuple[Dict[str, Any], int, Any, Any, Any, Any, ThreadNlpParams],
) -> Dict[str, Any]:
    """线程池入口：共享主进程已加载的轨道与动力学（无 pickle 大数组）。"""
    rec, search_index, dro, ro, system, dynamics, p = args
    out = row_template(rec, search_index)
    try:
        result = optimize_one_case(
            rec,
            dro,
            ro,
            system,
            dynamics,
            verbose=False,
            alpha_min=p.alpha_min,
            alpha_max=p.alpha_max,
            earth_radius=p.earth_radius,
            moon_radius=p.moon_radius,
            use_relaxed_velocity=p.use_relaxed_velocity,
            velocity_angle_tol=p.velocity_angle_tol,
            use_copt=p.use_copt,
            fallback_to_scipy=p.fallback_to_scipy,
        )
        out["nlp"] = serialize_nlp_result(result)
    except Exception:
        out["error"] = traceback.format_exc()
    return out
