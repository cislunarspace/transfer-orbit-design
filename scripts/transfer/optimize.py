"""
DRO–RO 转移 NLP 优化（Cui et al. 2025，Section III.B）

在网格搜索（粗搜索）结果基础上，对变量 y = (α, T, t_ins) 求解
最小 Δv1+Δv2，满足位置连续与速度平行约束（Cui et al. 2025）。

**默认使用 SciPy ``minimize(..., method="SLSQP")``**（e2m2e ``DROTRONLPOptimizer.optimize``），
无需 COPT。若已安装 coptpy，可将 ``USE_COPT = True`` 尝试 Cardoso 系求解器。

使用前请保证本脚本中轨道 JSON、``MAX_TRANSFER_TIME``、α 范围等与
``grid_search.py`` 生成 ``search_results_*.json`` 时一致。

运行:
    python optimize.py

进度条使用 ``tqdm``（与 e2m2e 网格搜索一致，输出到 stderr）。关闭进度条: ``set OPTIMIZE_NO_TQDM=1``。

默认 ``PARALLEL_BACKEND="processes"``、``N_WORKERS=None``（逻辑 CPU 数），与 ``transfer_search`` 网格搜索
并行策略一致；子进程任务经 ``_nlp_worker_packed`` 打包数组，在子进程内重建 ``Orbit``/动力学，绕过 GIL。
多进程前会设置 ``OMP_NUM_THREADS`` 等，使每 worker 内 BLAS 为单线程，避免与进程数相乘导致抢核。

Windows 多进程需 ``if __name__ == "__main__"``，请勿删除末尾保护。
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fontTools.misc.timeTools import timestampNow
from tqdm.auto import tqdm

import e2m2e
from e2m2e.transfer import (
    DROTRONLPOptimizer,
    NLPOptimizationResult,
    NLPOptimizationVariables,
    load_orbit_from_json,
)

from scripts.utils.common import DU, MU, TU

project_root = Path(__file__).resolve().parent.parent.parent

# =============================================================================
# 参数配置（须与生成 search_results 的 grid_search 一致）
# =============================================================================

SEARCH_RESULTS_FILE = project_root / (
    "output/transfer/search_results_200-1001-0.5-2.5-2.299848_3857331829.json"
)
DRO_FILE = project_root / "output/dro/dro_31_3857117998.json"
RO_FILE = project_root / "output/ro/ro_31_3857122799.json"

ALPHA_MIN = 0.5
ALPHA_MAX = 2.5
# 与 grid_search 中 MAX_TRANSFER_TIME 一致（无量纲 TU）
MAX_TRANSFER_TIME = 200.0 / TU

# 碰撞半径（无量纲 DU），与 grid_search 一致
EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

DT = 1.0 / (24.0 * TU)
INTEGRATOR = "DOP853"

# 仅对网格中的可行解做 NLP；None 表示全部可行解
TOP_K_FEASIBLE: Optional[int] = None
# 调试时可设为较小整数
MAX_CASES: Optional[int] = None

# 并行度（与 grid_search 一致）：
#   None → 使用本机逻辑 CPU 数（os.cpu_count），尽量跑满；
#   1    → 强制串行（单线程单任务）；
#   正整数 → 最多同时运行的 worker 数（仍不超过待优化条数）。
N_WORKERS: Optional[int] = None

# 并行后端（与 e2m2e ``DROTransferSearch._parallel_backend`` 一致，默认 **processes**）：
#   "processes"— 多进程，独立解释器，真正并行占满 CPU（网格搜索默认即此，见 transfer_search 注释）；
#   "threads"  — 线程池，受 GIL 影响，CPU 密集 SciPy 时常跑不满，仅作调试或 I/O 场景。
PARALLEL_BACKEND: str = "processes"

# 多进程并行时，每个子进程内 BLAS/OpenMP 线程数（默认 1，避免与进程数相乘导致过度抢占）。
# 也可用环境变量 OPTIMIZE_BLAS_THREADS_PER_WORKER 覆盖本常量。
LIMIT_BLAS_THREADS_PER_WORKER: int = 1


def _blas_threads_per_worker() -> int:
    raw = os.environ.get("OPTIMIZE_BLAS_THREADS_PER_WORKER")
    if raw is not None and raw.strip() != "":
        return max(1, int(raw))
    return max(1, int(LIMIT_BLAS_THREADS_PER_WORKER))


def _apply_blas_env_for_child_processes(n_threads: int) -> None:
    """在创建 ProcessPoolExecutor 之前写入环境变量，spawn 子进程会继承，避免每进程 BLAS 再开多线程。"""
    s = str(max(1, int(n_threads)))
    for k in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[k] = s

# 命令行进度条（与 e2m2e 网格搜索一致，使用 tqdm）；设环境变量 OPTIMIZE_NO_TQDM=1 可关闭
USE_TQDM = os.environ.get("OPTIMIZE_NO_TQDM", "").lower() not in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# NLP 求解器：默认 SciPy SLSQP（不依赖 coptpy）
# ---------------------------------------------------------------------------
USE_COPT = False
# COPT 未收敛时是否回退 SciPy（仅当 USE_COPT 为 True 时有效）
FALLBACK_TO_SCIPY = True

# 等式速度约束不易收敛时可改为 True，并调节 VELOCITY_ANGLE_TOL（弧度）
USE_RELAXED_VELOCITY = False
VELOCITY_ANGLE_TOL = 0.05


def _load_search_results(path: Path) -> List[Dict[str, Any]]:
    """加载网格 JSON。支持 Python 扩展（NaN / Infinity），与 grid_search 写出格式一致。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _json_safe(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, dict):
        return {k: _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(i) for i in x]
    return x


def _serialize_nlp_result(r: NLPOptimizationResult) -> Dict[str, Any]:
    return _json_safe(
        {
            "success": r.success,
            "message": r.message,
            "alpha": r.alpha,
            "transfer_time": r.transfer_time,
            "t_ins": r.t_ins,
            "objective_value": r.objective_value,
            "delta_v1": r.delta_v1,
            "delta_v2": r.delta_v2,
            "transfer_type": r.transfer_type.value if r.transfer_type else None,
            "constraints_violation": r.constraints_violation,
            "departure_state": r.departure_state,
            "insertion_state": r.insertion_state,
            "final_state": r.final_state,
            "transfer_trajectory": r.transfer_trajectory,
            "transfer_times": r.transfer_times,
        }
    )


def _initial_guess_from_search(
    rec: Dict[str, Any], ro_orbit: Any
) -> NLPOptimizationVariables:
    """由网格结果构造 (α, T, t_ins) 初值。t_ins 取 RO 上最近点相位对应时刻。"""
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


def _t_ins_bounds(ro_orbit: Any) -> Tuple[float, float]:
    t0 = float(ro_orbit.times[0])
    per = float(ro_orbit.period)
    return (t0, t0 + per)


def _build_dynamics() -> Tuple[Any, Any]:
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = INTEGRATOR
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = DT
    return system, dynamics


def _optimize_one_case(
    rec: Dict[str, Any],
    dro_orbit: Any,
    ro_orbit: Any,
    system: Any,
    dynamics: Any,
    *,
    verbose: bool = False,
    alpha_min: float = ALPHA_MIN,
    alpha_max: float = ALPHA_MAX,
    max_transfer_time: float = MAX_TRANSFER_TIME,
    earth_radius: float = EARTH_RADIUS,
    moon_radius: float = MOON_RADIUS,
    use_relaxed_velocity: bool = USE_RELAXED_VELOCITY,
    velocity_angle_tol: float = VELOCITY_ANGLE_TOL,
    use_copt: bool = USE_COPT,
    fallback_to_scipy: bool = FALLBACK_TO_SCIPY,
) -> NLPOptimizationResult:
    """单条网格记录 → NLP。标量参数可传入，供子进程 ``packed`` worker 使用。"""
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

    t_lo, t_hi = _t_ins_bounds(ro_orbit)
    guess = _initial_guess_from_search(rec, ro_orbit)

    kwargs_opt: Dict[str, Any] = dict(
        initial_guess=guess,
        alpha_range=(alpha_min, alpha_max),
        transfer_time_range=(1e-4, max_transfer_time),
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


def _row_template(rec: Dict[str, Any], search_index: int) -> Dict[str, Any]:
    return {
        "search_index": search_index,
        "search_snapshot": {
            "alpha": rec.get("alpha"),
            "transfer_time": rec.get("transfer_time"),
            "min_distance": rec.get("min_distance"),
            "is_feasible": rec.get("is_feasible"),
            "status": rec.get("status"),
        },
        "error": None,
        "nlp": None,
    }


def _pack_nlp_task(
    search_index: int,
    rec: Dict[str, Any],
    dro_orbit: Any,
    ro_orbit: Any,
) -> Tuple[Any, ...]:
    """打包为可 pickle 元组，供子进程 ``_nlp_worker_packed`` 使用（与 transfer_search 的 packed worker 同构）。"""
    return (
        int(search_index),
        rec,
        np.asarray(dro_orbit.states, dtype=float),
        np.asarray(dro_orbit.times, dtype=float),
        float(dro_orbit.period),
        np.asarray(ro_orbit.states, dtype=float),
        np.asarray(ro_orbit.times, dtype=float),
        float(ro_orbit.period),
        float(MU),
        float(ALPHA_MIN),
        float(ALPHA_MAX),
        float(MAX_TRANSFER_TIME),
        float(EARTH_RADIUS),
        float(MOON_RADIUS),
        float(DT),
        str(INTEGRATOR),
        float(1e-12),
        float(1e-12),
        float(DT),
        bool(USE_RELAXED_VELOCITY),
        float(VELOCITY_ANGLE_TOL),
        bool(USE_COPT),
        bool(FALLBACK_TO_SCIPY),
    )


def _nlp_worker_packed(packed: Tuple[Any, ...]) -> Dict[str, Any]:
    """子进程入口：在子进程内重建 Orbit 与动力学，绕过 GIL；模块级函数便于 Windows spawn pickle。"""
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
        max_transfer_time,
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

    from e2m2e.core.orbit import Orbit

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

    out = _row_template(rec, int(search_index))
    try:
        result = _optimize_one_case(
            rec,
            dro_orbit,
            ro_orbit,
            system,
            dynamics,
            verbose=False,
            alpha_min=float(alpha_min),
            alpha_max=float(alpha_max),
            max_transfer_time=float(max_transfer_time),
            earth_radius=float(earth_radius),
            moon_radius=float(moon_radius),
            use_relaxed_velocity=bool(use_relaxed_velocity),
            velocity_angle_tol=float(velocity_angle_tol),
            use_copt=bool(use_copt),
            fallback_to_scipy=bool(fallback_to_scipy),
        )
        out["nlp"] = _serialize_nlp_result(result)
    except Exception:
        out["error"] = traceback.format_exc()
    return out


def _worker_run_thread(
    args: Tuple[Dict[str, Any], int, Any, Any, Any, Any],
) -> Dict[str, Any]:
    """线程池入口：共享主进程已加载的轨道与动力学。"""
    rec, search_index, dro, ro, system, dynamics = args
    out = _row_template(rec, search_index)
    try:
        result = _optimize_one_case(rec, dro, ro, system, dynamics, verbose=False)
        out["nlp"] = _serialize_nlp_result(result)
    except Exception:
        out["error"] = traceback.format_exc()
    return out


def main() -> None:
    print("=" * 70, flush=True)
    print("DRO–RO 转移 NLP 优化（Cui et al. 2025；e2m2e DROTRONLPOptimizer）", flush=True)
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
        f"  并行: n_workers={N_WORKERS}（None=逻辑 CPU 数 {_cpu}）, "
        f"backend={PARALLEL_BACKEND}",
        flush=True,
    )
    print(f"  TOP_K_FEASIBLE: {TOP_K_FEASIBLE}", flush=True)
    print(f"  MAX_CASES: {MAX_CASES}", flush=True)
    print(f"  α 范围: [{ALPHA_MIN:.2f}, {ALPHA_MAX:.2f}]", flush=True)
    print(f"  最大转移时间: {MAX_TRANSFER_TIME:.6f} TU", flush=True)
    print(f"  积分步长（1 小时）: {DT:.8f} TU", flush=True)
    print(f"  碰撞半径: 地球={EARTH_RADIUS:.4f}, 月球={MOON_RADIUS:.4f}", flush=True)
    print(f"  进度条: {'开启（tqdm）' if USE_TQDM else '关闭（OPTIMIZE_NO_TQDM）'}", flush=True)

    print(f"\n加载网格结果:", flush=True)
    print(f"  文件: {SEARCH_RESULTS_FILE}", flush=True)
    print("  正在读取 JSON（大文件可能较慢）…", flush=True)
    all_results = _load_search_results(SEARCH_RESULTS_FILE)
    total_records = len(all_results)
    feasible_indexed: List[Tuple[int, Dict[str, Any]]] = [
        (i, r) for i, r in enumerate(all_results) if r.get("is_feasible")
    ]

    feasible_indexed.sort(key=lambda ir: float(ir[1].get("min_distance", 1e9)))
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

        print(
            f"NLP: 优先 COPT（已安装: {_HAVE_COPT}），失败则 SciPy SLSQP",
            flush=True,
        )
    else:
        print(
            "NLP: SciPy SLSQP（scipy.optimize.minimize，与 e2m2e DROTRONLPOptimizer.optimize 一致）",
            flush=True,
        )

    if not feasible_indexed:
        print("\n没有可行解，退出。", flush=True)
        return

    print(f"\n加载轨道数据:", flush=True)
    print(f"  DRO: {DRO_FILE}", flush=True)
    print(f"  RO: {RO_FILE}", flush=True)
    dro_orbit = load_orbit_from_json(str(DRO_FILE))
    ro_orbit = load_orbit_from_json(str(RO_FILE))
    print(f"  DRO 周期: {dro_orbit.period:.4f} TU, 状态数: {len(dro_orbit.states)}", flush=True)
    print(f"  RO 周期: {ro_orbit.period:.4f} TU, 状态数: {len(ro_orbit.states)}", flush=True)

    system, dynamics = _build_dynamics()
    print(f"\ne2m2e 动力学已就绪", flush=True)
    print(f"  系统: μ = {system.mu:.6e}", flush=True)
    print(f"  积分器: {dynamics.integrator}", flush=True)
    print(f"  rtol/atol: {dynamics.rtol:g} / {dynamics.atol:g}", flush=True)
    print(f"  max_step: {dynamics.max_step:.8f} TU", flush=True)

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
        pbar = tqdm(
            feasible_indexed,
            total=n_total,
            desc="NLP 优化",
            unit="条",
            file=sys.stderr,
            dynamic_ncols=True,
            mininterval=0.3,
            disable=disable_tqdm,
        )
        for k, (global_idx, rec) in enumerate(pbar):
            row: Dict[str, Any] = {
                "search_index": global_idx,
                "search_snapshot": {
                    "alpha": rec.get("alpha"),
                    "transfer_time": rec.get("transfer_time"),
                    "min_distance": rec.get("min_distance"),
                    "is_feasible": rec.get("is_feasible"),
                    "status": rec.get("status"),
                },
                "error": None,
                "nlp": None,
            }
            try:
                res = _optimize_one_case(
                    rec, dro_orbit, ro_orbit, system, dynamics, verbose=False
                )
                row["nlp"] = _serialize_nlp_result(res)
                if disable_tqdm:
                    pct = (k + 1) / n_total * 100
                    print(
                        f"  NLP 进度: {k + 1}/{n_total} ({pct:.1f}%)  "
                        f"idx={global_idx} success={res.success} ΔV={res.objective_value:.6f}",
                        flush=True,
                    )
                else:
                    pbar.set_postfix(
                        idx=global_idx,
                        alpha=f"{float(rec.get('alpha', 0.0)):.4f}",
                        ok=res.success,
                        dV=f"{res.objective_value:.4f}",
                        refresh=False,
                    )
            except Exception:
                row["error"] = traceback.format_exc()
                if disable_tqdm:
                    print(
                        f"  NLP 进度: {k + 1}/{n_total}  idx={global_idx} ERROR",
                        flush=True,
                    )
                else:
                    tqdm.write(
                        f"  [错误] idx={global_idx}:\n{row['error'][:2000]}",
                    )
                    pbar.set_postfix(
                        idx=global_idx,
                        err="ERR",
                        refresh=False,
                    )
            records.append(row)
    else:
        n_pool = min(n_workers_req, n_total)
        print(
            f"  并行执行: {n_pool} 个 worker（backend={backend}，本机逻辑 CPU={cpu_n}）",
            flush=True,
        )
        if backend == "processes":
            _bt = _blas_threads_per_worker()
            _apply_blas_env_for_child_processes(_bt)
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
                            _worker_run_thread,
                            (
                                rec,
                                idx,
                                dro_orbit,
                                ro_orbit,
                                system,
                                dynamics,
                            ),
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
                        ex.submit(_nlp_worker_packed, _pack_nlp_task(idx, rec, dro_orbit, ro_orbit))
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
                    "max_transfer_time": MAX_TRANSFER_TIME,
                    "nlp_solver": (
                        "copt_with_scipy_fallback"
                        if USE_COPT
                        else "scipy_slsqp"
                    ),
                    "use_relaxed_velocity": USE_RELAXED_VELOCITY,
                    "n_optimized": len(records),
                    "parallel_backend": PARALLEL_BACKEND,
                    "n_workers_requested": N_WORKERS,
                    "blas_threads_per_worker": _blas_threads_per_worker()
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
