"""
GEO → DRO 网格搜索

从 GEO 出发，搜索到月球 DRO 的转移轨道。
复用 TransferSearch，departure=GEO（近似圆轨道），arrival=DRO。

运行: python scripts/transfer/grid_search_geo_to_dro.py

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
from scripts.utils.geo import (
    R_GEO,
    V_CIRCULAR_GEO,
    T_GEO,
    EARTH_CENTER,
    geo_circular_velocity_rotating,
)

project_root = Path(__file__).resolve().parent.parent.parent


# =====================================================================
# 配置
# =====================================================================

# DRO 轨道文件（支持通过环境变量 DRO_FILE 覆盖）
DRO_FILE = Path(os.environ.get("DRO_FILE", str(project_root / "output/dro/dro_31_3857864736.json")))

# 搜索参数（基于预研结果调整）
N_DEPARTURE = 10       # GEO 上的出发点数量
N_ALPHA = 200           # alpha 方向网格密度
ALPHA_MIN = 1.0         # 切向速度比下界（1.0=不加速）
ALPHA_MAX = 1.5         # 切向速度比上界（预研发现有效范围 1.37-1.42）
MAX_TRANSFER_TIME = 10.0 / TU  # 最大转移时间 (TU)

# 检测阈值
INTERSECTION_THRESHOLD = 100.0 / DU  # 相交判定距离 (DU)
MIN_DISTANCE_THRESHOLD = 100.0 / DU  # 候选解最小距离阈值 (DU)
EARTH_RADIUS = 200.0 / DU            # 地球碰撞半径
MOON_RADIUS = 100.0 / DU             # 月球碰撞半径

# 积分参数
INTEGRATION_DT = 1.0 / (24.0 * TU)  # 输出步长（约 10 分钟）

# GEO 轨道采样点数
GEO_N_POINTS = 1000


# =====================================================================
# GEO 轨道生成
# =====================================================================


def generate_geo_orbit(n_points: int = 500) -> Orbit:
    """在 CR3BP 旋转系中生成 GEO 近似圆轨道。

    GEO 被建模为以地心为圆心、半径为 R_GEO 的圆轨道。
    速度通过 geo_circular_velocity_rotating 计算（包含 Coriolis 修正）。
    """
    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    states = np.zeros((n_points, 6))

    for i, th in enumerate(theta):
        x = EARTH_CENTER[0] + R_GEO * np.cos(th)
        y = R_GEO * np.sin(th)
        z = 0.0

        pos = np.array([x, y, z])
        vel = geo_circular_velocity_rotating(pos)

        states[i] = [x, y, z, vel[0], vel[1], vel[2]]

    times = np.linspace(0, T_GEO, n_points, endpoint=False)

    orbit = Orbit(states, times)
    orbit.period = T_GEO
    return orbit


def main() -> None:
    # =========================================================================
    # 初始化
    # =========================================================================
    for _k in [
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
    ]:
        os.environ[_k] = "1"

    if not DRO_FILE.exists():
        # 尝试查找可用的 DRO 文件
        dro_dir = project_root / "output/dro"
        dro_files = sorted(dro_dir.glob("dro_31_*.json"))
        if not dro_files:
            print("错误：找不到 DRO 轨道文件！请先生成 DRO 轨道。")
            return
        dro_file = dro_files[-1]
        print(f"使用 DRO 文件: {dro_file}")
    else:
        dro_file = DRO_FILE

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = INTEGRATION_DT

    # 加载 DRO 轨道
    dro_orbit = load_orbit_from_json(str(dro_file))
    with open(dro_file) as f:
        dro_data = json.load(f)
    dro_orbit.period = dro_data.get("properties", {}).get("period", None)

    # 生成 GEO 轨道
    geo_orbit = generate_geo_orbit(n_points=GEO_N_POINTS)

    # =========================================================================
    # 执行搜索
    # =========================================================================
    print("\n" + "=" * 70)
    print("GEO → DRO 网格搜索")
    print("=" * 70)
    print(f"  GEO 轨道: {GEO_N_POINTS} 点, R={R_GEO:.6f} DU = {R_GEO * DU:.0f} km")
    print(f"  DRO 轨道: {dro_orbit.states.shape[0]} 点, "
          f"周期={dro_orbit.period:.4f} TU = {dro_orbit.period * TU:.2f} 天")
    print(f"  α 范围: [{ALPHA_MIN}, {ALPHA_MAX}], n={N_ALPHA}")
    print(f"  出发点数量: {N_DEPARTURE}")
    print(f"  最大转移时间: {MAX_TRANSFER_TIME:.1f} TU = {MAX_TRANSFER_TIME * TU:.1f} 天")
    print("=" * 70)

    searcher = TransferSearch(dynamics)
    results = searcher.search(
        departure_orbit=geo_orbit,
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
    # 保存结果
    # =========================================================================
    output_dir = project_root / "output/transfer"
    output_file = output_dir / (
        f"search_geo_dro_{N_DEPARTURE}-{N_ALPHA}-{ALPHA_MIN:g}-{ALPHA_MAX:g}-"
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
        # 保存出发状态（优化阶段需要）
        departure_state = r.get("departure_state")
        if departure_state is not None:
            serialized["departure_state"] = _json_safe(departure_state)
        return serialized

    results_data = [serialize_result(r) for r in results]

    output_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "direction": "GEO_to_DRO",
        "dro_file": str(dro_file),
        "geo_radius": float(R_GEO),
        "geo_period": float(T_GEO),
        "search_params": {
            "n_departure": N_DEPARTURE,
            "n_alpha": N_ALPHA,
            "alpha_min": ALPHA_MIN,
            "alpha_max": ALPHA_MAX,
            "max_transfer_time": MAX_TRANSFER_TIME,
            "intersection_threshold": INTERSECTION_THRESHOLD,
            "min_distance_threshold": MIN_DISTANCE_THRESHOLD,
            "collision_earth_radius": EARTH_RADIUS,
            "collision_moon_radius": MOON_RADIUS,
        },
        "n_total": len(results_data),
        "n_feasible": len(feasible),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results_data}, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存到: {output_file}")
    print(f"  总候选解: {len(results_data)}")
    print(f"  可行解: {len(feasible)}")

    if feasible:
        print("\n可行解摘要（前 10 个）:")
        sorted_feasible = sorted(feasible, key=lambda r: r.get("min_distance", float("inf")))
        for i, r in enumerate(sorted_feasible[:10]):
            md = r.get("min_distance", float("inf"))
            dv = r.get("dv_departure", 0)
            tt = r.get("transfer_time", 0)
            al = r.get("alpha", 0)
            print(f"  #{i+1}: dep_idx={r.get('departure_time_index')}, "
                  f"α={al:.4f}, T={tt:.2f} TU ({tt * TU:.1f} 天), "
                  f"dv_dep={dv:.4f} VU ({dv * VU:.0f} m/s), "
                  f"min_dist={md:.6f} DU ({md * DU:.0f} km), "
                  f"相交={r.get('intersection_found', False)}")


if __name__ == "__main__":
    main()
