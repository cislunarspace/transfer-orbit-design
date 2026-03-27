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

**CPU 利用率偏低时请先检查：**

- ``N_WORKERS=1`` 或 ``len(可行解)==1`` 时本质单任务串行，无法占满多核；放宽 ``DEBUG_DEPARTURE_POINT`` /
  环境变量筛选或把 ``N_WORKERS`` 设为 ``None``。
- ``PARALLEL_BACKEND="threads"`` 对 SciPy/积分等 CPU 密集代码帮助很小，请用 ``processes``。
- 实际并发数为 ``min(N_WORKERS, 待优化条数)``；待优化条数过少时 worker 数再多也不会增加并行度。
- 多进程下单进程 BLAS 默认 1 线程；若**强制单进程**跑大量 case，可提高 ``OPTIMIZE_BLAS_THREADS_PER_WORKER``
  或相应 ``OMP_NUM_THREADS``，让单进程内线性代数多线程（与多进程二选一或折中，需实测）。
- 积分容差 ``INTEGRATOR_RTOL`` / ``INTEGRATOR_ATOL`` 过紧会显著增加耗时，可先放宽做试探再收紧。

``N_WORKERS`` 解析为 1 时走主进程顺序循环，可使用 ``progress_callback`` 打印迭代；多 worker 时子进程无该回调。

Windows 多进程需 ``if __name__ == "__main__"``，请勿删除末尾保护。
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

# =============================================================================
# 参数配置（须与生成 search_results 的 grid_search 一致）
# =============================================================================

SEARCH_RESULTS_FILE = project_root / (
    "output/transfer/search_results_200-1001-0.5-2.5-22.998482_3857379210.json"
)
DRO_FILE = project_root / "output/dro/dro_31_3857199098.json"
RO_FILE = project_root / "output/ro/ro_31_3857328571.json"

ALPHA_MIN = 0.5
ALPHA_MAX = 2.5
# 与 grid_search 中 MAX_TRANSFER_TIME 一致（无量纲 TU，100/TU ≈ 23 天）
MAX_TRANSFER_TIME = 100.0 / TU

# 撞星约束半径（无量纲，与地月距离 DU 的比值）：须与 grid_search.py 中
# ``collision_earth_radius`` / ``collision_moon_radius`` 一致，使粗搜可行解与 NLP 约束同一套几何。
# 含义：轨迹点到地球/月球中心距离小于该阈值则判碰撞（见 e2m2e ``DROTransferSearch`` / ``DROTRONLPOptimizer``）。
EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

DT = 1.0 / (24.0 * TU)
INTEGRATOR = "DOP853"
# 与 grid_search 及子进程 ``_nlp_worker_packed`` 共用；放宽可明显加速，终算或与文献对比时可收紧。
INTEGRATOR_RTOL = 1e-12
INTEGRATOR_ATOL = 1e-12

# 仅对网格中的可行解做 NLP：在按 min_distance 排序后只取前 K 条（None = 全部）。
TOP_K_FEASIBLE: Optional[int] = None
# 在上述截断之后再限制条数，便于调试或小规模试跑（None = 不额外限制）。
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

# 多进程并行时，每个子进程内 OpenBLAS/MKL 等 BLAS 使用的线程数（默认 1）。
# 若设为 N 且进程数为 P，最坏会占满约 P×N 个逻辑 CPU，故默认 1；可用环境变量
# OPTIMIZE_BLAS_THREADS_PER_WORKER 覆盖。
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


def _resolve_debug_departure_point() -> Optional[Tuple[float, float, float]]:
    """环境变量 OPTIMIZE_DEBUG_DEPARTURE 优先于模块常量 DEBUG_DEPARTURE_POINT。"""
    raw = os.environ.get("OPTIMIZE_DEBUG_DEPARTURE", "").strip()
    if not raw:
        return DEBUG_DEPARTURE_POINT
    parts = [p for p in raw.replace(",", " ").split() if p]
    if len(parts) != 3:
        raise ValueError(
            "OPTIMIZE_DEBUG_DEPARTURE 须为三个数，例如 1.093772,-0.089809,0.0"
        )
    return (float(parts[0]), float(parts[1]), float(parts[2]))


# 命令行进度条（与 e2m2e 网格搜索一致，使用 tqdm）；设环境变量 OPTIMIZE_NO_TQDM=1 可关闭
USE_TQDM = os.environ.get("OPTIMIZE_NO_TQDM", "").lower() not in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# NLP 求解器：默认 SciPy SLSQP（不依赖 coptpy）
# ---------------------------------------------------------------------------
USE_COPT = False
# COPT 未收敛时是否回退 SciPy（仅当 USE_COPT 为 True 时有效）
FALLBACK_TO_SCIPY = True

# True 时走 e2m2e ``use_relaxed_velocity_constraint``：用角度容差松弛「速度平行」等式，便于 SLSQP 收敛。
# 若需改为真正的「不等式约束」表述，须在 e2m2e ``transfer_optimization.py`` 内改约束形式，而非仅改此处。
USE_RELAXED_VELOCITY = True
VELOCITY_ANGLE_TOL = 0.05

# ---------------------------------------------------------------------------
# 调试配置
# ---------------------------------------------------------------------------
# 固定出发点：仅优化 departure_state 位置 (x,y,z) 与该三元组匹配的可行解；None = 不筛选。
# 调试值请从 ``search_results_*.json`` 某条记录的 ``departure_state`` 前三项复制，或设置环境变量
# OPTIMIZE_DEBUG_DEPARTURE="x,y,z"（逗号或空格分隔，覆盖本常量）。
DEBUG_DEPARTURE_POINT: Optional[Tuple[float, float, float]] = None

# ---------------------------------------------------------------------------
# 进度追踪（供优化迭代回调和监控线程共享）
# ---------------------------------------------------------------------------


class OptimizationProgress:
    """线程安全的优化进度状态，供 callback 和监控线程共享。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.case_index: int = -1      # 当前是第几条（0起）
        self.total_cases: int = 0      # 总共多少条
        self.search_index: int = -1     # 当前对应的 search_index
        self.iteration: int = 0        # 当前条 SLSQP 迭代数
        self.objective: float = float("inf")
        self.alpha: float = 0.0
        self.transfer_time: float = 0.0
        self.t_ins: float = 0.0
        self.start_time: float = 0.0   # 本条开始时间（墙钟）
        self.case_start_time: float = 0.0  # 本条开始时间
        # 上一条完成信息
        self.last_success: bool = False
        self.last_delta_v: float = float("inf")
        self.last_duration: float = 0.0  # 本条耗时（秒）

    def start_case(self, case_idx: int, total: int, search_idx: int) -> None:
        with self._lock:
            if self.start_time <= 0:
                self.start_time = _wall_time()
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
        with self._lock:
            self.iteration = it
            self.objective = obj
            self.alpha = a
            self.transfer_time = T
            self.t_ins = tins

    def finish_case(self, success: bool, delta_v: float) -> None:
        with self._lock:
            self.last_success = success
            self.last_delta_v = delta_v
            self.last_duration = _wall_time() - self.case_start_time

    def get_snapshot(self) -> dict:
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
    return time.time()


_progress: Optional[OptimizationProgress] = None


def _make_progress_callback(prog: OptimizationProgress, case_idx: int, total: int, search_idx: int):
    """创建当前案例的迭代回调函数。"""

    def callback(it: int, obj: float, a: float, T: float, tins: float) -> None:
        prog.update_iteration(it, obj, a, T, tins)

    return callback


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
    dynamics.rtol = INTEGRATOR_RTOL
    dynamics.atol = INTEGRATOR_ATOL
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
    progress_callback: Optional[Callable] = None,
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

    if progress_callback is not None:
        opt.set_progress_callback(progress_callback)

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
        float(INTEGRATOR_RTOL),
        float(INTEGRATOR_ATOL),
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

    # 按网格记录的 min_distance 升序：优先优化与目标轨道距离更大（通常更安全）的可行解。
    feasible_indexed.sort(key=lambda ir: float(ir[1].get("min_distance", 1e9)))

    debug_pt = _resolve_debug_departure_point()
    if debug_pt is not None:
        dx, dy, dz = debug_pt
        feasible_indexed = [
            (i, r) for i, r in feasible_indexed
            if _match_departure_point(r, dx, dy, dz)
        ]
        print(f"  [调试] 固定出发点 {debug_pt}，筛选后可行解: {len(feasible_indexed)}", flush=True)

    n_feasible_total = len(feasible_indexed)
    # 先取「质量最好」的前 TOP_K 条，再按 MAX_CASES 截断（两者可同时生效）。
    if TOP_K_FEASIBLE is not None:
        feasible_indexed = feasible_indexed[:TOP_K_FEASIBLE]
    if MAX_CASES is not None:
        feasible_indexed = feasible_indexed[:MAX_CASES]

    # 可行解列表已构建完毕，释放整表 JSON 以减小峰值内存。
    del all_results

    print(f"\n网格记录总数: {total_records}", flush=True)
    print(f"可行解总数: {n_feasible_total}", flush=True)
    print(f"本次待优化（经 TOP_K / MAX_CASES 截断后）: {len(feasible_indexed)}", flush=True)
    if USE_COPT:
        from e2m2e.transfer import _HAVE_COPT

        print(
            f"NLP 求解器: COPT（商业整数规划求解器，已安装: {_HAVE_COPT}），若收敛失败则回退到 SciPy SLSQP",
            flush=True,
        )
    else:
        print(
            "NLP 求解器: SciPy SLSQP（序列最小二乘规划算法，用于求解非线性约束优化问题）",
            flush=True,
        )

    if not feasible_indexed:
        print("\n没有可行解，退出。", flush=True)
        return

    print(f"\n加载轨道数据:", flush=True)
    dro_orbit = load_orbit_from_json(str(DRO_FILE))
    ro_orbit = load_orbit_from_json(str(RO_FILE))
    print(f"  DRO: {DRO_FILE}", flush=True)
    print(f"  RO: {RO_FILE}", flush=True)

    # ``load_orbit_from_json`` 内对周期可能用采样估计；若 JSON 含 ``properties.period``，用其覆盖为标称周期。
    with open(RO_FILE, encoding="utf-8") as f:
        ro_json = json.load(f)
    if "properties" in ro_json and "period" in ro_json["properties"]:
        ro_orbit.period = float(ro_json["properties"]["period"])

    print(f"  DRO 周期: {dro_orbit.period:.4f} TU, 状态数: {len(dro_orbit.states)}", flush=True)
    print(f"  RO 周期: {ro_orbit.period:.4f} TU, 状态数: {len(ro_orbit.states)}", flush=True)

    system, dynamics = _build_dynamics()
    print(f"\ne2m2e 动力学已就绪", flush=True)
    print(f"  系统: μ = {system.mu:.6e}", flush=True)
    print(f"  积分器: {dynamics.integrator}", flush=True)
    print(
        f"  rtol/atol: {dynamics.rtol:g} / {dynamics.atol:g} "
        f"（可调常量 INTEGRATOR_RTOL/ATOL；放宽通常显著加速）",
        flush=True,
    )
    print(f"  max_step: {dynamics.max_step:.8f} TU", flush=True)

    output_dir = project_root / "output/transfer"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"optimization_results_{timestampNow()}.json"

    # 解析并行后端与 worker 数（多进程见下文的 BLAS 环境写入）。
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
    # 单 worker：主进程顺序执行每条 case，可使用 SLSQP 迭代回调；无多 case 并行。
    if n_workers_req == 1:
        # 进度状态对象（跨案例共享；start_time 由 start_case 首次调用时初始化）
        global_progress = OptimizationProgress()
        global_progress.total_cases = n_total

        # 定期打印详细进度的监控线程
        def _monitor_loop(prog: OptimizationProgress, interval: float = 2.0) -> None:
            while True:
                time.sleep(interval)
                snap = prog.get_snapshot()
                # 算总耗时（从第一条开始计时）
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
                    # 所有案例都完成则退出
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
            # 本案例的回调：每 SLSQP 迭代触发
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
        # 多 worker：线程池共享主进程轨道/动力学；进程池在子进程内重建对象，真正并行 CPU。
        n_pool = min(n_workers_req, n_total)
        print(
            f"  并行执行: {n_pool} 个 worker（backend={backend}，本机逻辑 CPU={cpu_n}）",
            flush=True,
        )
        if backend == "processes":
            # 在创建进程池前写入 OMP/MKL 等，使子进程继承，限制每进程 BLAS 线程数。
            _bt = _blas_threads_per_worker()
            _apply_blas_env_for_child_processes(_bt)
            print(
                f"  多进程 BLAS/OpenMP: 每 worker {_bt} 线程（环境已写入 OMP/MKL/OpenBLAS 等）",
                flush=True,
            )
        # (rec, search_index) 与 feasible_indexed 中项一致。
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
                # as_completed：任一子进程完成即返回对应 future；顺序与提交顺序无关。
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
