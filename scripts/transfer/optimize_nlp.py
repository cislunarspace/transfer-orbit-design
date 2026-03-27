"""单条 DRO–RO 网格可行解的 NLP（e2m2e ``DROTRONLPOptimizer``）。"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
import e2m2e
from e2m2e.transfer import (
    DROTRONLPOptimizer,
    NLPOptimizationResult,
    NLPOptimizationVariables,
)

from scripts.utils.common import MU


def t_ins_bounds(ro_orbit: Any) -> Tuple[float, float]:
    """插入时刻 t_ins 的搜索区间：一个 RO 周期 ``[t0, t0+period]``。"""
    t0 = float(ro_orbit.times[0])
    per = float(ro_orbit.period)
    return (t0, t0 + per)


def initial_guess_from_search(
    rec: Dict[str, Any], ro_orbit: Any
) -> NLPOptimizationVariables:
    """由网格结果构造 (α, T, t_ins) 初值。α、T 来自粗搜；t_ins 优先用 ``min_distance_orbit_idx`` 在 RO 时间轴上的时刻，否则取半周期。"""
    alpha = float(rec["alpha"])
    transfer_time = float(rec["transfer_time"])
    idx = rec.get("min_distance_orbit_idx")
    t0 = float(ro_orbit.times[0])
    per = float(ro_orbit.period)
    if idx is not None:
        i = int(idx) % len(ro_orbit.times)
        t_ins = float(ro_orbit.times[i])
    else:
        t_ins = t0 + 0.5 * per
    return NLPOptimizationVariables(
        alpha=alpha, transfer_time=transfer_time, t_ins=t_ins
    )


def build_dynamics(
    *,
    integrator: str,
    rtol: float,
    atol: float,
    max_step: float,
    mu: float = MU,
) -> Tuple[Any, Any]:
    """构造地月 CR3BP 系统与动力学。"""
    system = e2m2e.core.system.CR3BP_System(mu=mu, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = integrator
    dynamics.rtol = rtol
    dynamics.atol = atol
    dynamics.max_step = max_step
    return system, dynamics


def optimize_one_case(
    rec: Dict[str, Any],
    dro_orbit: Any,
    ro_orbit: Any,
    system: Any,
    dynamics: Any,
    *,
    verbose: bool = False,
    alpha_min: float,
    alpha_max: float,
    earth_radius: float,
    moon_radius: float,
    use_relaxed_velocity: bool,
    velocity_angle_tol: float,
    use_copt: bool,
    fallback_to_scipy: bool,
    progress_callback: Optional[Callable] = None,
) -> NLPOptimizationResult:
    """对单条网格可行解做 NLP。参数由调用方传入（与 ``grid_search`` / 主脚本常量一致）。"""
    dep = np.asarray(rec["departure_state"], dtype=float).ravel()
    if dep.size != 6:
        raise ValueError("departure_state 须为长度 6 的向量")

    opt = DROTRONLPOptimizer(
        system=system,
        dynamics=dynamics,
        departure_orbit=dro_orbit,
        arrival_orbit=ro_orbit,
        departure_state=dep,
    )
    opt.earth_radius = earth_radius
    opt.moon_radius = moon_radius

    t_lo, t_hi = t_ins_bounds(ro_orbit)
    guess = initial_guess_from_search(rec, ro_orbit)

    if progress_callback is not None and hasattr(opt, "set_progress_callback"):
        opt.set_progress_callback(progress_callback)

    kwargs_opt: Dict[str, Any] = dict(
        initial_guess=guess,
        alpha_range=(alpha_min, alpha_max),
        t_ins_range=(t_lo, t_hi),
        use_relaxed_velocity_constraint=use_relaxed_velocity,
        velocity_angle_constraint=velocity_angle_tol,
        verbose=verbose,
    )

    if use_copt:
        from e2m2e.transfer import _HAVE_COPT, optimize_with_copt

        if _HAVE_COPT:
            scipy_kw = {k: v for k, v in kwargs_opt.items() if k != "initial_guess"}
            return optimize_with_copt(
                opt,
                initial_guess=guess,
                fallback_to_scipy=fallback_to_scipy,
                max_iter=1000,
                threads=1,
                bar_threads=1,
                scipy_fallback_kwargs=scipy_kw,
            )

    return opt.optimize(**kwargs_opt)
