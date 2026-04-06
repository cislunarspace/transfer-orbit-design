"""
DRO → GEO 网格搜索

将目标从 RO（周期轨道）替换为 GEO（固定半径球面）。
结构与 grid_search.py 一致，使用 GeoTransferSearch 类。

运行: python scripts/transfer/grid_search_dro_geo.py

Windows 多进程需要 ``if __name__ == "__main__"``。
"""

import json
import os
import numpy as np
from pathlib import Path
from fontTools.misc.timeTools import timestampNow

import e2m2e
from e2m2e.transfer import GeoTransferSearch, load_orbit_from_json
from scripts.utils.common import DU, MU, TU


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent

    # =========================================================================
    # 搜索参数配置
    # =========================================================================
    dro_file = project_root / "output/dro/dro_31_3857693511.json"

    n_departure = 200
    n_alpha = 100
    alpha_min = 0.5
    alpha_max = 2.5
    max_transfer_time = 100.0 / TU

    geo_threshold = 100.0 / DU
    earth_radius = 200.0 / DU
    moon_radius = 100.0 / DU

    # =========================================================================
    # 初始化系统
    # =========================================================================
    for _k in [
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        os.environ[_k] = "1"

    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = 1.0 / (24.0 * TU)

    dro_orbit = load_orbit_from_json(str(dro_file))

    # =========================================================================
    # 执行搜索
    # =========================================================================
    print("\n" + "=" * 70)
    print("DRO → GEO 网格搜索")
    print("=" * 70)

    searcher = GeoTransferSearch(dynamics, geo_threshold=geo_threshold)
    results = searcher.search(
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        n_alpha=n_alpha,
        n_departure=n_departure,
        max_transfer_time=max_transfer_time,
        intersection_threshold=0.001,
        min_distance_threshold=geo_threshold,
        collision_earth_radius=earth_radius,
        collision_moon_radius=moon_radius,
        integration_dt=dynamics.max_step,
        departure_orbit=dro_orbit,
        n_workers=None,
    )

    print(f"\n搜索完成，共找到 {len(results)} 个候选解")

    feasible_results = searcher.get_feasible_results()
    print(f"其中 {len(feasible_results)} 个为可行解")

    # =========================================================================
    # 保存结果
    # =========================================================================
    output_dir = project_root / "output/transfer"
    output_file = output_dir / (
        f"search_dro_geo_{n_departure}-{n_alpha}-{alpha_min:g}-{alpha_max:g}-"
        f"{max_transfer_time:.6f}_{timestampNow()}.json"
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
        return _json_safe(
            {
                "departure_time_index": r.get("departure_time_index"),
                "departure_time": r.get("departure_time"),
                "alpha": r.get("alpha"),
                "transfer_time": r.get("transfer_time"),
                "dv_departure": r.get("dv_departure"),
                "dv_insertion": r.get("dv_insertion"),
                "geo_crossing_found": r.get("geo_crossing_found"),
                "min_distance_to_geo": r.get("min_distance_to_geo"),
                "collision_found": r.get("collision_found"),
                "collision_body": r.get("collision_body"),
                "status": r.get("status"),
                "is_feasible": searcher._is_feasible(r),
            }
        )

    results_data = [serialize_result(r) for r in results]

    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存到: {output_file}")
    print(f"  总候选解: {len(results_data)}")
    print(f"  可行解: {len(feasible_results)}")


if __name__ == "__main__":
    main()
