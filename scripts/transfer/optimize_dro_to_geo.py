"""
DRO → GEO NLP 优化

参考 optimize.py，将目标从 RO（周期轨道）替换为 GEO（固定半径球面）。

优化变量: y = [α, T]
目标函数: J(y) = Δv1 + Δv2
约束: |r_final - r_earth| = r_GEO  (GEO 球面约束)

运行: python scripts/transfer/optimize_dro_geo.py

进度条: tqdm；关闭: OPTIMIZE_NO_TQDM=1
Windows 须保留 ``if __name__ == "__main__"``。
"""

from __future__ import annotations

import json
import multiprocessing
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import Bounds, minimize
from tqdm.auto import tqdm

import e2m2e
from e2m2e.core import CR3BP_Dynamics, CR3BP_System
from scripts.utils.common import DU, MU, TU, VU
from scripts.utils.geo import (
    R_GEO,
    EARTH_CENTER,
    compute_departure_velocity,
    compute_geo_dv2,
    check_collision,
    find_closest_approach_to_geo,
)

project_root = Path(__file__).resolve().parent.parent.parent

# =====================================================================
# 配置 — 运行前须更新文件路径
# =====================================================================
SEARCH_RESULTS_FILE = project_root / (
    "output/transfer/search_dro_geo_200-100-0.5-2.5-22.9985_UPDATE_ME.json"
)
DRO_FILE = project_root / "output/dro/dro_31_3857864736.json"

ALPHA_MIN = 0.5
ALPHA_MAX = 2.5
T_MIN = 0.5
T_MAX = 30.0

EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

DT = 1.0 / (24.0 * TU)
INTEGRATOR = "DOP853"
INTEGRATOR_RTOL = 1e-12
INTEGRATOR_ATOL = 1e-12

NLP_MAXITER = 100
NLP_FTOL = 1e-8
NLP_RTOL = 1e-10
NLP_ATOL = 1e-10
NLP_MAX_STEP = 0.1

TOP_K_FEASIBLE: Optional[int] = None
MAX_CASES: Optional[int] = None

N_WORKERS: Optional[int] = None
PARALLEL_BACKEND: str = "processes"

LIMIT_BLAS_THREADS_PER_WORKER: int = 1

USE_TQDM = os.environ.get("OPTIMIZE_NO_TQDM", "").lower() not in ("1", "true", "yes")


# =====================================================================
# Helpers
# =====================================================================


def build_dynamics(
    integrator: str, rtol: float, atol: float, max_step: float, mu: float
):
    system = CR3BP_System(mu=mu, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = integrator
    dynamics.rtol = rtol
    dynamics.atol = atol
    dynamics.max_step = max_step
    return system, dynamics


def forward_integrate_nlp(dynamics, initial_state, transfer_time):
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


# =====================================================================
# NLP problem
# =====================================================================


def _nlp_eval(y, departure_state, dynamics):
    """Evaluate objective, constraint, and cache for y = [alpha, T]."""
    alpha, T = y
    v_dep = compute_departure_velocity(departure_state, alpha)
    dv1 = float(np.linalg.norm(v_dep - departure_state[3:]))
    state0 = np.concatenate([departure_state[:3], v_dep])

    try:
        states, times = forward_integrate_nlp(dynamics, state0, T)
    except Exception:
        return {"empty": True, "objective": 1e10}

    if len(states) == 0:
        return {"empty": True, "objective": 1e10}

    final_state = states[-1]
    final_pos = final_state[:3]
    dist = float(np.linalg.norm(final_pos - EARTH_CENTER))
    dv2 = compute_geo_dv2(final_state)
    pos_violation = (dist - R_GEO) ** 2

    return {
        "empty": False,
        "states": states,
        "times": times,
        "final_state": final_state,
        "dv1": dv1,
        "dv2": dv2,
        "objective": dv1 + dv2,
        "pos_violation": pos_violation,
        "dist_from_earth": dist,
    }


def optimize_one_case(
    rec,
    dynamics,
    mu,
    *,
    alpha_min=0.5,
    alpha_max=2.5,
    t_min=0.5,
    t_max=30.0,
    earth_radius=200.0 / DU,
    moon_radius=100.0 / DU,
    verbose=False,
):
    departure_state = np.array(rec["departure_state"], dtype=float)
    alpha_0 = rec["alpha"]
    T_0 = rec["transfer_time"]

    nlp_system = CR3BP_System(mu=mu, primary="earth", secondary="moon")
    nlp_dynamics = CR3BP_Dynamics(system=nlp_system)
    nlp_dynamics.integrator = dynamics.integrator
    nlp_dynamics.rtol = NLP_RTOL
    nlp_dynamics.atol = NLP_ATOL
    nlp_dynamics.max_step = NLP_MAX_STEP

    y0 = np.array([alpha_0, T_0])

    cache_holder = [None]

    def objective(y):
        c = _nlp_eval(y, departure_state, nlp_dynamics)
        cache_holder[0] = c
        if c["empty"]:
            return 1e10
        return c["objective"]

    def constraint_position(y):
        c = cache_holder[0]
        if c is None or c["empty"]:
            c = _nlp_eval(y, departure_state, nlp_dynamics)
            cache_holder[0] = c
        if c["empty"]:
            return 1e6
        return c["pos_violation"]

    bounds = Bounds(lb=[alpha_min, t_min], ub=[alpha_max, t_max])
    constraints = [{"type": "eq", "fun": constraint_position}]

    try:
        result = minimize(
            objective,
            y0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": NLP_FTOL, "maxiter": NLP_MAXITER, "disp": verbose},
        )

        final_y = result.x
        c = _nlp_eval(final_y, departure_state, nlp_dynamics)

        return {
            "search_index": rec.get("departure_time_index", -1),
            "alpha": float(rec["alpha"]),
            "transfer_time": float(rec["transfer_time"]),
            "departure_state": rec["departure_state"],
            "is_feasible": rec.get("is_feasible"),
            "dv_departure": rec.get("dv_departure"),
            "nlp": {
                "success": bool(result.success),
                "alpha": float(final_y[0]),
                "transfer_time": float(final_y[1]),
                "objective_value": c["objective"] if not c["empty"] else float(result.fun),
                "delta_v1": c.get("dv1", 0.0),
                "delta_v2": c.get("dv2", 0.0),
                "dist_from_earth": c.get("dist_from_earth", float("nan")),
                "pos_violation": c.get("pos_violation", float("nan")),
                "message": str(result.message),
            },
        }
    except Exception:
        return {
            "search_index": rec.get("departure_time_index", -1),
            "alpha": float(rec["alpha"]),
            "transfer_time": float(rec["transfer_time"]),
            "departure_state": rec["departure_state"],
            "nlp": {"success": False, "message": traceback.format_exc()},
        }


# =====================================================================
# Parallel workers
# =====================================================================


@dataclass
class NlpPackConfig:
    mu: float
    alpha_min: float
    alpha_max: float
    t_min: float
    t_max: float
    earth_radius: float
    moon_radius: float
    integrator: str
    integrator_rtol: float
    integrator_atol: float


def nlp_worker_packed(payload):
    idx = payload["idx"]
    rec = payload["rec"]
    cfg = payload["cfg"]

    _, dynamics = build_dynamics(
        cfg.integrator, cfg.integrator_rtol, cfg.integrator_atol, DT, cfg.mu
    )
    return optimize_one_case(
        rec,
        dynamics,
        cfg.mu,
        alpha_min=cfg.alpha_min,
        alpha_max=cfg.alpha_max,
        t_min=cfg.t_min,
        t_max=cfg.t_max,
        earth_radius=cfg.earth_radius,
        moon_radius=cfg.moon_radius,
    )


# =====================================================================
# main
# =====================================================================


def main() -> None:
    print("=" * 70, flush=True)
    print("DRO → GEO 转移 NLP 优化", flush=True)
    print("=" * 70, flush=True)

    if not SEARCH_RESULTS_FILE.is_file():
        raise FileNotFoundError(f"未找到搜索结果: {SEARCH_RESULTS_FILE}")
    if not DRO_FILE.is_file():
        raise FileNotFoundError(f"未找到 DRO 文件: {DRO_FILE}")

    _cpu = multiprocessing.cpu_count() or 1
    print(f"\n优化配置:", flush=True)
    print(f"  并行: n_workers={N_WORKERS}（None=逻辑CPU数 {_cpu}）, backend={PARALLEL_BACKEND}")
    print(f"  α 范围: [{ALPHA_MIN}, {ALPHA_MAX}]")
    print(f"  T 范围: [{T_MIN}, {T_MAX}]")
    print(f"  GEO 约束: |r - r_earth| = {R_GEO:.6f} DU")

    with open(SEARCH_RESULTS_FILE, encoding="utf-8") as f:
        all_results = json.load(f)

    feasible_indexed: List[Tuple[int, Dict[str, Any]]] = [
        (i, r) for i, r in enumerate(all_results) if r.get("is_feasible")
    ]
    n_feasible_total = len(feasible_indexed)

    if TOP_K_FEASIBLE is not None:
        feasible_indexed = feasible_indexed[:TOP_K_FEASIBLE]
    if MAX_CASES is not None:
        feasible_indexed = feasible_indexed[:MAX_CASES]

    del all_results

    print(f"\n可行解总数: {n_feasible_total}", flush=True)
    print(f"本次待优化: {len(feasible_indexed)}", flush=True)

    if not feasible_indexed:
        print("没有可行解，退出。")
        return

    _, dynamics = build_dynamics(INTEGRATOR, INTEGRATOR_RTOL, INTEGRATOR_ATOL, DT, MU)
    print(f"\n动力学就绪: μ={dynamics.system.mu:.6e}, integrator={dynamics.integrator}")

    pack_cfg = NlpPackConfig(
        mu=float(MU),
        alpha_min=float(ALPHA_MIN),
        alpha_max=float(ALPHA_MAX),
        t_min=float(T_MIN),
        t_max=float(T_MAX),
        earth_radius=float(EARTH_RADIUS),
        moon_radius=float(MOON_RADIUS),
        integrator=str(INTEGRATOR),
        integrator_rtol=float(NLP_RTOL),
        integrator_atol=float(NLP_ATOL),
    )

    output_dir = project_root / "output/transfer"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"optimization_dro_geo_{int(time.time())}.json"

    cpu_n = multiprocessing.cpu_count() or 1
    n_workers_req = N_WORKERS if N_WORKERS is not None else max(1, cpu_n)
    n_total = len(feasible_indexed)
    disable_tqdm = not USE_TQDM or n_total <= 0

    print("\n" + "=" * 70, flush=True)
    print("开始 NLP 优化", flush=True)
    print("=" * 70, flush=True)

    records: List[Dict[str, Any]] = []

    if n_workers_req == 1:
        for k, (global_idx, rec) in enumerate(feasible_indexed):
            try:
                row = optimize_one_case(
                    rec, dynamics, float(MU),
                    alpha_min=float(ALPHA_MIN),
                    alpha_max=float(ALPHA_MAX),
                    t_min=float(T_MIN),
                    t_max=float(T_MAX),
                    earth_radius=float(EARTH_RADIUS),
                    moon_radius=float(MOON_RADIUS),
                )
                records.append(row)
                nlp = row.get("nlp", {})
                elapsed = 0.0
                print(
                    f"  case {k + 1}/{n_total} (idx={global_idx}) | "
                    f"success={nlp.get('success')} ΔV={nlp.get('objective_value', 'N/A')}",
                    flush=True,
                )
            except Exception:
                records.append({"search_index": global_idx, "error": traceback.format_exc()})
    else:
        n_pool = min(n_workers_req, n_total)
        backend = PARALLEL_BACKEND.strip().lower()

        if backend == "processes":
            for _k in [
                "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "GOTO_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
            ]:
                os.environ[_k] = str(LIMIT_BLAS_THREADS_PER_WORKER)

        payloads = []
        for global_idx, rec in feasible_indexed:
            payloads.append({
                "idx": global_idx,
                "rec": rec,
                "cfg": pack_cfg,
            })

        Executor = ProcessPoolExecutor if backend == "processes" else ThreadPoolExecutor
        with Executor(max_workers=n_pool) as ex:
            futures = [ex.submit(nlp_worker_packed, p) for p in payloads]
            for fut in tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"NLP({backend}×{n_pool})",
                file=sys.stderr,
                dynamic_ncols=True,
                disable=disable_tqdm,
            ):
                records.append(fut.result())

        records.sort(key=lambda x: x.get("search_index", 0))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "search_results_file": str(SEARCH_RESULTS_FILE),
                    "dro_file": str(DRO_FILE),
                    "alpha_range": [ALPHA_MIN, ALPHA_MAX],
                    "transfer_time_range": [T_MIN, T_MAX],
                    "geo_radius": R_GEO,
                    "nlp_solver": "scipy_slsqp",
                    "n_optimized": len(records),
                    "parallel_backend": PARALLEL_BACKEND,
                    "n_workers_requested": N_WORKERS,
                },
                "results": records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    successes = [r for r in records if r.get("nlp", {}).get("success")]
    print(f"\n优化完成: {len(records)} 条, 成功 {len(successes)} 条")
    print(f"结果已保存: {out_path}")

    if successes:
        best = min(successes, key=lambda r: r["nlp"]["objective_value"])
        b = best["nlp"]
        print(f"\n最优解:")
        print(f"  α = {b['alpha']:.6f}")
        print(f"  T = {b['transfer_time']:.6f} TU ({b['transfer_time'] * TU:.2f} days)")
        print(f"  Δv1 = {b['delta_v1']:.6f} VU ({b['delta_v1'] * VU:.1f} m/s)")
        print(f"  Δv2 = {b['delta_v2']:.6f} VU ({b['delta_v2'] * VU:.1f} m/s)")
        print(f"  Δv_total = {b['objective_value']:.6f} VU ({b['objective_value'] * VU:.1f} m/s)")
        print(f"  |r - r_earth| = {b.get('dist_from_earth', 'N/A'):.6f} DU (target: {R_GEO:.6f})")


if __name__ == "__main__":
    main()
