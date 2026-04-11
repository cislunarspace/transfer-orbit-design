"""
LEO → DRO 网格搜索

从 LEO 出发，搜索到月球 DRO 的转移轨道。
复用 TransferSearch，departure=LEO（近似圆轨道），arrival=DRO。

LEO 比 GEO 更接近地球，速度更高，需要更大的 alpha 值才能到达月球。
转移时间可能更长。

运行: python scripts/transfer/grid_search_leo_to_dro.py

Windows 多进程需要 ``if __name__ == "__main__"``。
"""

import json
import os
from pathlib import Path

import numpy as np
import time

import e2m2e
from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import TransferSearch, load_orbit_from_json
from scripts.utils.common import DU, MU, TU, VU
from scripts.utils.leo import (
    R_LEO,
    V_CIRCULAR_LEO,
    T_LEO,
    LEO_ALT_KM,
    EARTH_CENTER,
    generate_leo_orbit_states,
    leo_circular_velocity_rotating,
)

project_root = Path(__file__).resolve().parent.parent.parent


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

DRO_FILE = project_root / "output/dro/dro_31_3857864736.json"

# 搜索参数
# LEO 圆速度 ~7.5 VU，逃逸速度 ~10.6 VU，alpha ≈ 10.6/7.5 ≈ 1.41
# 但 LEO 附近受地球引力主导，实际需要的 alpha 可能更大
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


def main() -> None:
    # =========================================================================
    # 初始化
    # =========================================================================
    for _k in [
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
    ]:
        os.environ[_k] = "1"

    # 查找 DRO 文件
    dro_file = DRO_FILE
    if not dro_file.exists():
        dro_dir = project_root / "output/dro"
        dro_files = sorted(dro_dir.glob("dro_31_*.json"))
        if not dro_files:
            print("错误：找不到 DRO 轨道文件！")
            return
        dro_file = dro_files[-1]
        print(f"使用 DRO 文件: {dro_file}")

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
    leo_orbit = generate_leo_orbit(n_points=LEO_N_POINTS)

    # =========================================================================
    # 参数报告
    # =========================================================================
    print("\n" + "=" * 70)
    print("LEO → DRO 网格搜索")
    print("=" * 70)
    print(f"  LEO: 高度 {LEO_ALT_KM:.0f} km, R={R_LEO:.6f} DU = {R_LEO * DU:.0f} km")
    print(f"       V_circ={V_CIRCULAR_LEO:.4f} VU = {V_CIRCULAR_LEO * VU:.0f} m/s")
    print(f"       T={T_LEO:.6f} TU = {T_LEO * TU:.4f} 天")
    print(f"  DRO: {dro_orbit.states.shape[0]} 点, "
          f"周期={dro_orbit.period:.4f} TU = {dro_orbit.period * TU:.2f} 天")
    print(f"  α: [{ALPHA_MIN}, {ALPHA_MAX}], n={N_ALPHA}")
    print(f"  出发点: {N_DEPARTURE}")
    print(f"  最大转移时间: {MAX_TRANSFER_TIME:.1f} TU = {MAX_TRANSFER_TIME * TU:.1f} 天")
    print("=" * 70)

    # =========================================================================
    # 执行搜索
    # =========================================================================
    searcher = TransferSearch(dynamics)
    results = searcher.search(
        departure_orbit=leo_orbit,
        arrival_orbit=dro_orbit,
        alpha_min=ALPHA_MIN,
        alpha_max=ALPHA_MAX,
        n_alpha=N_ALPHA,
        n_departure=N_DEPARTURE,
        max_transfer_time=MAX_TRANSFER_TIME,
        intersection_threshold=INTERSECTION_THRESHOLD,
        min_distance_threshold=MIN_DISTANCE_THRESHOLD,
        collision_earth_radius=EARTH_RADIUS,
        collision_moon_radius=MOON_RADIUS,
        integration_dt=INTEGRATION_DT,
        verbose=True,
        n_workers=None,
    )

    feasible = searcher.get_feasible_results()
    print(f"\n搜索完成: {len(results)} 个候选解, {len(feasible)} 个可行解")

    # =========================================================================
    # 保存
    # =========================================================================
    output_dir = project_root / "output/transfer"
    output_file = output_dir / (
        f"search_leo_dro_{N_DEPARTURE}-{N_ALPHA}-{ALPHA_MIN:g}-{ALPHA_MAX:g}-"
        f"{MAX_TRANSFER_TIME:.4f}_{int(time.time())}.json"
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
        serialized = _json_safe({
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
            "n_departure": N_DEPARTURE,
            "n_alpha": N_ALPHA,
            "alpha_min": ALPHA_MIN,
            "alpha_max": ALPHA_MAX,
            "max_transfer_time": MAX_TRANSFER_TIME,
            "intersection_threshold": INTERSECTION_THRESHOLD,
            "min_distance_threshold": MIN_DISTANCE_THRESHOLD,
        },
        "n_total": len(results_data),
        "n_feasible": len(feasible),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results_data}, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存: {output_file}")
    print(f"  总候选解: {len(results_data)}, 可行解: {len(feasible)}")

    if feasible:
        sorted_f = sorted(feasible, key=lambda r: r.get("min_distance", float("inf")))
        print("\n可行解摘要（前 10）:")
        for i, r in enumerate(sorted_f[:10]):
            md = r.get("min_distance", float("inf"))
            dv = r.get("dv_departure", 0)
            tt = r.get("transfer_time", 0)
            al = r.get("alpha", 0)
            print(f"  #{i+1}: dep_idx={r.get('departure_time_index')}, "
                  f"α={al:.4f}, T={tt:.2f} TU ({tt * TU:.1f} 天), "
                  f"dv_dep={dv:.4f} VU ({dv * VU:.0f} m/s), "
                  f"min_dist={md:.6f} DU ({md * DU:.0f} km), "
                  f"相交={r.get('intersection_found', False)}")
    else:
        print("\n无可行解。分析距离分布...")
        if results:
            dists = [r.get("min_distance", float("inf")) for r in results
                     if r.get("min_distance", float("inf")) < float("inf")]
            if dists:
                print(f"  最小距离: {min(dists):.6f} DU = {min(dists) * DU:.0f} km")
                print(f"  建议: 调整 alpha 范围或增加积分时间")


if __name__ == "__main__":
    main()
