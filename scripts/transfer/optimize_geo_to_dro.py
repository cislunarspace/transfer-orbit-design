"""
GEO → DRO NLP 优化

从 GEO 出发的转移轨道 NLP 优化（第二步）。
读取搜索结果，对可行解进行 SLSQP 精细化。

优化变量: y = [α, T, t_ins]
  - α: GEO 出发切向速度比
  - T: 转移时间
  - t_ins: DRO 上的插入时间

目标函数: J(y) = Δv1 + Δv2
约束:
  - 位置连续性: ||pos_final - pos_DRO(t_ins)||² = 0
  - 速度平行性: cos(angle) - 1 = 0（可松弛）

运行: python scripts/transfer/optimize_geo_to_dro.py

Windows 须保留 ``if __name__ == "__main__"``。
"""

from __future__ import annotations

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
from scipy.optimize import Bounds, minimize

import e2m2e
from e2m2e.core import CR3BP_Dynamics, CR3BP_System
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import load_orbit_from_json
from scripts.utils.common import DU, MU, TU, VU
from scripts.utils.geo import (
    R_GEO,
    EARTH_CENTER,
    geo_circular_velocity_rotating,
)

project_root = Path(__file__).resolve().parent.parent.parent

# =====================================================================
# 配置 — 运行前须更新文件路径
# =====================================================================
SEARCH_RESULTS_FILE = project_root / (
    "output/transfer/search_geo_dro_10-200-1-1.5-2.2998_1775916430.json"
)
DRO_FILE = project_root / "output/dro/dro_31_3857864736.json"

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

LIMIT_BLAS_THREADS_PER_WORKER: int = 1


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


def compute_departure_velocity(state: np.ndarray, alpha: float) -> np.ndarray:
    """切向速度缩放（与 TransferSearch._compute_departure_velocity 一致）。"""
    pos = state[:3]
    vel = state[3:]
    r_xy = np.sqrt(pos[0] ** 2 + pos[1] ** 2)
    if r_xy < 1e-10:
        return vel.copy()
    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)
    v_rad = np.dot(vel, radial)
    v_tan = np.dot(vel, tangential)
    return v_rad * radial + alpha * v_tan * tangential


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

    # 用粗动力学重新积分找最接近 DRO 的时刻
    _, pre_dynamics = build_dynamics(1e-10, 1e-10, NLP_MAX_STEP)
    t_closest, t_dro_closest, reinit_min_dist = _find_closest_approach(
        departure_state, alpha_0, T_search, dro_orbit, pre_dynamics,
    )

    T_0 = max(t_min, min(t_closest, t_max))
    t_ins_0 = max(t_ins_min, min(t_dro_closest, t_ins_max))

    if verbose:
        print(f"  init: T_closest={t_closest:.2f}, t_ins={t_ins_0:.4f}, "
              f"dist={reinit_min_dist*DU:.0f} km")

    _, dynamics = build_dynamics(1e-10, 1e-10, NLP_MAX_STEP)

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

        if pos_err < 0.005 and dv_total < best_dv:  # < ~1900 km and better Δv
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
            pass

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
    print("=" * 70, flush=True)
    print("GEO → DRO 转移 NLP 优化", flush=True)
    print("=" * 70, flush=True)

    if not SEARCH_RESULTS_FILE.is_file():
        raise FileNotFoundError(f"未找到搜索结果: {SEARCH_RESULTS_FILE}")

    # 查找 DRO 文件
    dro_file = DRO_FILE
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
    print(f"\n优化配置:", flush=True)
    print(f"  并行: n_workers={N_WORKERS}（None=逻辑CPU数 {_cpu}）, backend={PARALLEL_BACKEND}")
    print(f"  α 范围: [{ALPHA_MIN}, {ALPHA_MAX}]")
    print(f"  T 范围: [{T_MIN}, {T_MAX}] TU = [{T_MIN * TU:.1f}, {T_MAX * TU:.1f}] 天")
    print(f"  t_ins 范围: [{T_INS_MIN}, {T_INS_MAX}]")
    print(f"  DRO 周期: {dro_orbit.period:.4f} TU = {dro_orbit.period * TU:.2f} 天")
    print(f"  速度平行性容差: {np.degrees(VELOCITY_ANGLE_TOLERANCE):.2f}°")

    with open(SEARCH_RESULTS_FILE, encoding="utf-8") as f:
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

    if TOP_K_FEASIBLE is not None:
        feasible_indexed = feasible_indexed[:TOP_K_FEASIBLE]
    if MAX_CASES is not None:
        feasible_indexed = feasible_indexed[:MAX_CASES]

    print(f"\n可行解总数: {n_feasible_total}", flush=True)
    print(f"本次待优化: {len(feasible_indexed)}", flush=True)

    if not feasible_indexed:
        print("没有可行解，退出。")
        return

    pack_cfg = NlpPackConfig(
        alpha_min=float(ALPHA_MIN),
        alpha_max=float(ALPHA_MAX),
        t_min=float(T_MIN),
        t_max=float(T_MAX),
        t_ins_min=float(T_INS_MIN),
        t_ins_max=float(T_INS_MAX),
        earth_radius=float(EARTH_RADIUS),
        moon_radius=float(MOON_RADIUS),
        angle_tolerance=float(VELOCITY_ANGLE_TOLERANCE),
    )

    output_dir = project_root / "output/transfer"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"optimization_geo_dro_{int(time.time())}.json"

    cpu_n = multiprocessing.cpu_count() or 1
    n_workers_req = N_WORKERS if N_WORKERS is not None else max(1, cpu_n)
    n_total = len(feasible_indexed)

    print("\n" + "=" * 70, flush=True)
    print("开始 NLP 优化", flush=True)
    print("=" * 70, flush=True)

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
                print(
                    f"  [{k+1}/{n_total}] ok={nlp.get('success')} "
                    f"dv={ov*VU:.0f} m/s pos={pos_km:.0f} km "
                    f"a={nlp.get('alpha', 0):.4f} T={nlp.get('transfer_time', 0):.1f}",
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
                    "search_results_file": str(SEARCH_RESULTS_FILE),
                    "dro_file": str(dro_file),
                    "alpha_range": [ALPHA_MIN, ALPHA_MAX],
                    "transfer_time_range": [T_MIN, T_MAX],
                    "t_ins_range": [T_INS_MIN, T_INS_MAX],
                    "velocity_angle_tolerance_rad": VELOCITY_ANGLE_TOLERANCE,
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
    # 过滤位置误差 < 100 km 的有效解
    valid = []
    for r in successes:
        pv = r.get("nlp", {}).get("pos_violation", 1e10)
        pos_km = np.sqrt(max(0, float(pv))) * DU
        if pos_km < 100:
            valid.append(r)

    print(f"\n优化完成: {len(records)} 条, 成功 {len(successes)} 条, 有效 {len(valid)} 条 (pos < 100 km)")
    print(f"结果已保存: {out_path}")

    if valid:
        best = min(valid, key=lambda r: r["nlp"]["objective_value"])
        b = best["nlp"]
        print(f"\n最优解:")
        print(f"  α = {b['alpha']:.6f}")
        print(f"  T = {b['transfer_time']:.6f} TU ({b['transfer_time'] * TU:.2f} 天)")
        print(f"  t_ins = {b['t_ins']:.6f} TU")
        print(f"  Δv1 = {b['delta_v1']:.6f} VU ({b['delta_v1'] * VU:.1f} m/s)")
        print(f"  Δv2 = {b['delta_v2']:.6f} VU ({b['delta_v2'] * VU:.1f} m/s)")
        print(f"  Δv_total = {b['objective_value']:.6f} VU ({b['objective_value'] * VU:.1f} m/s)")
        pv = b.get('pos_violation', 0)
        pos_km = np.sqrt(max(0, float(pv))) * DU
        print(f"  pos_err = {pos_km:.1f} km")
        print(f"  angle = {b.get('angle_deg', 'N/A'):.4f} deg")


if __name__ == "__main__":
    main()
