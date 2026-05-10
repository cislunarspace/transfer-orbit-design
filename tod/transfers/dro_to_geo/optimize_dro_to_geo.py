"""
DRO → GEO 转移 NLP 优化

在网格搜索结果的基础上，对 DRO→GEO 转移轨道进行 NLP 优化（SciPy SLSQP）。
优化变量: y = [α, T]
目标函数: J(y) = Δv1 + Δv2
约束: |r_final - r_earth| = r_GEO（到达 GEO 球面）

运行: python -m tod.transfers.dro_to_geo.optimize_dro_to_geo

进度条: tqdm；关闭: OPTIMIZE_NO_TQDM=1
Windows 须保留 ``if __name__ == "__main__"``。
"""

from __future__ import annotations

import argparse
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
from tod.commons.common import DU, MU, TU, VU
from e2m2e.orbits.geo import (
    R_GEO,
    EARTH_CENTER,
    compute_departure_velocity,
    compute_geo_dv2,
    check_collision,
    find_closest_approach_to_geo,
)
import logging

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent

# =====================================================================
# 配置 — 运行前须更新文件路径
# =====================================================================
SEARCH_RESULTS_DEFAULT = str(project_root / "output/transfer/search_dro_geo_200-100-0.5-2.5-22.9985_UPDATE_ME.json")
DRO_FILE_DEFAULT = str(project_root / "output/dro/dro_31_3857864736.json")

SEARCH_RESULTS_FILE = Path(os.environ.get("SEARCH_RESULTS_FILE", SEARCH_RESULTS_DEFAULT))
DRO_FILE = Path(os.environ.get("DRO_FILE", DRO_FILE_DEFAULT))

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


def parse_args():
    parser = argparse.ArgumentParser(description="DRO→GEO 转移 NLP 优化")
    parser.add_argument("--search-file", type=str, default=None, help="网格搜索结果 JSON 文件路径")
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径")
    parser.add_argument("--alpha-min", type=float, default=ALPHA_MIN, help="alpha 搜索下界")
    parser.add_argument("--alpha-max", type=float, default=ALPHA_MAX, help="alpha 搜索上界")
    parser.add_argument("--t-min", type=float, default=T_MIN, help="转移时间下界（无量纲）")
    parser.add_argument("--t-max", type=float, default=T_MAX, help="转移时间上界（无量纲）")
    parser.add_argument("--nlp-maxiter", type=int, default=NLP_MAXITER, help="NLP 最大迭代次数")
    parser.add_argument("--nlp-ftol", type=float, default=NLP_FTOL, help="NLP 函数容差")
    parser.add_argument("--top-k", type=int, default=None, help="取前 K 个可行解优化")
    parser.add_argument("--max-cases", type=int, default=None, help="最大优化案例数")
    parser.add_argument("--n-workers", type=int, default=None, help="并行 worker 数")
    return parser.parse_args()


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

    cache_holder: list[dict | None] = [None]

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

    bounds = Bounds(lb=[alpha_min, t_min], ub=[alpha_max, t_max])  # type: ignore[arg-type]
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
    args = parse_args()

    # CLI 参数覆盖
    search_file = Path(args.search_file or os.environ.get("SEARCH_RESULTS_FILE", SEARCH_RESULTS_DEFAULT))
    dro_file = Path(args.dro_file or os.environ.get("DRO_FILE", DRO_FILE_DEFAULT))
    alpha_min = args.alpha_min
    alpha_max = args.alpha_max
    t_min = args.t_min
    t_max = args.t_max
    top_k = args.top_k if args.top_k is not None else TOP_K_FEASIBLE
    max_cases = args.max_cases if args.max_cases is not None else MAX_CASES
    n_workers = args.n_workers if args.n_workers is not None else N_WORKERS

    logger.info("=" * 70)
    logger.info("DRO → GEO 转移 NLP 优化")
    logger.info("=" * 70)

    if not search_file.is_file():
        raise FileNotFoundError(f"未找到搜索结果: {search_file}")
    if not dro_file.is_file():
        raise FileNotFoundError(f"未找到 DRO 文件: {dro_file}")

    _cpu = multiprocessing.cpu_count() or 1
    logger.info(f"\n优化配置:")
    logger.info(f"  并行: n_workers={n_workers}（None=逻辑CPU数 {_cpu}）, backend={PARALLEL_BACKEND}")
    logger.info(f"  α 范围: [{alpha_min}, {alpha_max}]")
    logger.info(f"  T 范围: [{t_min}, {t_max}]")
    logger.info(f"  GEO 约束: |r - r_earth| = {R_GEO:.6f} DU")

    with open(search_file, encoding="utf-8") as f:
        all_results = json.load(f)

    feasible_indexed: List[Tuple[int, Dict[str, Any]]] = [
        (i, r) for i, r in enumerate(all_results) if r.get("is_feasible")
    ]
    n_feasible_total = len(feasible_indexed)

    if top_k is not None:
        feasible_indexed = feasible_indexed[:top_k]
    if max_cases is not None:
        feasible_indexed = feasible_indexed[:max_cases]

    del all_results

    logger.info(f"\n可行解总数: {n_feasible_total}")
    logger.info(f"本次待优化: {len(feasible_indexed)}")

    if not feasible_indexed:
        logger.info("没有可行解，退出。")
        return

    _, dynamics = build_dynamics(INTEGRATOR, INTEGRATOR_RTOL, INTEGRATOR_ATOL, DT, MU)
    logger.info(f"\n动力学就绪: μ={dynamics.system.mu:.6e}, integrator={dynamics.integrator}")

    pack_cfg = NlpPackConfig(
        mu=float(MU),
        alpha_min=float(alpha_min),
        alpha_max=float(alpha_max),
        t_min=float(t_min),
        t_max=float(t_max),
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
    n_workers_req = n_workers if n_workers is not None else max(1, cpu_n)
    n_total = len(feasible_indexed)
    disable_tqdm = not USE_TQDM or n_total <= 0

    logger.info("\n" + "=" * 70)
    logger.info("开始 NLP 优化")
    logger.info("=" * 70)

    records: List[Dict[str, Any]] = []

    if n_workers_req == 1:
        for k, (global_idx, rec) in enumerate(feasible_indexed):
            try:
                row = optimize_one_case(
                    rec, dynamics, float(MU),
                    alpha_min=float(alpha_min),
                    alpha_max=float(alpha_max),
                    t_min=float(t_min),
                    t_max=float(t_max),
                    earth_radius=float(EARTH_RADIUS),
                    moon_radius=float(MOON_RADIUS),
                )
                records.append(row)
                nlp = row.get("nlp", {})
                elapsed = 0.0
                logger.info(
                    f"  case {k + 1}/{n_total} (idx={global_idx}) | "
                    f"success={nlp.get('success')} ΔV={nlp.get('objective_value', 'N/A')}"
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
                    "search_results_file": str(search_file),
                    "dro_file": str(dro_file),
                    "alpha_range": [alpha_min, alpha_max],
                    "transfer_time_range": [t_min, t_max],
                    "geo_radius": R_GEO,
                    "nlp_solver": "scipy_slsqp",
                    "n_optimized": len(records),
                    "parallel_backend": PARALLEL_BACKEND,
                    "n_workers_requested": n_workers,
                },
                "results": records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    successes = [r for r in records if r.get("nlp", {}).get("success")]
    logger.info(f"\n优化完成: {len(records)} 条, 成功 {len(successes)} 条")
    logger.info(f"结果已保存: {out_path}")

    if successes:
        best = min(successes, key=lambda r: r["nlp"]["objective_value"])
        b = best["nlp"]
        logger.info(f"\n最优解:")
        logger.info(f"  α = {b['alpha']:.6f}")
        logger.info(f"  T = {b['transfer_time']:.6f} TU ({b['transfer_time'] * TU:.2f} days)")
        logger.info(f"  Δv1 = {b['delta_v1']:.6f} VU ({b['delta_v1'] * VU:.1f} m/s)")
        logger.info(f"  Δv2 = {b['delta_v2']:.6f} VU ({b['delta_v2'] * VU:.1f} m/s)")
        logger.info(f"  Δv_total = {b['objective_value']:.6f} VU ({b['objective_value'] * VU:.1f} m/s)")
        logger.info(f"  |r - r_earth| = {b.get('dist_from_earth', 'N/A'):.6f} DU (target: {R_GEO:.6f})")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--alpha-min", "0.5",                         # alpha 搜索下界（ALPHA_MIN）
            "--alpha-max", "2.5",                         # alpha 搜索上界（ALPHA_MAX）
            "--t-min", "0.5",                             # 转移时间下界（T_MIN）
            "--t-max", "30.0",                            # 转移时间上界（T_MAX）
            "--nlp-maxiter", "100",                       # NLP 最大迭代次数（NLP_MAXITER）
            "--nlp-ftol", "1e-8",                         # NLP 函数容差（NLP_FTOL）
        ]
        logger.debug("使用代码内置调试参数")
    main()
