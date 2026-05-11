"""
LEO → DRO 网格搜索

从 LEO 出发，搜索到月球 DRO 的转移轨道。
复用 TransferSearch，departure=LEO（近似圆轨道），arrival=DRO。

LEO 比 GEO 更接近地球，速度更高，需要更大的 alpha 值才能到达月球。
转移时间可能更长。

运行: python -m tod.transfers.leo_to_dro.grid_search_leo_to_dro

Windows 多进程需要 ``if __name__ == "__main__"``。
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import time

from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import TransferSearch, load_orbit_from_json
from tod.commons.common import DU, MU, TU, VU
from e2m2e.orbits.leo import (
    R_LEO,
    V_CIRCULAR_LEO,
    T_LEO,
    LEO_ALT_KM,
    generate_leo_orbit_states,
)
import logging

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent


def generate_leo_orbit(n_points: int = 500) -> Orbit:
    """在 CR3BP 旋转系中生成 LEO 近似圆轨道。"""
    states = generate_leo_orbit_states(n_points)
    times = np.linspace(0, T_LEO, n_points, endpoint=False)

    orbit = Orbit(states, times)
    orbit.period = T_LEO
    return orbit


# =====================================================================
# 配置
# =====================================================================

# DRO 轨道文件默认值
DRO_FILE_DEFAULT = str(project_root / "output/dro/dro_31_3857864736.json")

# 搜索参数默认值
N_DEPARTURE = 200
N_ALPHA = 100
ALPHA_MIN = 1.2          # 略加速
ALPHA_MAX = 2.0          # 大幅加速
MAX_TRANSFER_TIME = 80.0  # 更长的转移时间（约 348 天）

INTERSECTION_THRESHOLD = 0.001
MIN_DISTANCE_THRESHOLD = 500.0 / DU  # LEO 远，放宽阈值
EARTH_RADIUS = 200.0 / DU
MOON_RADIUS = 100.0 / DU

INTEGRATION_DT = 1.0 / (24.0 * TU)
LEO_N_POINTS = 500


def parse_args():
    parser = argparse.ArgumentParser(description="LEO→DRO 转移轨道网格搜索")
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径")
    parser.add_argument("--n-departure", type=int, default=N_DEPARTURE, help="出发时间网格数")
    parser.add_argument("--n-alpha", type=int, default=N_ALPHA, help="alpha 网格密度")
    parser.add_argument("--alpha-min", type=float, default=ALPHA_MIN, help="alpha 搜索下界")
    parser.add_argument("--alpha-max", type=float, default=ALPHA_MAX, help="alpha 搜索上界")
    parser.add_argument("--max-transfer-time", type=float, default=MAX_TRANSFER_TIME, help="最大转移时间（无量纲）")
    parser.add_argument("--intersection-threshold", type=float, default=INTERSECTION_THRESHOLD, help="相交判定距离阈值")
    parser.add_argument("--min-distance", type=float, default=MIN_DISTANCE_THRESHOLD, help="候选解最小距离阈值")
    parser.add_argument("--earth-radius", type=float, default=EARTH_RADIUS, help="地球碰撞检测半径")
    parser.add_argument("--moon-radius", type=float, default=MOON_RADIUS, help="月球碰撞检测半径")
    parser.add_argument("--leo-n-points", type=int, default=LEO_N_POINTS, help="LEO 轨道采样点数")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # =========================================================================
    # 初始化
    # =========================================================================
    for _k in [
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
    ]:
        os.environ[_k] = "1"

    # 查找 DRO 文件（CLI > 环境变量 > 默认值）
    dro_file = Path(args.dro_file or os.environ.get("DRO_FILE", DRO_FILE_DEFAULT))
    n_departure = args.n_departure
    n_alpha = args.n_alpha
    alpha_min = args.alpha_min
    alpha_max = args.alpha_max
    max_transfer_time = args.max_transfer_time
    intersection_threshold = args.intersection_threshold
    min_distance_threshold = args.min_distance
    earth_radius = args.earth_radius
    moon_radius = args.moon_radius
    leo_n_points = args.leo_n_points

    if not dro_file.exists():
        dro_dir = project_root / "output/dro"
        dro_files = sorted(dro_dir.glob("dro_31_*.json"))
        if not dro_files:
            logger.info("错误：找不到 DRO 轨道文件！")
            return
        dro_file = dro_files[-1]
        logger.info(f"使用 DRO 文件: {dro_file}")

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = INTEGRATION_DT

    # 加载 DRO
    dro_orbit = load_orbit_from_json(str(dro_file))
    with open(dro_file) as f:
        dro_data = json.load(f)
    dro_orbit.period = dro_data.get("properties", {}).get("period", None)

    # 生成 LEO 轨道
    leo_orbit = generate_leo_orbit(n_points=leo_n_points)

    # =========================================================================
    # 参数报告
    # =========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("LEO → DRO 网格搜索")
    logger.info("=" * 70)
    logger.info(f"  LEO: 高度 {LEO_ALT_KM:.0f} km, R={R_LEO:.6f} DU = {R_LEO * DU:.0f} km")
    logger.info(f"       V_circ={V_CIRCULAR_LEO:.4f} VU = {V_CIRCULAR_LEO * VU:.0f} m/s")
    logger.info(f"       T={T_LEO:.6f} TU = {T_LEO * TU:.4f} 天")
    logger.info(f"  DRO: {dro_orbit.states.shape[0]} 点, "
          f"周期={dro_orbit.period:.4f} TU = {dro_orbit.period * TU:.2f} 天")
    logger.info(f"  α: [{alpha_min}, {alpha_max}], n={n_alpha}")
    logger.info(f"  出发点: {n_departure}")
    logger.info(f"  最大转移时间: {max_transfer_time:.1f} TU = {max_transfer_time * TU:.1f} 天")
    logger.info("=" * 70)

    # =========================================================================
    # 执行搜索
    # =========================================================================
    searcher = TransferSearch(dynamics)
    results = searcher.search(
        departure_orbit=leo_orbit,
        arrival_orbit=dro_orbit,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        n_alpha=n_alpha,
        n_departure=n_departure,
        max_transfer_time=max_transfer_time,
        intersection_threshold=intersection_threshold,
        min_distance_threshold=min_distance_threshold,
        collision_earth_radius=earth_radius,
        collision_moon_radius=moon_radius,
        integration_dt=INTEGRATION_DT,
        verbose=True,
        n_workers=None,
    )

    feasible = searcher.get_feasible_results()
    logger.info(f"\n搜索完成: {len(results)} 个候选解, {len(feasible)} 个可行解")

    # =========================================================================
    # 保存
    # =========================================================================
    output_dir = project_root / "output/transfer"
    output_file = output_dir / (
        f"search_leo_dro_{n_departure}-{n_alpha}-{alpha_min:g}-{alpha_max:g}-"
        f"{max_transfer_time:.4f}_{int(time.time())}.json"
    )

    def _json_safe(x):
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

    def serialize_result(r):
        serialized: dict = _json_safe({  # type: ignore[assignment]
            "departure_time_index": r.get("departure_time_index"),
            "departure_time": r.get("departure_time"),
            "alpha": r.get("alpha"),
            "transfer_time": r.get("transfer_time"),
            "dv_departure": r.get("dv_departure"),
            "dv_arrival": r.get("dv_arrival"),
            "min_distance": r.get("min_distance"),
            "intersection_found": r.get("intersection_found"),
            "collision_found": r.get("collision_found"),
            "collision_body": r.get("collision_body"),
            "local_minimum_found": r.get("local_minimum_found"),
            "local_minimum_distance": r.get("local_minimum_distance"),
            "status": r.get("status"),
            "is_feasible": searcher._is_feasible(r),
        })
        departure_state = r.get("departure_state")
        if departure_state is not None:
            serialized["departure_state"] = _json_safe(departure_state)
        return serialized

    results_data = [serialize_result(r) for r in results]

    output_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "direction": "LEO_to_DRO",
        "dro_file": str(dro_file),
        "leo_altitude_km": LEO_ALT_KM,
        "leo_radius": float(R_LEO),
        "leo_period": float(T_LEO),
        "search_params": {
            "n_departure": n_departure,
            "n_alpha": n_alpha,
            "alpha_min": alpha_min,
            "alpha_max": alpha_max,
            "max_transfer_time": max_transfer_time,
            "intersection_threshold": intersection_threshold,
            "min_distance_threshold": min_distance_threshold,
        },
        "n_total": len(results_data),
        "n_feasible": len(feasible),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results_data}, f, indent=2, ensure_ascii=False)

    logger.info(f"\n结果已保存: {output_file}")
    logger.info(f"  总候选解: {len(results_data)}, 可行解: {len(feasible)}")

    if feasible:
        sorted_f = sorted(feasible, key=lambda r: r.get("min_distance", float("inf")))
        logger.info("\n可行解摘要（前 10）:")
        for i, r in enumerate(sorted_f[:10]):
            md = r.get("min_distance", float("inf"))
            dv = r.get("dv_departure", 0)
            tt = r.get("transfer_time", 0)
            al = r.get("alpha", 0)
            logger.info(f"  #{i+1}: dep_idx={r.get('departure_time_index')}, "
                  f"α={al:.4f}, T={tt:.2f} TU ({tt * TU:.1f} 天), "
                  f"dv_dep={dv:.4f} VU ({dv * VU:.0f} m/s), "
                  f"min_dist={md:.6f} DU ({md * DU:.0f} km), "
                  f"相交={r.get('intersection_found', False)}")
    else:
        logger.info("\n无可行解。分析距离分布...")
        if results:
            dists = [r.get("min_distance", float("inf")) for r in results
                     if r.get("min_distance", float("inf")) < float("inf")]
            if dists:
                logger.info(f"  最小距离: {min(dists):.6f} DU = {min(dists) * DU:.0f} km")
                logger.info(f"  建议: 调整 alpha 范围或增加积分时间")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--n-departure", "200",                       # 出发时间网格数（N_DEPARTURE）
            "--n-alpha", "100",                           # alpha 网格密度（N_ALPHA）
            "--alpha-min", "1.2",                         # alpha 搜索下界（ALPHA_MIN）
            "--alpha-max", "2.0",                         # alpha 搜索上界（ALPHA_MAX）
            "--max-transfer-time", "80.0",                # 最大转移时间（MAX_TRANSFER_TIME）
            "--intersection-threshold", "0.001",          # 相交判定距离（INTERSECTION_THRESHOLD）
            "--min-distance", "0.0013007114891845839",    # 候选解最小距离（500.0/DU）
            "--earth-radius", "0.0005202845956738336",    # 地球碰撞半径（200.0/DU）
            "--moon-radius", "0.0002601422978369168",     # 月球碰撞半径（100.0/DU）
            "--leo-n-points", "500",                      # LEO 轨道采样点数（LEO_N_POINTS）
        ]
        logger.debug("使用代码内置调试参数")
    main()
