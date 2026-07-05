"""optimize_dro_to_geo 转移设计脚本。

本模块读取已生成的轨道或搜索结果 JSON，在地月 CR3BP 单位体系中执行搜索、验证或 NLP 优化。网格类脚本输出候选转移，优化类脚本读取候选并最小化速度增量或插入误差，结果写入 output/transfer 相关目录。

运行示例:
    .. code-block:: bash

       uv run python -m tod.transfers.dro_to_geo.optimize_dro_to_geo --help
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
from scipy.optimize import minimize, root
from tqdm.auto import tqdm

from e2m2e.core import CR3BP_Dynamics, CR3BP_System
from tod.commons.constants import DU, MU, TU, VU
from tod.transfers.optimize_config import apply_blas_env_for_child_processes, blas_threads_per_worker
from e2m2e.orbits.geo import (
    R_GEO,
    EARTH_CENTER,
    check_collision,
    compute_departure_velocity,
    compute_geo_dv2,
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


USE_TQDM = os.environ.get("OPTIMIZE_NO_TQDM", "").lower() not in ("1", "true", "yes")


def parse_args():
    """解析命令行参数。
    
    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="DRO→GEO 转移 NLP 优化", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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
# 辅助函数
# =====================================================================


def build_dynamics(
    integrator: str, rtol: float, atol: float, max_step: float, mu: float
):
    """构建脚本所需的动力学模型。
    
    Args:
        integrator: 积分器类型。
        rtol: 相对容差。
        atol: 绝对容差。
        max_step: 最大步长。
        mu: 质量比。
    
    Returns:
        (system, dynamics) 元组。
    """
    system = CR3BP_System(mu=mu, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = integrator
    dynamics.rtol = rtol
    dynamics.atol = atol
    dynamics.max_step = max_step
    return system, dynamics


def forward_integrate_nlp(dynamics, initial_state, transfer_time):
    """对 NLP 优化过程进行前向积分。
    
    Args:
        dynamics: 动力学对象。
        initial_state: 初始状态。
        transfer_time: 转移时间。
    
    Returns:
        (states, times) 元组。
    """
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
# 残差评估
# =====================================================================


def _nlp_eval(y, departure_state, dynamics, mu, earth_radius, moon_radius):
    """计算 y = [alpha, T] 的 2D 残差与代价。

    残差 F(y) = [r_xy(终点) - R_GEO, z_rel(终点)] —— 赤道圆约束。
    碰撞检测：穿地球或月球的轨迹标记 collided=True，由调用方丢弃。
    """
    alpha, T = y
    v_dep = compute_departure_velocity(departure_state, alpha)
    dv1 = float(np.linalg.norm(v_dep - departure_state[3:]))
    state0 = np.concatenate([departure_state[:3], v_dep])

    try:
        states, times = forward_integrate_nlp(dynamics, state0, T)
    except (FloatingPointError, ValueError, RuntimeError, np.linalg.LinAlgError):
        # 数值积分发散时返回哨兵；编程错误（TypeError 等）让它抛
        return {"empty": True, "residual": np.array([1e6, 1e6])}

    if len(states) == 0:
        return {"empty": True, "residual": np.array([1e6, 1e6])}

    collided, body, _ = check_collision(states, mu, earth_radius, moon_radius)

    final_state = states[-1]
    final_pos = final_state[:3]
    r_rel = final_pos - EARTH_CENTER
    r_xy = float(np.sqrt(r_rel[0] ** 2 + r_rel[1] ** 2))
    z_rel = float(r_rel[2])
    dist = float(np.linalg.norm(r_rel))

    residual = np.array([r_xy - R_GEO, z_rel])
    dv2 = compute_geo_dv2(final_state)

    return {
        "empty": False,
        "collided": collided,
        "collision_body": body,
        "states": states,
        "times": times,
        "final_state": final_state,
        "dv1": dv1,
        "dv2": dv2,
        "objective": dv1 + dv2,
        "residual": residual,
        "pos_violation": float(residual @ residual),
        "dist_from_earth": dist,
        "r_xy": r_xy,
        "z_rel": z_rel,
    }


# =====================================================================
# 单案例求解：α 扫描求根 + Nelder-Mead 回退
# =====================================================================


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
    """执行转移优化计算。
    
    Args:
        rec: 调用方传入的参数值。
        dynamics: 调用方传入的参数值。
        mu: 调用方传入的参数值。
        alpha_min: 调用方传入的参数值。
        alpha_max: 调用方传入的参数值。
        t_min: 调用方传入的参数值。
        t_max: 调用方传入的参数值。
        earth_radius: 调用方传入的参数值。
        moon_radius: 调用方传入的参数值。
        verbose: 调用方传入的参数值。
    
    Returns:
        函数执行结果。
    """
    departure_state = np.array(rec["departure_state"], dtype=float)
    alpha_0 = float(rec["alpha"])
    T_0 = float(rec["transfer_time"])

    nlp_system = CR3BP_System(mu=mu, primary="earth", secondary="moon")
    nlp_dynamics = CR3BP_Dynamics(system=nlp_system)
    nlp_dynamics.integrator = dynamics.integrator
    nlp_dynamics.rtol = NLP_RTOL
    nlp_dynamics.atol = NLP_ATOL
    nlp_dynamics.max_step = NLP_MAX_STEP

    def _eval(y):
        return _nlp_eval(y, departure_state, nlp_dynamics, mu, earth_radius, moon_radius)

    def _residual_2d(y):
        a, T = float(y[0]), float(y[1])
        if not (alpha_min <= a <= alpha_max and t_min <= T <= t_max):
            return np.array([1e6, 1e6])
        c = _eval([a, T])
        if c["empty"]:
            return np.array([1e6, 1e6])
        return c["residual"]

    def _solve_2d(a_init, T_init):
        try:
            sol = root(
                _residual_2d,
                [a_init, T_init],
                method="lm",
                options={"maxiter": NLP_MAXITER, "xtol": 1e-12},
            )
            a_sol, T_sol = float(sol.x[0]), float(sol.x[1])
            res_norm_sq = float(sol.fun @ sol.fun)
            in_box = alpha_min <= a_sol <= alpha_max and t_min <= T_sol <= t_max
            ok = sol.success and res_norm_sq < 1e-8 and in_box
            return a_sol, T_sol, ok
        # 仅捕获数值意义上的失败（积分发散/线性代数奇异）；编程错误应向上抛
        except (FloatingPointError, ValueError, RuntimeError, np.linalg.LinAlgError):
            return a_init, T_init, False

    a_lo = max(alpha_min, alpha_0 - 0.05)
    a_hi = min(alpha_max, alpha_0 + 0.05)
    alpha_starts = np.linspace(a_lo, a_hi, 5) if a_hi > a_lo else np.array([alpha_0])

    best = None
    best_dv = float("inf")

    # 转移时间惩罚权重（无量纲）：objective = dv + w * T
    # w = 0.1 时，T = 5 TU 的惩罚约 0.5 VU，与 dv 量级相当，
    # 使短转移时间解在总目标中占优。
    TIME_PENALTY_WEIGHT = 0.1

    # 多组 T_init：搜索结果的 T_0 + 短转移时间尝试
    T_inits = [T_0, 5.0, 10.0, 15.0, 20.0]

    for a_start in alpha_starts:
        for T_init in T_inits:
            a_sol, T_sol, ok = _solve_2d(float(a_start), T_init)
            if not ok:
                continue
            c = _eval([a_sol, T_sol])
            if c["empty"] or c["collided"]:
                continue
            dv_total = c["dv1"] + c["dv2"]
            obj = dv_total + TIME_PENALTY_WEIGHT * T_sol
            if obj < best_dv:
                best_dv = obj
                best = {"alpha": a_sol, "T": T_sol, "c": c}

    used_fallback = False
    if best is None:
        used_fallback = True

        def _nm_obj(y):
            a, T = y
            if not (alpha_min <= a <= alpha_max and t_min <= T <= t_max):
                return 1e10
            c = _eval([float(a), float(T)])
            if c["empty"]:
                return 1e10
            return c["pos_violation"]

        try:
            nm_res = minimize(
                _nm_obj,
                [alpha_0, T_0],
                method="Nelder-Mead",
                options={"maxiter": 200, "adaptive": True, "xatol": 1e-8, "fatol": 1e-10},
            )
            c = _eval([float(nm_res.x[0]), float(nm_res.x[1])])
            if not c["empty"] and not c["collided"] and c["pos_violation"] < 1e-6:
                best = {"alpha": float(nm_res.x[0]), "T": float(nm_res.x[1]), "c": c}
        except (FloatingPointError, ValueError, RuntimeError, np.linalg.LinAlgError):
            # Nelder-Mead 兜底只在数值失败时跳过；编程错误让它抛
            if verbose:
                logger.info(f"    Nelder-Mead 兜底失败 idx={rec.get('departure_time_index', '?')}")

    base_payload = {
        "search_index": rec.get("departure_time_index", -1),
        "alpha": alpha_0,
        "transfer_time": T_0,
        "departure_state": rec["departure_state"],
        "is_feasible": rec.get("is_feasible"),
        "dv_departure": rec.get("dv_departure"),
        "search_min_distance": rec.get("min_distance"),
    }

    if best is None:
        base_payload["nlp"] = {
            "success": False,
            "message": "root-find + Nelder-Mead 均未收敛或被碰撞过滤拒绝",
            "used_fallback": used_fallback,
        }
        return base_payload

    c = best["c"]
    base_payload["nlp"] = {
        "success": True,
        "alpha": best["alpha"],
        "transfer_time": best["T"],
        "objective_value": c["objective"],
        "delta_v1": c["dv1"],
        "delta_v2": c["dv2"],
        "dist_from_earth": c["dist_from_earth"],
        "r_xy": c["r_xy"],
        "z_rel": c["z_rel"],
        "pos_violation": c["pos_violation"],
        "collided": False,
        "used_fallback": used_fallback,
        "message": "ok",
    }
    return base_payload


# =====================================================================
# 并行工作器
# =====================================================================


@dataclass
class NlpPackConfig:
    """保存 NlpPackConfig 的配置字段。
    
    该类由脚本或 GUI 工作流内部使用，字段含义与调用处的参数保持一致。
    """
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
    """打包后的 NLP worker 函数。
    
    Args:
        payload: 包含索引、记录和配置的打包数据。
    
    Returns:
        优化结果字典。
    """
    payload["idx"]
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
# 主流程
# =====================================================================


def main() -> None:
    """执行脚本主流程。
    
    Returns:
        None。
    
    Raises:
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
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
    logger.info("\n优化配置:")
    logger.info(f"  并行: n_workers={n_workers}（None=逻辑CPU数 {_cpu}）, backend={PARALLEL_BACKEND}")
    logger.info(f"  α 范围: [{alpha_min}, {alpha_max}]")
    logger.info(f"  T 范围: [{t_min}, {t_max}]")
    logger.info(f"  GEO 约束: |r - r_earth| = {R_GEO:.6f} DU")

    with open(search_file, encoding="utf-8") as f:
        search_data = json.load(f)

    # 兼容有/无 meta 的格式（与 geo_to_dro 一致）
    if isinstance(search_data, dict) and "results" in search_data:
        all_results = search_data["results"]
    else:
        all_results = search_data

    feasible_indexed: List[Tuple[int, Dict[str, Any]]] = [
        (i, r) for i, r in enumerate(all_results) if r.get("is_feasible")
    ]
    feasible_indexed.sort(key=lambda x: x[1].get("min_distance", float("inf")))
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
                logger.info(
                    f"  case {k + 1}/{n_total} (idx={global_idx}) | "
                    f"success={nlp.get('success')} ΔV={nlp.get('objective_value', 'N/A')}"
                )
            except (FloatingPointError, ValueError, RuntimeError, np.linalg.LinAlgError):
                # 主循环逐 case 捕获数值失败；编程错误让它抛
                records.append({"search_index": global_idx, "error": traceback.format_exc()})
    else:
        n_pool = min(n_workers_req, n_total)
        backend = PARALLEL_BACKEND.strip().lower()

        if backend == "processes":
            apply_blas_env_for_child_processes(blas_threads_per_worker())

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
                    "geo_constraint": "equatorial_circle (r_xy=R_GEO, z=0)",
                    "solver": "scipy_root_lm + nelder_mead_fallback",
                    "feasible_sort_key": "min_distance",
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
        logger.info("\n最优解:")
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


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='transfer',
    name='optimize_dro_to_geo',
    description='优化',
    script_path='tod/transfers/dro_to_geo/optimize_dro_to_geo.py',
    output_dir='output/transfer',
    group_label='DRO→GEO',
    cli_params=[
        CliParam('--search-file', '搜索结果文件', 'str', '', help='网格搜索结果 JSON 文件路径。', file_category='transfer'),
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--alpha-min', 'alpha 下界', 'float', '0.5', help='alpha 搜索下界。'),
        CliParam('--alpha-max', 'alpha 上界', 'float', '2.5', help='alpha 搜索上界。'),
        CliParam('--t-min', '转移时间下界', 'float', '0.5', help='转移时间下界（无量纲）。', unit_group='time', default_unit='days'),
        CliParam('--t-max', '转移时间上界', 'float', '30.0', help='转移时间上界（无量纲）。', unit_group='time', default_unit='days'),
        CliParam('--nlp-maxiter', 'NLP 最大迭代', 'int', '100', help='NLP 最大迭代次数。'),
        CliParam('--nlp-ftol', 'NLP 函数容差', 'float', '1e-8', help='NLP 函数容差。'),
        CliParam('--top-k', '前 K 个可行解', 'int', '', help='取前 K 个可行解优化。'),
        CliParam('--max-cases', '最大案例数', 'int', '', help='最大优化案例数。'),
        CliParam('--n-workers', '并行 worker 数', 'int', '', help='并行 worker 数。'),
    ],
)
