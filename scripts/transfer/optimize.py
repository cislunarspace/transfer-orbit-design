"""
DRO-RO 转移 NLP（Cui et al. 2025）：在网格搜索结果上对 y=(α,T,t_ins) 最小化 Δv，默认 SciPy SLSQP（``DROTRONLPOptimizer``）。

须与 ``grid_search.py`` 生成 ``search_results`` 时一致：轨道 JSON、网格时间上限与步长、α 范围、碰撞半径等。

运行: ``python optimize.py``。进度条: ``tqdm``；关闭: ``OPTIMIZE_NO_TQDM=1``。

并行: 默认 ``PARALLEL_BACKEND="processes"``、``N_WORKERS=None``；子进程经 ``nlp_worker_packed`` 重建轨道，绕过 GIL。
多进程创建前会限制每 worker 的 BLAS 线程（``LIMIT_BLAS_THREADS_PER_WORKER`` / ``OPTIMIZE_BLAS_THREADS_PER_WORKER``）。

Windows 须保留末尾 ``if __name__ == "__main__"``。
"""

from __future__ import annotations

import json
import multiprocessing
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fontTools.misc.timeTools import timestampNow
from tqdm.auto import tqdm

from e2m2e.core import CR3BP_Dynamics, CR3BP_System
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import (
    DROTRONLPOptimizer,
    NLPOptimizationVariables,
    load_orbit_from_json,
    optimize_with_copt,
)

from scripts.utils.common import DU, MU, TU

project_root = Path(__file__).resolve().parent.parent.parent

SEARCH_RESULTS_FILE = project_root / (
    "output/transfer/search_results_200-1001-0.5-2.5-22.998482_3857379210.json"
)
DRO_FILE = project_root / "output/dro/dro_31_3857199098.json"
RO_FILE = project_root / "output/ro/ro_31_3857328571.json"

ALPHA_MIN = 0.5
ALPHA_MAX = 2.5

EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

DT = 1.0 / (24.0 * TU)
INTEGRATOR = "DOP853"
INTEGRATOR_RTOL = 1e-12
INTEGRATOR_ATOL = 1e-12

TOP_K_FEASIBLE: Optional[int] = None
MAX_CASES: Optional[int] = None

N_WORKERS: Optional[int] = None
PARALLEL_BACKEND: str = "processes"

LIMIT_BLAS_THREADS_PER_WORKER: int = 1

USE_TQDM = os.environ.get("OPTIMIZE_NO_TQDM", "").lower() not in ("1", "true", "yes")

USE_COPT = False
FALLBACK_TO_SCIPY = True

USE_RELAXED_VELOCITY = True
VELOCITY_ANGLE_TOL = 0.05

DEBUG_DEPARTURE_POINT: Optional[Tuple[float, float, float]] = None


# ---------------------------------------------------------------------------
# Inline helpers (replacing missing optimize_io / optimize_progress / etc.)
# ---------------------------------------------------------------------------


def load_search_results(filepath: Path) -> List[Dict[str, Any]]:
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def row_template(rec: Dict[str, Any], global_idx: int) -> Dict[str, Any]:
    return {
        "search_index": global_idx,
        "alpha": rec.get("alpha"),
        "transfer_time": rec.get("transfer_time"),
        "departure_state": rec.get("departure_state"),
        "is_feasible": rec.get("is_feasible"),
        "dv_departure": rec.get("dv_departure"),
    }


def serialize_nlp_result(res) -> Dict[str, Any]:
    return {
        "success": res.success,
        "alpha": float(res.alpha),
        "transfer_time": float(res.transfer_time),
        "t_ins": float(res.t_ins),
        "objective_value": float(res.objective_value),
        "delta_v1": float(res.delta_v1),
        "delta_v2": float(res.delta_v2),
        "message": res.message,
        "constraints_violation": {
            k: float(v) for k, v in (res.constraints_violation or {}).items()
        },
        "transfer_type": res.transfer_type.value if res.transfer_type else None,
    }


def build_dynamics(integrator: str, rtol: float, atol: float, max_step: float, mu: float):
    system = CR3BP_System(mu=mu, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = integrator
    dynamics.rtol = rtol
    dynamics.atol = atol
    dynamics.max_step = max_step
    return system, dynamics


def optimize_one_case(
    rec,
    dro_orbit,
    ro_orbit,
    system,
    dynamics,
    *,
    verbose=False,
    alpha_min=0.5,
    alpha_max=2.5,
    earth_radius=200.0 / DU,
    moon_radius=100.0 / DU,
    use_relaxed_velocity=True,
    velocity_angle_tol=0.05,
    use_copt=False,
    fallback_to_scipy=True,
    progress_callback=None,
):
    departure_state = np.array(rec["departure_state"], dtype=float)
    ig = NLPOptimizationVariables(
        alpha=rec["alpha"],
        transfer_time=rec["transfer_time"],
        t_ins=rec.get("t_ins", 0.0),
    )
    optimizer = DROTRONLPOptimizer(
        system=system,
        dynamics=dynamics,
        departure_orbit=dro_orbit,
        arrival_orbit=ro_orbit,
        departure_state=departure_state,
    )
    optimizer.alpha_range = (alpha_min, alpha_max)
    optimizer.earth_radius = earth_radius
    optimizer.moon_radius = moon_radius

    if progress_callback is not None:
        optimizer.set_progress_callback(progress_callback)

    if use_copt:
        return optimize_with_copt(
            optimizer,
            initial_guess=ig,
            fallback_to_scipy=fallback_to_scipy,
        )
    else:
        return optimizer.optimize(
            initial_guess=ig,
            alpha_range=(alpha_min, alpha_max),
            use_relaxed_velocity_constraint=use_relaxed_velocity,
            velocity_angle_constraint=velocity_angle_tol,
            verbose=verbose,
        )


def blas_threads_per_worker(default_limit: int = 1) -> int:
    env_val = os.environ.get("OPTIMIZE_BLAS_THREADS_PER_WORKER", "").strip()
    if env_val:
        return max(1, int(env_val))
    return default_limit


def apply_blas_env_for_child_processes(n_threads: int) -> None:
    for key in [
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        os.environ[key] = str(n_threads)


class OptimizationProgress:
    def __init__(self):
        self.total_cases = 0
        self.start_time = 0.0
        self._iter = 0
        self._successes = 0
        self._failures = 0
        self._best_obj = float("inf")

    def start_case(self, k, n_total, global_idx):
        if self.start_time == 0:
            self.start_time = time.perf_counter()
        self._iter = 0

    def finish_case(self, success, obj_value):
        if success:
            self._successes += 1
            self._best_obj = min(self._best_obj, obj_value)
        else:
            self._failures += 1

    def get_snapshot(self):
        return {
            "iter": self._iter,
            "successes": self._successes,
            "failures": self._failures,
            "best_obj": self._best_obj,
        }


def make_progress_callback(prog: OptimizationProgress, k, n_total, global_idx):
    def _cb(iteration, obj_value, alpha, T, t_ins):
        prog._iter = iteration

    return _cb


def monitor_loop_serial_nlp(prog: OptimizationProgress):
    while True:
        time.sleep(10)
        if prog.start_time > 0 and prog.total_cases > 0:
            done = prog._successes + prog._failures
            if done >= prog.total_cases:
                break
            elapsed = time.perf_counter() - prog.start_time
            snap = prog.get_snapshot()
            print(
                f"  [monitor] elapsed={elapsed:.1f}s | "
                f"done={done}/{prog.total_cases} | "
                f"best_dV={snap['best_obj']:.6f}",
                flush=True,
            )


@dataclass
class NlpPackConfig:
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
    except Exception:
        row["error"] = traceback.format_exc()
    return row


def worker_run_thread(args):
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
    except Exception:
        row["error"] = traceback.format_exc()
    return row


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    """加载网格与轨道、筛选可行解、按并行设置跑 NLP，并写出 ``optimization_results_*.json``。"""
    print("=" * 70, flush=True)
    print("DRO-RO 转移 NLP 优化（Cui et al. 2025；e2m2e DROTRONLPOptimizer）", flush=True)
    print("=" * 70, flush=True)

    if not SEARCH_RESULTS_FILE.is_file():
        raise FileNotFoundError(f"未找到网格结果文件: {SEARCH_RESULTS_FILE}")
    if not DRO_FILE.is_file():
        raise FileNotFoundError(f"未找到 DRO 文件: {DRO_FILE}")
    if not RO_FILE.is_file():
        raise FileNotFoundError(f"未找到 RO 文件: {RO_FILE}")

    print(f"\n优化配置:", flush=True)
    _cpu = multiprocessing.cpu_count() or 1
    print(
        f"  并行: n_workers={N_WORKERS}（None=逻辑 CPU 数 {_cpu}）, backend={PARALLEL_BACKEND}",
        flush=True,
    )
    print(f"  TOP_K_FEASIBLE: {TOP_K_FEASIBLE}")
    print(f"  MAX_CASES: {MAX_CASES}")
    print(f"  α 范围: [{ALPHA_MIN:.2f}, {ALPHA_MAX:.2f}]")
    print(f"  积分步长（1 小时）: {DT:.8f} TU")
    print(f"  碰撞半径: 地球={EARTH_RADIUS:.4f}, 月球={MOON_RADIUS:.4f}")
    print(f"  进度条: {'开启（tqdm）' if USE_TQDM else '关闭（OPTIMIZE_NO_TQDM）'}")

    print(f"\n加载网格结果:", flush=True)
    print(f"  文件: {SEARCH_RESULTS_FILE}", flush=True)
    print("  正在读取 JSON（大文件可能较慢）…", flush=True)
    all_results = load_search_results(SEARCH_RESULTS_FILE)
    total_records = len(all_results)
    feasible_indexed: List[Tuple[int, Dict[str, Any]]] = [
        (i, r) for i, r in enumerate(all_results) if r.get("is_feasible")
    ]

    n_feasible_total = len(feasible_indexed)
    if TOP_K_FEASIBLE is not None:
        feasible_indexed = feasible_indexed[:TOP_K_FEASIBLE]
    if MAX_CASES is not None:
        feasible_indexed = feasible_indexed[:MAX_CASES]

    del all_results

    print(f"\n网格记录总数: {total_records}", flush=True)
    print(f"可行解总数: {n_feasible_total}", flush=True)
    print(f"本次待优化（经 TOP_K / MAX_CASES 截断后）: {len(feasible_indexed)}", flush=True)
    if USE_COPT:
        from e2m2e.transfer import _HAVE_COPT

        print(f"NLP: COPT（已安装: {_HAVE_COPT}），失败则 SciPy SLSQP", flush=True)
    else:
        print("NLP: SciPy SLSQP（scipy.optimize.minimize）", flush=True)

    if not feasible_indexed:
        print("\n没有可行解，退出。")
        return

    print(f"\n加载轨道数据:", flush=True)
    dro_orbit = load_orbit_from_json(str(DRO_FILE))
    ro_orbit = load_orbit_from_json(str(RO_FILE))
    print(f"  DRO: {DRO_FILE}", flush=True)
    print(f"  RO: {RO_FILE}", flush=True)

    with open(RO_FILE, encoding="utf-8") as f:
        ro_json = json.load(f)
    if "properties" in ro_json and "period" in ro_json["properties"]:
        ro_orbit.period = float(ro_json["properties"]["period"])

    print(f"  DRO 周期: {dro_orbit.period:.4f} TU, 状态数: {len(dro_orbit.states)}", flush=True)
    print(f"  RO 周期: {ro_orbit.period:.4f} TU, 状态数: {len(ro_orbit.states)}", flush=True)

    system, dynamics = build_dynamics(
        integrator=INTEGRATOR,
        rtol=INTEGRATOR_RTOL,
        atol=INTEGRATOR_ATOL,
        max_step=DT,
        mu=MU,
    )
    print(f"\ne2m2e 动力学已就绪", flush=True)
    print(f"  系统: μ = {system.mu:.6e}", flush=True)
    print(f"  积分器: {dynamics.integrator}", flush=True)
    print(f"  rtol/atol: {dynamics.rtol:g} / {dynamics.atol:g}", flush=True)
    print(f"  max_step: {dynamics.max_step:.8f} TU", flush=True)

    pack_cfg = NlpPackConfig(
        mu=float(MU),
        alpha_min=float(ALPHA_MIN),
        alpha_max=float(ALPHA_MAX),
        earth_radius=float(EARTH_RADIUS),
        moon_radius=float(MOON_RADIUS),
        dt=float(DT),
        integrator=str(INTEGRATOR),
        integrator_rtol=float(INTEGRATOR_RTOL),
        integrator_atol=float(INTEGRATOR_ATOL),
        use_relaxed_velocity=bool(USE_RELAXED_VELOCITY),
        velocity_angle_tol=float(VELOCITY_ANGLE_TOL),
        use_copt=bool(USE_COPT),
        fallback_to_scipy=bool(FALLBACK_TO_SCIPY),
    )
    thread_nlp = ThreadNlpParams(
        alpha_min=float(ALPHA_MIN),
        alpha_max=float(ALPHA_MAX),
        earth_radius=float(EARTH_RADIUS),
        moon_radius=float(MOON_RADIUS),
        use_relaxed_velocity=bool(USE_RELAXED_VELOCITY),
        velocity_angle_tol=float(VELOCITY_ANGLE_TOL),
        use_copt=bool(USE_COPT),
        fallback_to_scipy=bool(FALLBACK_TO_SCIPY),
    )

    output_dir = project_root / "output/transfer"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"optimization_results_{timestampNow()}.json"

    backend = PARALLEL_BACKEND.strip().lower()
    if backend not in ("threads", "processes"):
        raise ValueError("PARALLEL_BACKEND 须为 'threads' 或 'processes'")

    cpu_n = multiprocessing.cpu_count() or 1
    if N_WORKERS is None:
        n_workers_req = max(1, cpu_n)
    else:
        n_workers_req = max(1, int(N_WORKERS))

    n_total = len(feasible_indexed)
    disable_tqdm = not USE_TQDM or n_total <= 0

    print("\n" + "=" * 70, flush=True)
    print("开始 NLP 优化", flush=True)
    print("=" * 70, flush=True)

    records: List[Dict[str, Any]] = []
    if n_workers_req == 1:
        global_progress = OptimizationProgress()
        global_progress.total_cases = n_total

        monitor = threading.Thread(
            target=monitor_loop_serial_nlp, args=(global_progress,), daemon=True
        )
        monitor.start()

        for k, (global_idx, rec) in enumerate(feasible_indexed):
            global_progress.start_case(k, n_total, global_idx)
            row = row_template(rec, global_idx)
            cb = make_progress_callback(global_progress, k, n_total, global_idx)
            try:
                res = optimize_one_case(
                    rec,
                    dro_orbit,
                    ro_orbit,
                    system,
                    dynamics,
                    verbose=False,
                    alpha_min=float(ALPHA_MIN),
                    alpha_max=float(ALPHA_MAX),
                    earth_radius=float(EARTH_RADIUS),
                    moon_radius=float(MOON_RADIUS),
                    use_relaxed_velocity=bool(USE_RELAXED_VELOCITY),
                    velocity_angle_tol=float(VELOCITY_ANGLE_TOL),
                    use_copt=bool(USE_COPT),
                    fallback_to_scipy=bool(FALLBACK_TO_SCIPY),
                    progress_callback=cb,
                )
                row["nlp"] = serialize_nlp_result(res)
                global_progress.finish_case(res.success, res.objective_value)
                snap = global_progress.get_snapshot()
                elapsed = (
                    time.perf_counter() - global_progress.start_time
                    if global_progress.start_time > 0
                    else 0
                )
                print(
                    f"  ✓ case {k + 1}/{n_total} done "
                    f"(search_idx={global_idx}) | "
                    f"iter={snap['iter']} | "
                    f"success={res.success} ΔV={res.objective_value:.6f} | "
                    f"elapsed={elapsed:.1f}s",
                    flush=True,
                )
            except Exception:
                row["error"] = traceback.format_exc()
                global_progress.finish_case(False, float("inf"))
                print(
                    f"  ✗ case {k + 1}/{n_total} ERROR (search_idx={global_idx}):\n"
                    f"  {row['error'][:500]}",
                    flush=True,
                )
            records.append(row)
    else:
        n_pool = min(n_workers_req, n_total)
        print(
            f"  并行执行: {n_pool} 个 worker（backend={backend}，本机逻辑 CPU={cpu_n}）",
            flush=True,
        )
        if backend == "processes":
            _bt = blas_threads_per_worker(default_limit=LIMIT_BLAS_THREADS_PER_WORKER)
            apply_blas_env_for_child_processes(_bt)
            print(
                f"  多进程 BLAS/OpenMP: 每 worker {_bt} 线程（环境已写入 OMP/MKL/OpenBLAS 等）",
                flush=True,
            )
        payloads = [(rec, idx) for idx, rec in feasible_indexed]
        futures_list: List[Any] = []

        if backend == "threads":
            with ThreadPoolExecutor(max_workers=n_pool) as ex:
                for rec, idx in payloads:
                    futures_list.append(
                        ex.submit(
                            worker_run_thread,
                            (rec, idx, dro_orbit, ro_orbit, system, dynamics, thread_nlp),
                        )
                    )
                for fut in tqdm(
                    as_completed(futures_list),
                    total=len(futures_list),
                    desc=f"NLP 优化(线程×{n_pool})",
                    unit="条",
                    file=sys.stderr,
                    dynamic_ncols=True,
                    mininterval=0.3,
                    disable=disable_tqdm,
                ):
                    records.append(fut.result())
        else:
            with ProcessPoolExecutor(max_workers=n_pool) as ex:
                for rec, idx in payloads:
                    futures_list.append(
                        ex.submit(
                            nlp_worker_packed,
                            pack_nlp_task(idx, rec, dro_orbit, ro_orbit, pack_cfg),
                        )
                    )
                for fut in tqdm(
                    as_completed(futures_list),
                    total=len(futures_list),
                    desc=f"NLP 优化(进程×{n_pool})",
                    unit="条",
                    file=sys.stderr,
                    dynamic_ncols=True,
                    mininterval=0.3,
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
                    "ro_file": str(RO_FILE),
                    "alpha_range": [ALPHA_MIN, ALPHA_MAX],
                    "nlp_solver": "copt_with_scipy_fallback" if USE_COPT else "scipy_slsqp",
                    "use_relaxed_velocity": USE_RELAXED_VELOCITY,
                    "n_optimized": len(records),
                    "parallel_backend": PARALLEL_BACKEND,
                    "n_workers_requested": N_WORKERS,
                    "integrator_rtol": INTEGRATOR_RTOL,
                    "integrator_atol": INTEGRATOR_ATOL,
                    "blas_threads_per_worker": blas_threads_per_worker(
                        default_limit=LIMIT_BLAS_THREADS_PER_WORKER,
                    )
                    if PARALLEL_BACKEND.strip().lower() == "processes"
                    else None,
                },
                "results": records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n优化完成，共写入 {len(records)} 条记录", flush=True)
    print(f"结果已保存到: {out_path}", flush=True)


if __name__ == "__main__":
    main()
