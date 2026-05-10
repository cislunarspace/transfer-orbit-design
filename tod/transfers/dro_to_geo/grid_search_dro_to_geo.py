"""
DRO → GEO 转移轨道网格搜索

从 DRO 出发，搜索到达 GEO（地球静止轨道）的转移轨道。
使用 TransferSearch 类，在 α（切向速度比）和出发时间构成的参数空间中搜索。

运行: python -m tod.transfers.dro_to_geo.grid_search_dro_to_geo

DEPRECATED: GeoTransferSearch has been removed from e2m2e.
Windows 多进程需要 ``if __name__ == "__main__"``。
"""

import argparse
import json
import os
import sys
import numpy as np
from pathlib import Path
import time

import e2m2e
from e2m2e.transfer import load_orbit_from_json

# GeoTransferSearch has been removed from e2m2e; this script is deprecated
# from e2m2e.transfer import GeoTransferSearch
from tod.commons.common import DU, MU, TU


def parse_args():
    parser = argparse.ArgumentParser(description="DRO→GEO 转移轨道网格搜索")
    parser.add_argument(
        "--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径"
    )
    parser.add_argument("--n-departure", type=int, default=200, help="出发时间网格数")
    parser.add_argument("--n-alpha", type=int, default=100, help="alpha 网格密度")
    parser.add_argument("--alpha-min", type=float, default=0.5, help="alpha 搜索下界")
    parser.add_argument("--alpha-max", type=float, default=2.5, help="alpha 搜索上界")
    parser.add_argument(
        "--max-transfer-time",
        type=float,
        default=100.0 / TU,
        help="最大转移时间（无量纲）",
    )
    parser.add_argument(
        "--geo-threshold", type=float, default=100.0 / DU, help="GEO 相交距离阈值"
    )
    parser.add_argument(
        "--earth-radius", type=float, default=200.0 / DU, help="地球碰撞检测半径"
    )
    parser.add_argument(
        "--moon-radius", type=float, default=100.0 / DU, help="月球碰撞检测半径"
    )
    return parser.parse_args()


def main() -> None:
    raise NotImplementedError(
        "GeoTransferSearch has been removed from e2m2e; "
        "use TransferSearch or DROTransferSearch instead."
    )
    args = parse_args()  # type: ignore[unreachable]
    project_root = Path(__file__).resolve().parent.parent.parent.parent

    # =========================================================================
    # 搜索参数配置
    # =========================================================================
    dro_file = Path(
        args.dro_file
        or os.environ.get(
            "DRO_FILE", str(project_root / "output/dro/dro_31_3857693511.json")
        )
    )

    n_departure = args.n_departure
    n_alpha = args.n_alpha
    alpha_min = args.alpha_min
    alpha_max = args.alpha_max
    max_transfer_time = args.max_transfer_time

    geo_threshold = args.geo_threshold
    earth_radius = args.earth_radius
    moon_radius = args.moon_radius

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
        f"{max_transfer_time:.6f}_{int(time.time())}.json"
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
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--n-departure", "200",                       # 出发时间网格数
            "--n-alpha", "100",                           # alpha 网格密度
            "--alpha-min", "0.5",                         # alpha 搜索下界
            "--alpha-max", "2.5",                         # alpha 搜索上界
            "--max-transfer-time", "22.998482090701266",  # 最大转移时间（无量纲，100.0/TU）
            "--geo-threshold", "0.0002601422978369168",   # GEO 相交距离阈值（100.0/DU）
            "--earth-radius", "0.0005202845956738336",    # 地球碰撞检测半径（200.0/DU）
            "--moon-radius", "0.0002601422978369168",     # 月球碰撞检测半径（100.0/DU）
        ]
        print("[debug] 使用代码内置调试参数")
    main()
