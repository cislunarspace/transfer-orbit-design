"""
GEO → DRO NLP 优化

从 GEO 出发的转移轨道 NLP 优化（第二步）。
读取搜索结果，对可行解进行 root-LM + Nelder-Mead 精细化。

优化变量: y = [α, T, t_ins]
  - α: GEO 出发切向速度比
  - T: 转移时间
  - t_ins: DRO 上的插入时间

目标函数: J(y) = Δv1 + Δv2
约束:
  - 位置连续性: ||pos_final - pos_DRO(t_ins)||² = 0
  - 速度平行性: 后过滤 cos(angle) ≥ cos(tolerance)

运行: python -m tod.transfers.geo_to_dro.optimize_geo_to_dro

Windows 须保留 ``if __name__ == "__main__"``。
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import time
from scipy.optimize import minimize

from e2m2e.core import CR3BP_Dynamics, CR3BP_System
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import load_orbit_from_json
from tod.commons.constants import DU, MU, TU, VU
from tod.transfers.optimize_config import apply_blas_env_for_child_processes, blas_threads_per_worker
from e2m2e.orbits.geo import (
    compute_departure_velocity,
)
import logging

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent

# =====================================================================
# 配置 — 运行前须更新文件路径
# =====================================================================
SEARCH_RESULTS_DEFAULT = str(project_root / "output/transfer/search_geo_dro_10-200-1-1.5-2.2998_1775916430.json")
DRO_FILE_DEFAULT = str(project_root / "output/dro/dro_31_3857864736.json")

SEARCH_RESULTS_FILE = Path(os.environ.get("SEARCH_RESULTS_FILE", SEARCH_RESULTS_DEFAULT))
DRO_FILE = Path(os.environ.get("DRO_FILE", DRO_FILE_DEFAULT))

ALPHA_MIN = 1.0
ALPHA_MAX = 1.5
T_MIN = 5.0
T_MAX = 60.0
T_INS_MIN = 0.0
T_INS_MAX = 10.0

EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

# 速度平行性松弛（弧度），0 表示严格平行
VELOCITY_ANGLE_TOLERANCE = np.deg2rad(10.0)  # 10° 不等式约束

DT = 1.0 / (24.0 * TU)
INTEGRATOR = "DOP853"
INTEGRATOR_RTOL = 1e-12
INTEGRATOR_ATOL = 1e-12

NLP_MAXITER = 100
NLP_FTOL = 1e-8
NLP_RTOL = 1e-10
NLP_ATOL = 1e-10
NLP_MAX_STEP = 0.1

TOP_K_FEASIBLE: Optional[int] = 100
MAX_CASES: Optional[int] = None

N_WORKERS: Optional[int] = None
PARALLEL_BACKEND: str = "threads"



def parse_args():
    parser = argparse.ArgumentParser(description="GEO→DRO 转移 NLP 优化")
    parser.add_argument("--search-file", type=str, default=None, help="网格搜索结果 JSON 文件路径")
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径")
    parser.add_argument("--alpha-min", type=float, default=ALPHA_MIN, help="alpha 搜索下界")
    parser.add_argument("--alpha-max", type=float, default=ALPHA_MAX, help="alpha 搜索上界")
    parser.add_argument("--t-min", type=float, default=T_MIN, help="转移时间下界（无量纲）")
    parser.add_argument("--t-max", type=float, default=T_MAX, help="转移时间上界（无量纲）")
    parser.add_argument("--t-ins-min", type=float, default=T_INS_MIN, help="DRO 插入时间下界")
    parser.add_argument("--t-ins-max", type=float, default=T_INS_MAX, help="DRO 插入时间上界")
    parser.add_argument("--velocity-angle-tol", type=float, default=None, help="速度平行性容差（度）")
    parser.add_argument("--nlp-maxiter", type=int, default=NLP_MAXITER, help="NLP 最大迭代次数")
    parser.add_argument("--nlp-ftol", type=float, default=NLP_FTOL, help="NLP 函数容差")
    parser.add_argument("--top-k", type=int, default=None, help="取前 K 个可行解优化")
    parser.add_argument("--max-cases", type=int, default=None, help="最大优化案例数")
    parser.add_argument("--n-workers", type=int, default=None, help="并行 worker 数")
    return parser.parse_args()


# =====================================================================
# Helpers
# =====================================================================


def build_dynamics(rtol, atol, max_step):
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = INTEGRATOR
    dynamics.rtol = rtol
    dynamics.atol = atol
    dynamics.max_step = max_step
    return system, dynamics


def forward_integrate(dynamics, initial_state, transfer_time):
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


def get_dro_state_at_time(dro_orbit: Orbit, t_ins: float) -> np.ndarray:
    """获取 DRO 轨道上在 t_ins 时刻的状态。

    使用 CR3BP_Dynamics 从 DRO 初始状态前向积分到 t_ins（对周期取模）。
    """
    period = dro_orbit.period
    if period is None or period <= 0:
        # 无周期信息，直接用最近的采样点
        idx = int(t_ins / (dro_orbit.times[-1] / len(dro_orbit.times))) % len(dro_orbit.times)
        return dro_orbit.states[idx]

    t_mod = t_ins % period
    # 在已有采样点中插值
    times = dro_orbit.times
    states = dro_orbit.states

    # 找到 t_mod 两侧的索引
    idx = np.searchsorted(times, t_mod, side="right") - 1
    idx = max(0, min(idx, len(times) - 2))

    t0, t1 = times[idx], times[idx + 1]
    s0, s1 = states[idx], states[idx + 1]

    if abs(t1 - t0) < 1e-15:
        return s0.copy()

    frac = (t_mod - t0) / (t1 - t0)
    return s0 + frac * (s1 - s0)


# =====================================================================
# 初始猜测：重新积分找最接近 DRO 的时刻
# =====================================================================


def _find_closest_approach(departure_state, alpha, max_time, dro_orbit, dynamics):
    """重新积分转移轨迹，找到最接近 DRO 轨道的时刻。

    Returns:
        (t_closest, t_dro_closest, min_distance)
        t_closest: 转移轨迹上的时间（作为 T 初值）
        t_dro_closest: DRO 轨道上的时间（作为 t_ins 初值）
        min_distance: 最近距离 (DU)
    """
    v_dep = compute_departure_velocity(departure_state, alpha)
    s0 = np.concatenate([departure_state[:3], v_dep])

    step = max(0.01, dynamics.max_step)
    n_steps = int(max_time / step) + 1
    t_eval = np.linspace(0.0, max_time, n_steps)

    try:
        result = dynamics.propagate(
            initial_state=s0, t_span=(0.0, max_time),
            t_eval=t_eval, with_stm=False, with_jacobi=False,
        )
        states = result["states"]
        times = result["time"]
    except Exception:
        return max_time * 0.5, 0.0, 1e10

    if len(states) == 0:
        return max_time * 0.5, 0.0, 1e10

    # DRO 轨道采样
    dro_states = dro_orbit.states
    dro_times = dro_orbit.times

    # 对每个转移轨迹点，找最近的 DRO 点
    min_dist_sq = float("inf")
    best_t_idx = 0
    best_dro_idx = 0

    # 分块处理避免内存爆炸
    chunk = 500
    for i_start in range(0, len(states), chunk):
        i_end = min(i_start + chunk, len(states))
        # (chunk, 1, 3) - (1, n_dro, 3) → (chunk, n_dro, 3)
        diff = states[i_start:i_end, np.newaxis, :3] - dro_states[np.newaxis, :, :3]
        dist_sq = np.sum(diff ** 2, axis=2)  # (chunk, n_dro)
        flat_idx = np.argmin(dist_sq)
        ci, di = np.unravel_index(flat_idx, dist_sq.shape)
        if dist_sq[ci, di] < min_dist_sq:
            min_dist_sq = dist_sq[ci, di]
            best_t_idx = i_start + ci
            best_dro_idx = di

    t_closest = float(times[best_t_idx])
    min_dist = float(np.sqrt(min_dist_sq))

    # DRO 时间
    if best_dro_idx < len(dro_times):
        t_dro_closest = float(dro_times[best_dro_idx])
    else:
        t_dro_closest = 0.0

    return t_closest, t_dro_closest, min_dist


# =====================================================================
# NLP problem
# =====================================================================


def _nlp_eval(y, departure_state, dro_orbit, dynamics):
    """Evaluate objective, constraint, and cache for y = [alpha, T, t_ins]."""
    alpha, T, t_ins = y

    v_dep = compute_departure_velocity(departure_state, alpha)
    dv1 = float(np.linalg.norm(v_dep - departure_state[3:]))
    state0 = np.concatenate([departure_state[:3], v_dep])

    try:
        states, times = forward_integrate(dynamics, state0, T)
    except Exception:
        return {"empty": True, "objective": 1e10}

    if len(states) == 0:
        return {"empty": True, "objective": 1e10}

    final_state = states[-1]
    final_pos = final_state[:3]
    final_vel = final_state[3:]

    # 获取 DRO 上的插入点状态
    dro_state = get_dro_state_at_time(dro_orbit, t_ins)
    dro_pos = dro_state[:3]
    dro_vel = dro_state[3:]

    # 位置误差
    pos_error = final_pos - dro_pos
    pos_violation = float(np.dot(pos_error, pos_error))

    # 速度平行性
    v_final_mag = np.linalg.norm(final_vel)
    v_dro_mag = np.linalg.norm(dro_vel)
    cos_angle = -1.0
    if v_final_mag > 1e-10 and v_dro_mag > 1e-10:
        cos_angle = float(np.dot(final_vel, dro_vel) / (v_final_mag * v_dro_mag))
        cos_angle = max(-1.0, min(1.0, cos_angle))

    # Δv2: 速度差
    dv2 = float(np.linalg.norm(final_vel - dro_vel))

    return {
        "empty": False,
        "states": states,
        "times": times,
        "final_state": final_state,
        "dro_state_at_ins": dro_state,
        "dv1": dv1,
        "dv2": dv2,
        "objective": dv1 + dv2,
        "pos_error": pos_error,
        "pos_violation": pos_violation,
        "cos_angle": cos_angle,
        "angle_deg": float(np.degrees(np.arccos(max(-1, min(1, cos_angle))))) if cos_angle > -1 else 180.0,
    }


def optimize_one_case(
    rec,
    dro_orbit,
    *,
    alpha_min=ALPHA_MIN,
    alpha_max=ALPHA_MAX,
    t_min=T_MIN,
    t_max=T_MAX,
    t_ins_min=T_INS_MIN,
    t_ins_max=T_INS_MAX,
    earth_radius=EARTH_RADIUS,
    moon_radius=MOON_RADIUS,
    angle_tolerance=VELOCITY_ANGLE_TOLERANCE,
    verbose=False,
):
    departure_state = np.array(rec["departure_state"], dtype=float)
    alpha_0 = rec["alpha"]
    T_search = rec["transfer_time"]

    # 用动力学对象重新积分找最接近 DRO 的时刻
    _, dynamics = build_dynamics(1e-10, 1e-10, NLP_MAX_STEP)
    t_closest, t_dro_closest, reinit_min_dist = _find_closest_approach(
        departure_state, alpha_0, T_search, dro_orbit, dynamics,
    )

    T_0 = max(t_min, min(t_closest, t_max))
    t_ins_0 = max(t_ins_min, min(t_dro_closest, t_ins_max))

    if verbose:
        logger.info(f"  init: T_closest={t_closest:.2f}, t_ins={t_ins_0:.4f}, "
              f"dist={reinit_min_dist*DU:.0f} km")

    # ====== 方法: root 求解位置匹配 + alpha 扫描 ======

    def _position_residual(x, alpha):
        """给定 alpha，求 [T, t_ins] 使位置误差为 0。返回 [dx, dy]。"""
        T_val, t_ins_val = x
        if T_val < t_min or T_val > t_max:
            return np.array([1e6, 1e6])
        c = _nlp_eval([alpha, T_val, t_ins_val], departure_state, dro_orbit, dynamics)
        if c["empty"]:
            return np.array([1e6, 1e6])
        return c["pos_error"][:2]  # x, y 分量

    def _solve_for_alpha(alpha_val, T_init, tins_init):
        """对给定 alpha，用 root 求解 [T, t_ins]。"""
        from scipy.optimize import root
        try:
            sol = root(
                _position_residual, [T_init, tins_init], args=(alpha_val,),
                method="lm",  # Levenberg-Marquardt，对超定/近奇异系统鲁棒
                options={"maxiter": 50, "xtol": 1e-12},
            )
            if sol.success and sol.fun[0]**2 + sol.fun[1]**2 < 1e-8:
                T_sol, tins_sol = sol.x
                if t_min <= T_sol <= t_max and t_ins_min <= tins_sol <= t_ins_max:
                    return T_sol, tins_sol, True
            return T_init, tins_init, False
        except Exception:
            return T_init, tins_init, False

    # 在 alpha_0 附近扫描，找最优 Δv
    alpha_grid = np.linspace(
        max(alpha_min, alpha_0 - 0.03),
        min(alpha_max, alpha_0 + 0.03),
        7,
    )

    best_result = None
    best_dv = float("inf")
    T_prev, tins_prev = T_0, t_ins_0

    for a_val in alpha_grid:
        T_sol, tins_sol, ok = _solve_for_alpha(a_val, T_prev, tins_prev)
        if not ok:
            continue
        T_prev, tins_prev = T_sol, tins_sol

        c = _nlp_eval([a_val, T_sol, tins_sol], departure_state, dro_orbit, dynamics)
        if c["empty"]:
            continue

        pos_err = np.sqrt(c["pos_violation"])
        dv_total = c["dv1"] + c["dv2"]

        pos_err_km = pos_err * DU
        if pos_err_km < 384 and dv_total < best_dv:  # < ~384 km; final filter at 100 km in main()
            best_dv = dv_total
            best_result = {
                "alpha": a_val,
                "T": T_sol,
                "t_ins": tins_sol,
                "c": c,
            }

    # 如果 alpha 扫描没找到好的结果，用 Nelder-Mead 做位置匹配
    if best_result is None:
        def _nm_obj(y):
            c = _nlp_eval(y, departure_state, dro_orbit, dynamics)
            if c["empty"]:
                return 1e10
            return c["pos_violation"]

        try:
            nm_res = minimize(
                _nm_obj, [alpha_0, T_0, t_ins_0], method="Nelder-Mead",
                options={"maxiter": 200, "adaptive": True},
            )
            c = _nlp_eval(nm_res.x, departure_state, dro_orbit, dynamics)
            if not c["empty"]:
                best_result = {
                    "alpha": nm_res.x[0],
                    "T": nm_res.x[1],
                    "t_ins": nm_res.x[2],
                    "c": c,
                }
        except Exception:
            logger.info(f"    警告: Nelder-Mead 精修失败 (departure_idx={rec.get('departure_time_index', '?')})")

    if best_result is None:
        return {
            "search_index": rec.get("departure_time_index", -1),
            "search_alpha": float(alpha_0),
            "search_transfer_time": float(T_search),
            "departure_state": rec["departure_state"],
            "search_min_distance": rec.get("min_distance"),
            "reinit_min_distance": reinit_min_dist,
            "nlp": {"success": False, "message": "No solution found"},
        }

    c = best_result["c"]

    # 后过滤: 速度角度超过容限则拒绝
    if c["cos_angle"] < np.cos(angle_tolerance):
        return {
            "search_index": rec.get("departure_time_index", -1),
            "search_alpha": float(alpha_0),
            "search_transfer_time": float(T_search),
            "departure_state": rec["departure_state"],
            "search_min_distance": rec.get("min_distance"),
            "reinit_min_distance": reinit_min_dist,
            "nlp": {
                "success": False,
                "message": f"速度角度 {c['angle_deg']:.1f}° 超过容限 {np.degrees(angle_tolerance):.1f}°",
            },
        }

    final_y = [best_result["alpha"], best_result["T"], best_result["t_ins"]]

    return {
        "search_index": rec.get("departure_time_index", -1),
        "search_alpha": float(alpha_0),
        "search_transfer_time": float(T_search),
        "departure_state": rec["departure_state"],
        "is_feasible": rec.get("is_feasible"),
        "search_dv_departure": rec.get("dv_departure"),
        "search_min_distance": rec.get("min_distance"),
        "reinit_min_distance": reinit_min_dist,
        "initial_T_guess": t_closest,
        "initial_t_ins_guess": t_dro_closest,
        "nlp": {
            "success": True,
            "alpha": float(final_y[0]),
            "transfer_time": float(final_y[1]),
            "t_ins": float(final_y[2]),
            "objective_value": c.get("dv1", 0) + c.get("dv2", 0),
            "delta_v1": c.get("dv1", 0.0),
            "delta_v2": c.get("dv2", 0.0),
            "pos_violation": c.get("pos_violation", float("nan")),
            "cos_angle": c.get("cos_angle", float("nan")),
            "angle_deg": c.get("angle_deg", float("nan")),
        },
    }


# =====================================================================
# Parallel workers
# =====================================================================


@dataclass
class NlpPackConfig:
    alpha_min: float
    alpha_max: float
    t_min: float
    t_max: float
    t_ins_min: float
    t_ins_max: float
    earth_radius: float
    moon_radius: float
    angle_tolerance: float


def nlp_worker_packed(payload):
    rec = payload["rec"]
    dro_orbit = payload["dro_orbit"]
    cfg = payload["cfg"]

    return optimize_one_case(
        rec,
        dro_orbit,
        alpha_min=cfg.alpha_min,
        alpha_max=cfg.alpha_max,
        t_min=cfg.t_min,
        t_max=cfg.t_max,
        t_ins_min=cfg.t_ins_min,
        t_ins_max=cfg.t_ins_max,
        earth_radius=cfg.earth_radius,
        moon_radius=cfg.moon_radius,
        angle_tolerance=cfg.angle_tolerance,
    )


# =====================================================================
# main
# =====================================================================


def main() -> None:
    args = parse_args()

    # 限制 BLAS 线程，避免过量订阅（保留已有环境变量，不覆盖）——原用 setdefault
    apply_blas_env_for_child_processes(blas_threads_per_worker(), overwrite=False)

    # CLI 参数覆盖
    search_file = Path(args.search_file or os.environ.get("SEARCH_RESULTS_FILE", SEARCH_RESULTS_DEFAULT))
    dro_file = Path(args.dro_file or os.environ.get("DRO_FILE", DRO_FILE_DEFAULT))
    alpha_min = args.alpha_min
    alpha_max = args.alpha_max
    t_min = args.t_min
    t_max = args.t_max
    t_ins_min = args.t_ins_min
    t_ins_max = args.t_ins_max
    angle_tol = np.deg2rad(args.velocity_angle_tol) if args.velocity_angle_tol is not None else VELOCITY_ANGLE_TOLERANCE
    top_k = args.top_k if args.top_k is not None else TOP_K_FEASIBLE
    max_cases = args.max_cases if args.max_cases is not None else MAX_CASES
    n_workers = args.n_workers if args.n_workers is not None else N_WORKERS

    logger.info("=" * 70)
    logger.info("GEO → DRO 转移 NLP 优化")
    logger.info("=" * 70)

    if not search_file.is_file():
        raise FileNotFoundError(f"未找到搜索结果: {search_file}")

    # 查找 DRO 文件
    if not dro_file.exists():
        dro_dir = project_root / "output/dro"
        dro_files = sorted(dro_dir.glob("dro_31_*.json"))
        if not dro_files:
            raise FileNotFoundError("找不到 DRO 轨道文件")
        dro_file = dro_files[-1]

    # 加载 DRO 轨道
    dro_orbit = load_orbit_from_json(str(dro_file))
    with open(dro_file) as f:
        dro_data = json.load(f)
    dro_orbit.period = dro_data.get("properties", {}).get("period", None)

    _cpu = multiprocessing.cpu_count() or 1
    logger.info(f"\n优化配置:")
    logger.info(f"  并行: n_workers={n_workers}（None=逻辑CPU数 {_cpu}）, backend={PARALLEL_BACKEND}")
    logger.info(f"  α 范围: [{alpha_min}, {alpha_max}]")
    logger.info(f"  T 范围: [{t_min}, {t_max}] TU = [{t_min * TU:.1f}, {t_max * TU:.1f}] 天")
    logger.info(f"  t_ins 范围: [{t_ins_min}, {t_ins_max}]")
    logger.info(f"  DRO 周期: {dro_orbit.period:.4f} TU = {dro_orbit.period * TU:.2f} 天")
    logger.info(f"  速度平行性容差: {np.degrees(angle_tol):.2f}°")

    with open(search_file, encoding="utf-8") as f:
        search_data = json.load(f)

    # 兼容有/无 meta 的格式
    if isinstance(search_data, dict) and "results" in search_data:
        all_results = search_data["results"]
    else:
        all_results = search_data

    feasible_indexed: List[Tuple[int, Dict[str, Any]]] = [
        (i, r) for i, r in enumerate(all_results) if r.get("is_feasible")
    ]
    # 按 min_distance 排序，优先优化最近的
    feasible_indexed.sort(key=lambda x: x[1].get("min_distance", float("inf")))
    n_feasible_total = len(feasible_indexed)

    if top_k is not None:
        feasible_indexed = feasible_indexed[:top_k]
    if max_cases is not None:
        feasible_indexed = feasible_indexed[:max_cases]

    logger.info(f"\n可行解总数: {n_feasible_total}")
    logger.info(f"本次待优化: {len(feasible_indexed)}")

    if not feasible_indexed:
        logger.info("没有可行解，退出。")
        return

    pack_cfg = NlpPackConfig(
        alpha_min=float(alpha_min),
        alpha_max=float(alpha_max),
        t_min=float(t_min),
        t_max=float(t_max),
        t_ins_min=float(t_ins_min),
        t_ins_max=float(t_ins_max),
        earth_radius=float(EARTH_RADIUS),
        moon_radius=float(MOON_RADIUS),
        angle_tolerance=float(angle_tol),
    )

    output_dir = project_root / "output/transfer"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"optimization_geo_dro_{int(time.time())}.json"

    cpu_n = multiprocessing.cpu_count() or 1
    n_workers_req = n_workers if n_workers is not None else max(1, cpu_n)
    n_total = len(feasible_indexed)

    logger.info("\n" + "=" * 70)
    logger.info("开始 NLP 优化")
    logger.info("=" * 70)

    records: List[Dict[str, Any]] = []

    if n_workers_req == 1:
        for k, (global_idx, rec) in enumerate(feasible_indexed):
            try:
                row = optimize_one_case(rec, dro_orbit)
                records.append(row)
                nlp = row.get("nlp", {})
                pv = nlp.get("pos_violation", 1e10)
                pos_km = np.sqrt(max(0, float(pv))) * DU
                ov = nlp.get("objective_value", 0)
                logger.info(
                    f"  [{k+1}/{n_total}] ok={nlp.get('success')} "
                    f"dv={ov*VU:.0f} m/s pos={pos_km:.0f} km "
                    f"a={nlp.get('alpha', 0):.4f} T={nlp.get('transfer_time', 0):.1f}"
                )
            except Exception:
                records.append({"search_index": global_idx, "error": traceback.format_exc()})
    else:
        n_pool = min(n_workers_req, n_total)
        backend = PARALLEL_BACKEND.strip().lower()

        payloads = []
        for global_idx, rec in feasible_indexed:
            payloads.append({
                "idx": global_idx,
                "rec": rec,
                "dro_orbit": dro_orbit,
                "cfg": pack_cfg,
            })

        Executor = ProcessPoolExecutor if backend == "processes" else ThreadPoolExecutor
        with Executor(max_workers=n_pool) as ex:
            futures = [ex.submit(nlp_worker_packed, p) for p in payloads]
            from tqdm.auto import tqdm
            for fut in tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"NLP({backend}×{n_pool})",
                file=sys.stderr,
                dynamic_ncols=True,
            ):
                records.append(fut.result())

        records.sort(key=lambda x: x.get("search_index", 0))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "direction": "GEO_to_DRO",
                    "search_results_file": str(search_file),
                    "dro_file": str(dro_file),
                    "alpha_range": [alpha_min, alpha_max],
                    "transfer_time_range": [t_min, t_max],
                    "t_ins_range": [t_ins_min, t_ins_max],
                    "velocity_angle_tolerance_rad": angle_tol,
                    "nlp_solver": "scipy_root_lm+nm_fallback",
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
    # 过滤位置误差 < 100 km 且速度角度在容限内的有效解
    valid = []
    for r in successes:
        pv = r.get("nlp", {}).get("pos_violation", 1e10)
        pos_km = np.sqrt(max(0, float(pv))) * DU
        cos_a = r.get("nlp", {}).get("cos_angle", -1)
        if pos_km < 100 and cos_a >= np.cos(angle_tol):
            valid.append(r)

    logger.info(f"\n优化完成: {len(records)} 条, 成功 {len(successes)} 条, 有效 {len(valid)} 条 (pos < 100 km)")
    logger.info(f"结果已保存: {out_path}")

    if valid:
        best = min(valid, key=lambda r: r["nlp"]["objective_value"])
        b = best["nlp"]
        logger.info(f"\n最优解:")
        logger.info(f"  α = {b['alpha']:.6f}")
        logger.info(f"  T = {b['transfer_time']:.6f} TU ({b['transfer_time'] * TU:.2f} 天)")
        logger.info(f"  t_ins = {b['t_ins']:.6f} TU")
        logger.info(f"  Δv1 = {b['delta_v1']:.6f} VU ({b['delta_v1'] * VU:.1f} m/s)")
        logger.info(f"  Δv2 = {b['delta_v2']:.6f} VU ({b['delta_v2'] * VU:.1f} m/s)")
        logger.info(f"  Δv_total = {b['objective_value']:.6f} VU ({b['objective_value'] * VU:.1f} m/s)")
        pv = b.get('pos_violation', 0)
        pos_km = np.sqrt(max(0, float(pv))) * DU
        logger.info(f"  pos_err = {pos_km:.1f} km")
        logger.info(f"  angle = {b.get('angle_deg', 'N/A'):.4f} deg")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--alpha-min", "1.0",                         # alpha 搜索下界（ALPHA_MIN）
            "--alpha-max", "1.5",                         # alpha 搜索上界（ALPHA_MAX）
            "--t-min", "5.0",                             # 转移时间下界（T_MIN）
            "--t-max", "60.0",                            # 转移时间上界（T_MAX）
            "--t-ins-min", "0.0",                         # DRO 插入时间下界（T_INS_MIN）
            "--t-ins-max", "10.0",                        # DRO 插入时间上界（T_INS_MAX）
            "--nlp-maxiter", "100",                       # NLP 最大迭代次数（NLP_MAXITER）
            "--nlp-ftol", "1e-8",                         # NLP 函数容差（NLP_FTOL）
        ]
        logger.debug("使用代码内置调试参数")
    main()
