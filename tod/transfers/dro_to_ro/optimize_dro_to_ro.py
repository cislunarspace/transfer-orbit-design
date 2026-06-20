"""optimize_dro_to_ro 转移设计脚本。

本模块读取已生成的轨道或搜索结果 JSON，在地月 CR3BP 单位体系中执行搜索、验证或 NLP 优化。网格类脚本输出候选转移，优化类脚本读取候选并最小化速度增量或插入误差，结果写入 output/transfer 相关目录。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.dro_to_ro.optimize_dro_to_ro --help
"""


from __future__ import annotations

import argparse
import json
import logging
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
from scipy.optimize import Bounds, minimize
from tqdm.auto import tqdm

from e2m2e.core import CR3BP_Dynamics, CR3BP_System
from e2m2e.core.orbit import Orbit
from e2m2e.mbse.data import TransferType
from e2m2e.transfer import (
    DROTRONLPOptimizer,
    NLPOptimizationVariables,
    TransferOptimizationResult,
    load_orbit_from_json,
    optimize_with_copt,
)
from tod.commons.constants import DU, MU, TU
from tod.transfers.optimize_config import (
    OptimizationProgress,
    apply_blas_env_for_child_processes,
    blas_threads_per_worker,
)

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent

SEARCH_RESULTS_DEFAULT = str(project_root / "output/transfer/search_results_200-100-0.5-2.5-22.998482_3857865736.json")
DRO_FILE_DEFAULT = str(project_root / "output/dro/dro_31_3857864736.json")
RO_FILE_DEFAULT = str(project_root / "output/ro/ro_31_3857864753.json")

SEARCH_RESULTS_FILE = Path(os.environ.get("SEARCH_RESULTS_FILE", SEARCH_RESULTS_DEFAULT))
DRO_FILE = Path(os.environ.get("DRO_FILE", DRO_FILE_DEFAULT))
RO_FILE = Path(os.environ.get("RO_FILE", RO_FILE_DEFAULT))

ALPHA_MIN = 0.5
ALPHA_MAX = 2.5

EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

DT = 1.0 / (24.0 * TU)
INTEGRATOR = "DOP853"
INTEGRATOR_RTOL = 1e-12
INTEGRATOR_ATOL = 1e-12

NLP_MAXITER = 100
NLP_FTOL = 1e-6
NLP_RTOL = 1e-10
NLP_ATOL = 1e-10
NLP_MAX_STEP = 0.1

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

COMPUTE_T_INS_FROM_TRAJECTORY = True


def parse_args():
    """解析命令行参数。
    
    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="DRO→RO 转移 NLP 优化（SLSQP 最小化 Δv）", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--search-file", type=str, default=None, help="网格搜索结果 JSON 文件路径")
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径")
    parser.add_argument("--ro-file", type=str, default=None, help="RO 轨道 JSON 文件路径")
    parser.add_argument("--alpha-min", type=float, default=ALPHA_MIN, help="alpha 搜索下界")
    parser.add_argument("--alpha-max", type=float, default=ALPHA_MAX, help="alpha 搜索上界")
    parser.add_argument("--nlp-maxiter", type=int, default=NLP_MAXITER, help="NLP 最大迭代次数")
    parser.add_argument("--nlp-ftol", type=float, default=NLP_FTOL, help="NLP 函数容差")
    parser.add_argument("--top-k", type=int, default=None, help="取前 K 个可行解优化")
    parser.add_argument("--max-cases", type=int, default=None, help="最大优化案例数")
    parser.add_argument("--n-workers", type=int, default=None, help="并行 worker 数")
    parser.add_argument("--velocity-angle-tol", type=float, default=VELOCITY_ANGLE_TOL, help="速度方向容差（弧度）")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 内联辅助函数（替代缺失的 optimize_io / optimize_progress 等）
# ---------------------------------------------------------------------------


def load_search_results(filepath: Path) -> List[Dict[str, Any]]:
    """读取转移搜索结果 JSON 文件。
    
    Args:
        filepath: 搜索结果文件路径。
    
    Returns:
        解析后的 JSON 数据列表。
    """
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def row_template(rec: Dict[str, Any], global_idx: int) -> Dict[str, Any]:
    """执行 row_template 对应的处理逻辑。
    
    Args:
        rec: 调用方传入的参数值。
        global_idx: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    return {
        "search_index": global_idx,
        "alpha": rec.get("alpha"),
        "transfer_time": rec.get("transfer_time"),
        "departure_state": rec.get("departure_state"),
        "is_feasible": rec.get("is_feasible"),
        "dv_departure": rec.get("dv_departure"),
    }


def serialize_nlp_result(res) -> Dict[str, Any]:
    """将结果对象转换为可写入 JSON 的结构。
    
    Args:
        res: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    return {
        "success": res.success,
        "alpha": float(res.departure_alpha),
        "transfer_time": float(res.transfer_time),
        "t_ins": float(res.t_ins),
        "objective_value": float(res.total_delta_v),
        "delta_v1": float(res.delta_v1),
        "delta_v2": float(res.delta_v2),
        "message": res.message,
        "constraints_violation": float(res.constraints_violation),
        "transfer_type": res.transfer_type.value if res.transfer_type else None,
    }


def build_dynamics(integrator: str, rtol: float, atol: float, max_step: float, mu: float):
    """构建脚本所需的动力学模型。
    
    Args:
        integrator: 调用方传入的参数值。
        rtol: 调用方传入的参数值。
        atol: 调用方传入的参数值。
        max_step: 调用方传入的参数值。
        mu: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    system = CR3BP_System(mu=mu, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = integrator
    dynamics.rtol = rtol
    dynamics.atol = atol
    dynamics.max_step = max_step
    return system, dynamics


def _compute_initial_t_ins(
    departure_state: np.ndarray,
    alpha: float,
    transfer_time: float,
    ro_orbit: Orbit,
    dynamics: CR3BP_Dynamics,
) -> Tuple[float, float]:
    pos = departure_state[:3]
    vel = departure_state[3:]
    v_mag = np.linalg.norm(vel)
    if v_mag < 1e-10:
        return transfer_time, 0.0
    tangential = vel / v_mag
    v_injection = alpha * v_mag * tangential
    initial_state = np.concatenate([pos, v_injection])

    result = dynamics.propagate(
        initial_state=initial_state,
        t_span=(0.0, transfer_time),
        with_stm=False,
        with_jacobi=False,
    )
    times = result["time"]
    states = result["states"]
    if len(states) == 0:
        return transfer_time, 0.0

    traj_pos = states[:, :3]
    ro_pos = np.asarray(ro_orbit.states)[:, :3]
    ro_times = np.asarray(ro_orbit.times)

    dists = np.sqrt(
        np.sum((traj_pos[:, None, :] - ro_pos[None, :, :]) ** 2, axis=2)
    )
    flat_idx = np.argmin(dists)
    i, j = np.unravel_index(flat_idx, dists.shape)
    return float(times[i]), float(ro_times[j])


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
    nlp_maxiter=NLP_MAXITER,
    nlp_ftol=NLP_FTOL,
):
    """执行转移优化计算。
    
    Args:
        rec: 调用方传入的参数值。
        dro_orbit: 调用方传入的参数值。
        ro_orbit: 调用方传入的参数值。
        system: 调用方传入的参数值。
        dynamics: 调用方传入的参数值。
        verbose: 调用方传入的参数值。
        alpha_min: 调用方传入的参数值。
        alpha_max: 调用方传入的参数值。
        earth_radius: 调用方传入的参数值。
        moon_radius: 调用方传入的参数值。
        use_relaxed_velocity: 调用方传入的参数值。
        velocity_angle_tol: 调用方传入的参数值。
        use_copt: 调用方传入的参数值。
        fallback_to_scipy: 调用方传入的参数值。
        progress_callback: 调用方传入的参数值。
        nlp_maxiter: 调用方传入的参数值。
        nlp_ftol: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    departure_state = np.array(rec["departure_state"], dtype=float)

    alpha_0 = rec["alpha"]
    T_0 = rec["transfer_time"]
    t_ins_0 = rec.get("t_ins", None)

    nlp_system = CR3BP_System(mu=system.mu, primary="earth", secondary="moon")
    nlp_dynamics = CR3BP_Dynamics(system=nlp_system)
    nlp_dynamics.integrator = dynamics.integrator
    nlp_dynamics.rtol = NLP_RTOL
    nlp_dynamics.atol = NLP_ATOL
    nlp_dynamics.max_step = NLP_MAX_STEP

    if COMPUTE_T_INS_FROM_TRAJECTORY and (t_ins_0 is None or t_ins_0 == 0.0):
        T_0, t_ins_0 = _compute_initial_t_ins(
            departure_state, alpha_0, T_0, ro_orbit, nlp_dynamics
        )

    y0 = np.array([alpha_0, T_0, t_ins_0 if t_ins_0 is not None else 0.0])

    if use_copt:
        optimizer = DROTRONLPOptimizer(
            system=nlp_system,
            dynamics=nlp_dynamics,
            departure_orbit=dro_orbit,
            arrival_orbit=ro_orbit,
            departure_state=departure_state,
        )
        optimizer.alpha_range = (alpha_min, alpha_max)
        optimizer.earth_radius = earth_radius
        optimizer.moon_radius = moon_radius
        ig = NLPOptimizationVariables(alpha=y0[0], transfer_time=y0[1], t_ins=y0[2])
        return optimize_with_copt(
            optimizer, initial_guess=ig, fallback_to_scipy=fallback_to_scipy
        )

    optimizer = DROTRONLPOptimizer(
        system=nlp_system,
        dynamics=nlp_dynamics,
        departure_orbit=dro_orbit,
        arrival_orbit=ro_orbit,
        departure_state=departure_state,
    )
    optimizer.alpha_range = (alpha_min, alpha_max)
    optimizer.earth_radius = earth_radius
    optimizer.moon_radius = moon_radius
    optimizer.enable_cache(True)

    bounds = Bounds(
        lb=[alpha_min, 1.0, 0.0],  # type: ignore[arg-type]
        ub=[alpha_max, 30.0, 10.0],  # type: ignore[arg-type]
    )

    constraints = [{"type": "eq", "fun": optimizer.constraint_position}]

    cos_theta_max = np.cos(velocity_angle_tol)
    if use_relaxed_velocity:
        constraints.append(
            {"type": "ineq", "fun": lambda y: cos_theta_max - optimizer._compute_cos_angle(y)}
        )
    else:
        constraints.append({"type": "eq", "fun": optimizer.constraint_velocity_parallel})

    iteration_counter = [0]

    def _scipy_cb(xk):
        iteration_counter[0] += 1
        if progress_callback is not None:
            obj_k = float(optimizer.objective_function(xk))
            progress_callback(
                iteration_counter[0], obj_k, float(xk[0]), float(xk[1]), float(xk[2])
            )

    try:
        result = minimize(
            optimizer.objective_function,
            y0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": nlp_ftol, "maxiter": nlp_maxiter, "disp": verbose},
            callback=_scipy_cb,
        )

        final_y = result.x
        cache = optimizer._evaluate_all(final_y)

        states = cache["states"]
        times = cache["times"]
        final_state = cache["final_state"]
        insertion_state = cache["insertion_state"]
        dv1 = cache["dv1"]
        dv2 = cache["dv2"]

        violation = {}
        if result.success:
            violation["position"] = float(cache["pos_violation"])
            if use_relaxed_velocity:
                violation["velocity"] = max(0.0, cos_theta_max - cache["cos_angle"])
            else:
                violation["velocity"] = abs(float(optimizer.constraint_velocity_parallel(final_y)))

        transfer_type = TransferType.DIRECT
        if not cache["empty"]:
            x_max = float(np.max(states[:, 0]))
            T_opt = float(final_y[1])
            if T_opt < 20.0 and x_max < 1.5:
                transfer_type = TransferType.DIRECT
            elif x_max > 3.0:
                transfer_type = TransferType.EXTERNAL
            else:
                transfer_type = TransferType.LGA

        return TransferOptimizationResult(
            departure_alpha=float(final_y[0]),
            transfer_time=float(final_y[1]),
            t_ins=float(final_y[2]),
            total_delta_v=dv1 + dv2,
            delta_v1=dv1,
            delta_v2=dv2,
            transfer_trajectory=states,
            transfer_trajectory_times=times,
            departure_state=departure_state.copy(),
            insertion_state=insertion_state,
            final_state=final_state,
            success=bool(result.success),
            message=str(result.message),
            transfer_type=transfer_type,
            constraints_violation=max(violation.values()) if violation else 0.0,
        )
    except Exception as e:
        return TransferOptimizationResult(
            departure_alpha=float(y0[0]),
            transfer_time=float(y0[1]),
            t_ins=float(y0[2]),
            success=False,
            message=f"优化失败: {e}",
        )


def make_progress_callback(prog: OptimizationProgress, k, n_total, global_idx):
    """执行 make_progress_callback 对应的处理逻辑。
    
    Args:
        prog: 调用方传入的参数值。
        k: 调用方传入的参数值。
        n_total: 调用方传入的参数值。
        global_idx: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    def _cb(iteration, obj_value, alpha, T, t_ins):
        prog._iter = iteration

    return _cb


def monitor_loop_serial_nlp(prog: OptimizationProgress):
    """执行 monitor_loop_serial_nlp 对应的处理逻辑。
    
    Args:
        prog: 调用方传入的参数值。
    
    Returns:
        None。
    """
    while True:
        time.sleep(10)
        if prog.start_time > 0 and prog.total_cases > 0:
            done = prog._successes + prog._failures
            if done >= prog.total_cases:
                break
            elapsed = time.perf_counter() - prog.start_time
            snap = prog.get_snapshot()
            logger.info(
                f"  [monitor] elapsed={elapsed:.1f}s | "
                f"done={done}/{prog.total_cases} | "
                f"best_dV={snap['best_obj']:.6f}"
            )


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
    """表示 ThreadNlpParams 相关的数据结构或行为。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
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
    """执行 nlp_worker_packed 对应的处理逻辑。
    
    Args:
        payload: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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
    """执行 worker_run_thread 对应的处理逻辑。
    
    Args:
        args: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
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
# 主流程
# ---------------------------------------------------------------------------


def main() -> None:
    """加载网格与轨道、筛选可行解、按并行设置跑 NLP，并写出 ``optimization_results_*.json``。"""
    args = parse_args()

    # CLI 参数覆盖模块级常量
    search_file = Path(args.search_file or os.environ.get("SEARCH_RESULTS_FILE", SEARCH_RESULTS_DEFAULT))
    dro_file = Path(args.dro_file or os.environ.get("DRO_FILE", DRO_FILE_DEFAULT))
    ro_file = Path(args.ro_file or os.environ.get("RO_FILE", RO_FILE_DEFAULT))
    alpha_min = args.alpha_min
    alpha_max = args.alpha_max
    top_k = args.top_k if args.top_k is not None else TOP_K_FEASIBLE
    max_cases = args.max_cases if args.max_cases is not None else MAX_CASES
    n_workers = args.n_workers if args.n_workers is not None else N_WORKERS
    velocity_angle_tol = args.velocity_angle_tol

    logger.info("=" * 70)
    logger.info("DRO-RO 转移 NLP 优化（Cui et al. 2025；e2m2e DROTRONLPOptimizer）")
    logger.info("=" * 70)

    if not search_file.is_file():
        raise FileNotFoundError(f"未找到网格结果文件: {search_file}")
    if not dro_file.is_file():
        raise FileNotFoundError(f"未找到 DRO 文件: {dro_file}")
    if not ro_file.is_file():
        raise FileNotFoundError(f"未找到 RO 文件: {ro_file}")

    logger.info("\n优化配置:")
    _cpu = multiprocessing.cpu_count() or 1
    logger.info(
        f"  并行: n_workers={n_workers}（None=逻辑 CPU 数 {_cpu}）, backend={PARALLEL_BACKEND}"
    )
    logger.info(f"  TOP_K_FEASIBLE: {top_k}")
    logger.info(f"  MAX_CASES: {max_cases}")
    logger.info(f"  α 范围: [{alpha_min:.2f}, {alpha_max:.2f}]")
    logger.info(f"  积分步长（1 小时）: {DT:.8f} TU")
    logger.info(f"  碰撞半径: 地球={EARTH_RADIUS:.4f}, 月球={MOON_RADIUS:.4f}")
    logger.info(f"  进度条: {'开启（tqdm）' if USE_TQDM else '关闭（OPTIMIZE_NO_TQDM）'}")
    logger.info(f"  自动推算 t_ins: {COMPUTE_T_INS_FROM_TRAJECTORY}")

    logger.info("\n加载网格结果:")
    logger.info(f"  文件: {search_file}")
    logger.info("  正在读取 JSON（大文件可能较慢）…")
    all_results = load_search_results(search_file)
    total_records = len(all_results)
    feasible_indexed: List[Tuple[int, Dict[str, Any]]] = [
        (i, r) for i, r in enumerate(all_results) if r.get("is_feasible")
    ]

    n_feasible_total = len(feasible_indexed)
    if top_k is not None:
        feasible_indexed = feasible_indexed[:top_k]
    if max_cases is not None:
        feasible_indexed = feasible_indexed[:max_cases]

    del all_results

    logger.info(f"\n网格记录总数: {total_records}")
    logger.info(f"可行解总数: {n_feasible_total}")
    logger.info(f"本次待优化（经 TOP_K / MAX_CASES 截断后）: {len(feasible_indexed)}")
    if USE_COPT:
        from e2m2e.transfer import _HAVE_COPT

        logger.info(f"NLP: COPT（已安装: {_HAVE_COPT}），失败则 SciPy SLSQP")
    else:
        logger.info("NLP: SciPy SLSQP（scipy.optimize.minimize）")

    if not feasible_indexed:
        logger.info("\n没有可行解，退出。")
        return

    logger.info("\n加载轨道数据:")
    dro_orbit = load_orbit_from_json(str(dro_file))
    ro_orbit = load_orbit_from_json(str(ro_file))
    logger.info(f"  DRO: {dro_file}")
    logger.info(f"  RO: {ro_file}")

    with open(ro_file, encoding="utf-8") as f:
        ro_json = json.load(f)
    if "properties" in ro_json and "period" in ro_json["properties"]:
        ro_orbit.period = float(ro_json["properties"]["period"])

    logger.info(f"  DRO 周期: {dro_orbit.period:.4f} TU, 状态数: {len(dro_orbit.states)}")
    logger.info(f"  RO 周期: {ro_orbit.period:.4f} TU, 状态数: {len(ro_orbit.states)}")

    system, dynamics = build_dynamics(
        integrator=INTEGRATOR,
        rtol=INTEGRATOR_RTOL,
        atol=INTEGRATOR_ATOL,
        max_step=DT,
        mu=MU,
    )
    logger.info("\ne2m2e 动力学已就绪")
    logger.info(f"  系统: μ = {system.mu:.6e}")
    logger.info(f"  积分器: {dynamics.integrator}")
    logger.info(f"  rtol/atol: {dynamics.rtol:g} / {dynamics.atol:g}")
    logger.info(f"  max_step: {dynamics.max_step:.8f} TU")

    pack_cfg = NlpPackConfig(
        mu=float(MU),
        alpha_min=float(alpha_min),
        alpha_max=float(alpha_max),
        earth_radius=float(EARTH_RADIUS),
        moon_radius=float(MOON_RADIUS),
        dt=float(DT),
        integrator=str(INTEGRATOR),
        integrator_rtol=float(INTEGRATOR_RTOL),
        integrator_atol=float(INTEGRATOR_ATOL),
        use_relaxed_velocity=bool(USE_RELAXED_VELOCITY),
        velocity_angle_tol=float(velocity_angle_tol),
        use_copt=bool(USE_COPT),
        fallback_to_scipy=bool(FALLBACK_TO_SCIPY),
    )
    thread_nlp = ThreadNlpParams(
        alpha_min=float(alpha_min),
        alpha_max=float(alpha_max),
        earth_radius=float(EARTH_RADIUS),
        moon_radius=float(MOON_RADIUS),
        use_relaxed_velocity=bool(USE_RELAXED_VELOCITY),
        velocity_angle_tol=float(velocity_angle_tol),
        use_copt=bool(USE_COPT),
        fallback_to_scipy=bool(FALLBACK_TO_SCIPY),
    )

    output_dir = project_root / "output/transfer"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"optimization_results_{int(time.time())}.json"

    backend = PARALLEL_BACKEND.strip().lower()
    if backend not in ("threads", "processes"):
        raise ValueError("PARALLEL_BACKEND 须为 'threads' 或 'processes'")

    cpu_n = multiprocessing.cpu_count() or 1
    if n_workers is None:
        n_workers_req = max(1, cpu_n)
    else:
        n_workers_req = max(1, int(n_workers))

    n_total = len(feasible_indexed)
    disable_tqdm = not USE_TQDM or n_total <= 0

    logger.info("\n" + "=" * 70)
    logger.info("开始 NLP 优化")
    logger.info("=" * 70)

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
                    alpha_min=float(alpha_min),
                    alpha_max=float(alpha_max),
                    earth_radius=float(EARTH_RADIUS),
                    moon_radius=float(MOON_RADIUS),
                    use_relaxed_velocity=bool(USE_RELAXED_VELOCITY),
                    velocity_angle_tol=float(velocity_angle_tol),
                    use_copt=bool(USE_COPT),
                    fallback_to_scipy=bool(FALLBACK_TO_SCIPY),
                    progress_callback=cb,
                )
                row["nlp"] = serialize_nlp_result(res)
                global_progress.finish_case(res.success, res.total_delta_v)
                snap = global_progress.get_snapshot()
                elapsed = (
                    time.perf_counter() - global_progress.start_time
                    if global_progress.start_time > 0
                    else 0
                )
                logger.info(
                    f"  ✓ case {k + 1}/{n_total} done "
                    f"(search_idx={global_idx}) | "
                    f"iter={snap['iter']} | "
                    f"success={res.success} ΔV={res.total_delta_v:.6f} | "
                    f"elapsed={elapsed:.1f}s"
                )
            except Exception:
                row["error"] = traceback.format_exc()
                global_progress.finish_case(False, float("inf"))
                logger.info(
                    f"  ✗ case {k + 1}/{n_total} ERROR (search_idx={global_idx}):\n"
                    f"  {row['error'][:500]}"
                )
            records.append(row)
    else:
        n_pool = min(n_workers_req, n_total)
        logger.info(
            f"  并行执行: {n_pool} 个 worker（backend={backend}，本机逻辑 CPU={cpu_n}）"
        )
        if backend == "processes":
            _bt = blas_threads_per_worker(default_limit=LIMIT_BLAS_THREADS_PER_WORKER)
            apply_blas_env_for_child_processes(_bt)
            logger.info(
                f"  多进程 BLAS/OpenMP: 每 worker {_bt} 线程（环境已写入 OMP/MKL/OpenBLAS 等）"
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
                    "search_results_file": str(search_file),
                    "dro_file": str(dro_file),
                    "ro_file": str(ro_file),
                    "alpha_range": [alpha_min, alpha_max],
                    "nlp_solver": "copt_with_scipy_fallback" if USE_COPT else "scipy_slsqp",
                    "use_relaxed_velocity": USE_RELAXED_VELOCITY,
                    "n_optimized": len(records),
                    "parallel_backend": PARALLEL_BACKEND,
                    "n_workers_requested": n_workers,
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

    logger.info(f"\n优化完成，共写入 {len(records)} 条记录")
    logger.info(f"结果已保存到: {out_path}")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--alpha-min", "0.5",                         # alpha 搜索下界（ALPHA_MIN）
            "--alpha-max", "2.5",                         # alpha 搜索上界（ALPHA_MAX）
            "--nlp-maxiter", "100",                       # NLP 最大迭代次数（NLP_MAXITER）
            "--nlp-ftol", "1e-6",                         # NLP 函数容差（NLP_FTOL）
            "--velocity-angle-tol", "0.05",              # 速度方向容差（VELOCITY_ANGLE_TOL）
        ]
        logger.debug("使用代码内置调试参数")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.gui.script_registry import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='optimize_dro_to_ro',
    description='优化',
    script_path='tod/transfers/dro_to_ro/optimize_dro_to_ro.py',
    output_dir='output/transfer',
    group_label='DRO→RO',
    cli_params=[
        CliParam('--search-file', '搜索结果文件', 'str', '', help='网格搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--ro-file', 'RO 文件', 'str', '', help='RO 轨道 JSON 文件路径。', file_category='ro'),
        CliParam('--alpha-min', 'alpha 下界', 'float', '0.5', help='alpha 搜索下界。'),
        CliParam('--alpha-max', 'alpha 上界', 'float', '2.5', help='alpha 搜索上界。'),
        CliParam('--nlp-maxiter', 'NLP 最大迭代', 'int', '100', help='NLP 最大迭代次数。'),
        CliParam('--nlp-ftol', 'NLP 函数容差', 'float', '1e-8', help='NLP 函数容差。'),
        CliParam('--top-k', '前 K 个可行解', 'int', '', help='取前 K 个可行解优化。'),
        CliParam('--max-cases', '最大案例数', 'int', '', help='最大优化案例数。'),
        CliParam('--n-workers', '并行 worker 数', 'int', '', help='并行 worker 数。'),
        CliParam('--velocity-angle-tol', '速度方向容差', 'float', '0.05', help='速度方向容差（弧度）。', unit_group='angle'),
    ],
)
