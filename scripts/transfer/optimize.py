"""
DRO–RO 转移 NLP（Cui et al. 2025）：在网格搜索结果上对 y=(α,T,t_ins) 最小化 Δv，默认 SciPy SLSQP（``DROTRONLPOptimizer``）。

须与 ``grid_search.py`` 生成 ``search_results`` 时一致：轨道 JSON、``MAX_TRANSFER_TIME``、α 范围、碰撞半径等。

运行: ``python optimize.py``。进度条: ``tqdm``；关闭: ``OPTIMIZE_NO_TQDM=1``。

并行: 默认 ``PARALLEL_BACKEND="processes"``、``N_WORKERS=None``；子进程经 ``_nlp_worker_packed`` 重建轨道，绕过 GIL。
多进程创建前会限制每 worker 的 BLAS 线程（``LIMIT_BLAS_THREADS_PER_WORKER`` / ``OPTIMIZE_BLAS_THREADS_PER_WORKER``）。

CPU 跑不满时: 提高待优化条数（本文件 ``TOP_K_FEASIBLE`` / ``MAX_CASES`` / ``DEBUG_DEPARTURE_POINT``）或 ``N_WORKERS``；
用 ``processes`` 而非 ``threads``；并发数 ``≤ min(N_WORKERS, 条数)``；单进程跑满核可增大 BLAS 线程；积分可放宽 ``INTEGRATOR_RTOL/ATOL``。

Windows 须保留末尾 ``if __name__ == "__main__"``。
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
import multiprocessing
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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

# --- 须与 grid_search 生成 search_results 时一致 ---
SEARCH_RESULTS_FILE = project_root / (
    "output/transfer/search_results_200-1001-0.5-2.5-22.998482_3857379210.json"
)
DRO_FILE = project_root / "output/dro/dro_31_3857199098.json"
RO_FILE = project_root / "output/ro/ro_31_3857328571.json"

ALPHA_MIN = 0.5
ALPHA_MAX = 2.5
MAX_TRANSFER_TIME = 100.0 / TU  # 与 grid_search 一致（无量纲 TU）

# 与 grid_search 的 collision_earth/moon_radius 一致（到中心距离判碰撞，见 e2m2e DROTransferSearch / NLP）
EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

DT = 1.0 / (24.0 * TU)
INTEGRATOR = "DOP853"
INTEGRATOR_RTOL = 1e-12  # 与 _pack_nlp_task 一致；放宽可加速
INTEGRATOR_ATOL = 1e-12

TOP_K_FEASIBLE: Optional[int] = None  # 排序后取前 K 条；None=全部
MAX_CASES: Optional[int] = None  # 在 TOP_K 之后再截断；None=不限制

N_WORKERS: Optional[int] = None  # None→cpu_count；1→串行
PARALLEL_BACKEND: str = "processes"  # processes 推荐；threads 受 GIL 影响大

LIMIT_BLAS_THREADS_PER_WORKER: int = 1  # 每子进程 BLAS 线程；环境变量 OPTIMIZE_BLAS_THREADS_PER_WORKER 可覆盖


def _blas_threads_per_worker() -> int:
    """读取每 worker 的 BLAS 线程数：环境变量优先，否则用 ``LIMIT_BLAS_THREADS_PER_WORKER``。"""
    raw = os.environ.get("OPTIMIZE_BLAS_THREADS_PER_WORKER")
    if raw is not None and raw.strip() != "":
        return max(1, int(raw))
    return max(1, int(LIMIT_BLAS_THREADS_PER_WORKER))


def _apply_blas_env_for_child_processes(n_threads: int) -> None:
    """ProcessPool 创建前设置 OMP/MKL 等，子进程继承。"""
    s = str(max(1, int(n_threads)))
    for k in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[k] = s


USE_TQDM = os.environ.get("OPTIMIZE_NO_TQDM", "").lower() not in ("1", "true", "yes")

USE_COPT = False
FALLBACK_TO_SCIPY = True  # USE_COPT 时是否回退 SciPy

USE_RELAXED_VELOCITY = True  # e2m2e use_relaxed_velocity_constraint；不等式形式需改 e2m2e
VELOCITY_ANGLE_TOL = 0.05

DEBUG_DEPARTURE_POINT: Optional[Tuple[float, float, float]] = None  # 非 None 时只跑匹配 (x,y,z) 的可行解；值从 search_results 的 departure_state 抄


class OptimizationProgress:
    """串行模式：callback 与监控线程共享的进度。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.case_index: int = -1
        self.total_cases: int = 0
        self.search_index: int = -1  # 对应网格 JSON 下标
        self.iteration: int = 0
        self.objective: float = float("inf")
        self.alpha: float = 0.0
        self.transfer_time: float = 0.0
        self.t_ins: float = 0.0
        self.start_time: float = 0.0
        self.case_start_time: float = 0.0
        self.last_success: bool = False
        self.last_delta_v: float = float("inf")
        self.last_duration: float = 0.0

    def start_case(self, case_idx: int, total: int, search_idx: int) -> None:
        """进入第 ``case_idx`` 条（共 ``total`` 条），对应原始网格下标 ``search_idx``。"""
        with self._lock:
            if self.start_time <= 0:
                self.start_time = _wall_time()  # 整条批任务开始时刻
            self.case_index = case_idx
            self.total_cases = total
            self.search_index = search_idx
            self.iteration = 0
            self.objective = float("inf")
            self.alpha = 0.0
            self.transfer_time = 0.0
            self.t_ins = 0.0
            self.case_start_time = _wall_time()

    def update_iteration(self, it: int, obj: float, a: float, T: float, tins: float) -> None:
        """由 SLSQP 回调更新当前迭代的序号、目标与变量猜测。"""
        with self._lock:
            self.iteration = it
            self.objective = obj
            self.alpha = a
            self.transfer_time = T
            self.t_ins = tins

    def finish_case(self, success: bool, delta_v: float) -> None:
        """本条 NLP 结束：记录是否成功与 ΔV，并统计耗时。"""
        with self._lock:
            self.last_success = success
            self.last_delta_v = delta_v
            self.last_duration = _wall_time() - self.case_start_time

    def get_snapshot(self) -> dict:
        """供监控线程读取当前进度（线程安全拷贝）。"""
        with self._lock:
            return dict(
                case=self.case_index,
                total=self.total_cases,
                search_index=self.search_index,
                iter=self.iteration,
                obj=self.objective,
                alpha=self.alpha,
                T=self.transfer_time,
                tins=self.t_ins,
                duration=self.last_duration,
                last_success=self.last_success,
                last_delta_v=self.last_delta_v,
            )


def _wall_time() -> float:
    """墙钟秒数（与 ``time.time()`` 一致）。"""
    return time.time()


_progress: Optional[OptimizationProgress] = None  # 预留；当前进度由 main 内 local ``global_progress`` 持有


def _make_progress_callback(prog: OptimizationProgress, case_idx: int, total: int, search_idx: int):
    """返回写入 OptimizationProgress 的 SLSQP 回调（若 e2m2e 支持）。"""

    def callback(it: int, obj: float, a: float, T: float, tins: float) -> None:
        """由优化器在每次迭代调用（iter, 目标值, α, T, t_ins）。"""
        prog.update_iteration(it, obj, a, T, tins)

    return callback


def _load_search_results(path: Path) -> List[Dict[str, Any]]:
    """加载网格 JSON。支持 Python 扩展（NaN / Infinity），与 grid_search 写出格式一致。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _json_safe(x: Any) -> Any:
    """将 numpy 标量/数组及嵌套结构转为可 ``json.dump`` 的 Python 原生类型。"""
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
    """把 ``NLPOptimizationResult`` 打成可写入结果 JSON 的 dict。"""
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


def _match_departure_point(rec: Dict[str, Any], x: float, y: float, z: float, tol: float = 1e-4) -> bool:
    """判断搜索结果 rec 的出发点是否与指定 (x, y, z) 匹配（容差 tol）。"""
    dep_state = rec.get("departure_state")
    if dep_state is None:
        return False
    return (abs(dep_state[0] - x) < tol and
            abs(dep_state[1] - y) < tol and
            abs(dep_state[2] - z) < tol)


def _initial_guess_from_search(
    rec: Dict[str, Any], ro_orbit: Any
) -> NLPOptimizationVariables:
    """由网格结果构造 (α, T, t_ins) 初值。α、T 来自粗搜；t_ins 优先用 ``min_distance_orbit_idx`` 在 RO 时间轴上的时刻，否则取半周期。"""
    alpha = float(rec["alpha"])
    transfer_time = float(rec["transfer_time"])
    idx = rec.get("min_distance_orbit_idx")
    t0 = float(ro_orbit.times[0])
    per = float(ro_orbit.period)
    if idx is not None:
        i = int(idx) % len(ro_orbit.times)  # 与网格离散索引对齐
        t_ins = float(ro_orbit.times[i])
    else:
        t_ins = t0 + 0.5 * per  # 无索引时取 RO 中段相位
    return NLPOptimizationVariables(
        alpha=alpha, transfer_time=transfer_time, t_ins=t_ins
    )


def _t_ins_bounds(ro_orbit: Any) -> Tuple[float, float]:
    """插入时刻 t_ins 的搜索区间：一个 RO 周期 ``[t0, t0+period]``。"""
    t0 = float(ro_orbit.times[0])
    per = float(ro_orbit.period)
    return (t0, t0 + per)


def _build_dynamics() -> Tuple[Any, Any]:
    """构造地月 CR3BP 系统与动力学；积分器与容差与 ``_pack_nlp_task`` 中常量保持一致。"""
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = INTEGRATOR
    dynamics.rtol = INTEGRATOR_RTOL
    dynamics.atol = INTEGRATOR_ATOL
    dynamics.max_step = DT  # 与网格输出步长一致，控制积分输出密度
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
    progress_callback: Optional[Callable] = None,
) -> NLPOptimizationResult:
    """对单条网格可行解做 NLP。参数可覆盖模块常量，供子进程 ``_nlp_worker_packed`` 传入。"""
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

    if progress_callback is not None and hasattr(opt, "set_progress_callback"):
        opt.set_progress_callback(progress_callback)

    kwargs_opt: Dict[str, Any] = dict(
        initial_guess=guess,
        alpha_range=(alpha_min, alpha_max),
        transfer_time_range=(1e-4, max_transfer_time),  # 下界略大于 0 避免除零
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
    """单条结果记录骨架：网格下标、粗搜快照、错误与 NLP 占位。"""
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
    """打包为可 pickle 元组，供 ``_nlp_worker_packed`` 在子进程重建轨道与动力学。

    顺序为：search_index、rec、DRO 状态/时间/周期、RO 状态/时间/周期、μ、α 与 T 范围、
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
        float(MU),
        float(ALPHA_MIN),
        float(ALPHA_MAX),
        float(MAX_TRANSFER_TIME),
        float(EARTH_RADIUS),
        float(MOON_RADIUS),
        float(DT),  # _nlp_worker_packed 中 _dt_unused，与 pack 历史字段对齐
        str(INTEGRATOR),
        float(INTEGRATOR_RTOL),
        float(INTEGRATOR_ATOL),
        float(DT),  # max_step，与主进程 dynamics.max_step 一致
        bool(USE_RELAXED_VELOCITY),
        float(VELOCITY_ANGLE_TOL),
        bool(USE_COPT),
        bool(FALLBACK_TO_SCIPY),
    )


def _nlp_worker_packed(packed: Tuple[Any, ...]) -> Dict[str, Any]:
    """子进程入口：解包 ``_pack_nlp_task`` 元组，重建 ``Orbit``/动力学后调用 ``_optimize_one_case``。

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
        out["error"] = traceback.format_exc()  # 子进程内异常写入文本，便于主进程落盘
    return out


def _worker_run_thread(
    args: Tuple[Dict[str, Any], int, Any, Any, Any, Any],
) -> Dict[str, Any]:
    """线程池入口：共享主进程已加载的轨道与动力学（无 pickle 大数组）。"""
    rec, search_index, dro, ro, system, dynamics = args
    out = _row_template(rec, search_index)
    try:
        result = _optimize_one_case(rec, dro, ro, system, dynamics, verbose=False)
        out["nlp"] = _serialize_nlp_result(result)
    except Exception:
        out["error"] = traceback.format_exc()  # 与多进程分支一致，保留栈信息
    return out


def main() -> None:
    """加载网格与轨道、筛选可行解、按并行设置跑 NLP，并写出 ``optimization_results_*.json``。"""
    print("=" * 70, flush=True)
    print("DRO–RO 转移 NLP 优化（Cui et al. 2025；e2m2e DROTRONLPOptimizer）", flush=True)
    print("=" * 70, flush=True)

    # --- 输入文件存在性 ---
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

    # --- 读取网格 JSON，筛可行解、排序、TOP_K / MAX_CASES / 固定出发点 ---
    print(f"\n加载网格结果:", flush=True)
    print(f"  文件: {SEARCH_RESULTS_FILE}", flush=True)
    print("  正在读取 JSON（大文件可能较慢）…", flush=True)
    all_results = _load_search_results(SEARCH_RESULTS_FILE)
    total_records = len(all_results)
    feasible_indexed: List[Tuple[int, Dict[str, Any]]] = [
        (i, r) for i, r in enumerate(all_results) if r.get("is_feasible")
    ]

    feasible_indexed.sort(key=lambda ir: float(ir[1].get("min_distance", 1e9)))  # 升序；TOP_K 取 min_distance 最小的 K 条

    if DEBUG_DEPARTURE_POINT is not None:
        dx, dy, dz = DEBUG_DEPARTURE_POINT
        feasible_indexed = [
            (i, r) for i, r in feasible_indexed
            if _match_departure_point(r, dx, dy, dz)
        ]
        print(
            f"  [调试] 固定出发点 {DEBUG_DEPARTURE_POINT}，筛选后可行解: {len(feasible_indexed)}",
            flush=True,
        )

    n_feasible_total = len(feasible_indexed)
    if TOP_K_FEASIBLE is not None:
        feasible_indexed = feasible_indexed[:TOP_K_FEASIBLE]
    if MAX_CASES is not None:
        feasible_indexed = feasible_indexed[:MAX_CASES]

    del all_results  # 释放整表，降内存峰值

    print(f"\n网格记录总数: {total_records}", flush=True)
    print(f"可行解总数: {n_feasible_total}", flush=True)
    print(f"本次待优化（经 TOP_K / MAX_CASES 截断后）: {len(feasible_indexed)}", flush=True)
    if USE_COPT:
        from e2m2e.transfer import _HAVE_COPT

        print(
            f"NLP: COPT（已安装: {_HAVE_COPT}），失败则 SciPy SLSQP",
            flush=True,
        )
    else:
        print("NLP: SciPy SLSQP（scipy.optimize.minimize）", flush=True)

    if not feasible_indexed:
        print("\n没有可行解，退出。", flush=True)
        return

    # --- DRO/RO 轨道与 JSON 周期覆盖；主进程动力学 ---
    print(f"\n加载轨道数据:", flush=True)
    dro_orbit = load_orbit_from_json(str(DRO_FILE))
    ro_orbit = load_orbit_from_json(str(RO_FILE))
    print(f"  DRO: {DRO_FILE}", flush=True)
    print(f"  RO: {RO_FILE}", flush=True)

    with open(RO_FILE, encoding="utf-8") as f:
        ro_json = json.load(f)
    if "properties" in ro_json and "period" in ro_json["properties"]:
        ro_orbit.period = float(ro_json["properties"]["period"])  # 覆盖 load 估计周期

    print(f"  DRO 周期: {dro_orbit.period:.4f} TU, 状态数: {len(dro_orbit.states)}", flush=True)
    print(f"  RO 周期: {ro_orbit.period:.4f} TU, 状态数: {len(ro_orbit.states)}", flush=True)

    system, dynamics = _build_dynamics()
    print(f"\ne2m2e 动力学已就绪", flush=True)
    print(f"  系统: μ = {system.mu:.6e}", flush=True)
    print(f"  积分器: {dynamics.integrator}", flush=True)
    print(f"  rtol/atol: {dynamics.rtol:g} / {dynamics.atol:g}", flush=True)
    print(f"  max_step: {dynamics.max_step:.8f} TU", flush=True)

    # --- 输出路径与并行参数（worker 数、BLAS 环境）---
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
    # --- 串行：可挂 SLSQP 迭代回调与监控线程 ---
    if n_workers_req == 1:
        global_progress = OptimizationProgress()
        global_progress.total_cases = n_total

        def _monitor_loop(prog: OptimizationProgress, interval: float = 2.0) -> None:
            """后台周期性打印当前 case 与迭代信息；最后一条开始后若已有迭代则退出。"""
            while True:
                time.sleep(interval)
                snap = prog.get_snapshot()
                total_elapsed = _wall_time() - prog.start_time if prog.start_time > 0 else 0
                if snap["total"] > 0 and snap["case"] >= 0:
                    print(
                        f"  ▶ case {snap['case']+1}/{snap['total']} "
                        f"(search_idx={snap['search_index']}) | "
                        f"iter={snap['iter']:4d} | "
                        f"α={snap['alpha']:.4f} T={snap['T']:.4f} tins={snap['tins']:.4f} | "
                        f"obj={snap['obj']:.6f} | "
                        f"elapsed={total_elapsed:.0f}s",
                        flush=True,
                    )
                    # 已是最后一条且出现过迭代，认为监控可结束（避免无限 sleep）
                    if snap["case"] >= snap["total"] - 1 and snap["iter"] > 0:
                        break

        monitor = threading.Thread(target=_monitor_loop, args=(global_progress,), daemon=True)
        monitor.start()

        for k, (global_idx, rec) in enumerate(feasible_indexed):
            global_progress.start_case(k, n_total, global_idx)
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
            cb = _make_progress_callback(global_progress, k, n_total, global_idx)
            try:
                res = _optimize_one_case(
                    rec, dro_orbit, ro_orbit, system, dynamics,
                    verbose=False, progress_callback=cb,
                )
                row["nlp"] = _serialize_nlp_result(res)
                global_progress.finish_case(res.success, res.objective_value)
                snap = global_progress.get_snapshot()
                elapsed = _wall_time() - global_progress.start_time if global_progress.start_time > 0 else 0
                print(
                    f"  ✓ case {k+1}/{n_total} done "
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
                    f"  ✗ case {k+1}/{n_total} ERROR (search_idx={global_idx}):\n"
                    f"  {row['error'][:500]}",
                    flush=True,
                )
            records.append(row)
    else:
        # --- 多 worker：线程或进程池 + tqdm；进程模式先限 BLAS ---
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
                        ex.submit(
                            _nlp_worker_packed,
                            _pack_nlp_task(idx, rec, dro_orbit, ro_orbit),
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
        # as_completed 完成顺序与提交顺序无关，按 search_index 排序再写 JSON
        records.sort(key=lambda x: x.get("search_index", 0))

    # --- 写出结果 JSON（meta + results）---
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
                    "integrator_rtol": INTEGRATOR_RTOL,
                    "integrator_atol": INTEGRATOR_ATOL,
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
