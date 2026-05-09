"""
DRO → RO 转移轨道网格搜索

从 DRO 出发，搜索到达 RO（共振周期轨道）的转移轨道。
在 α（切向速度比）和出发时间构成的参数空间中搜索可行转移。

运行: python -m tod.pipelines.transfer.dro_to_ro.grid_search_dro_to_ro

输出文件名：``search_results_{nDep}-{nAlpha}-{αmin}-{αmax}-{tmax}_{timestamp}.json``。

Windows 多进程需要 ``if __name__ == "__main__"``，请勿删除末尾保护。
"""

import argparse
import json
import os
import numpy as np
import e2m2e
from pathlib import Path
import time
from e2m2e.transfer import TransferSearch, load_orbit_from_json
from tod.commons.common import DU, MU, TU


def parse_args():
    parser = argparse.ArgumentParser(description="DRO→RO 转移轨道网格搜索")
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径")
    parser.add_argument("--ro-file", type=str, default=None, help="RO 轨道 JSON 文件路径")
    parser.add_argument("--n-departure", type=int, default=200, help="出发时间网格数")
    parser.add_argument("--n-alpha", type=int, default=100, help="alpha 网格密度")
    parser.add_argument("--max-transfer-time", type=float, default=100.0 / TU, help="最大转移时间（无量纲）")
    parser.add_argument("--alpha-min", type=float, default=0.5, help="alpha 搜索下界")
    parser.add_argument("--alpha-max", type=float, default=2.5, help="alpha 搜索上界")
    parser.add_argument("--intersection-threshold", type=float, default=0.001, help="相交判定距离阈值")
    parser.add_argument("--min-distance", type=float, default=100.0 / DU, help="候选解最小距离阈值")
    parser.add_argument("--earth-radius", type=float, default=200.0 / DU, help="地球碰撞检测半径")
    parser.add_argument("--moon-radius", type=float, default=100.0 / DU, help="月球碰撞检测半径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # =========================================================================
    # 搜索参数配置
    # =========================================================================

    # 轨道数据文件路径（CLI > 环境变量 > 默认值）
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    dro_file = Path(args.dro_file or os.environ.get("DRO_FILE", str(project_root / "output/dro/dro_31_3857693511.json")))
    ro_file = Path(args.ro_file or os.environ.get("RO_FILE", str(project_root / "output/ro/ro_31_3857693516.json")))

    # =========================================================================
    # 初始化系统
    # =========================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = 1.0 / (24.0 * TU)

    _blas_keys = [
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]
    for _k in _blas_keys:
        os.environ[_k] = "1"

    # 加载轨道数据
    dro_orbit = load_orbit_from_json(str(dro_file))
    ro_orbit = load_orbit_from_json(str(ro_file))

    # =========================================================================
    # 执行搜索
    # =========================================================================
    print("\n" + "=" * 70)
    print("开始网格搜索")
    print("=" * 70)

    # 搜索参数
    n_departure = args.n_departure
    n_alpha = args.n_alpha
    max_transfer_time = args.max_transfer_time

    # alpha 参数搜索范围
    alpha_min = args.alpha_min
    alpha_max = args.alpha_max

    # 可行解判定条件
    intersection_threshold = args.intersection_threshold  # 相交判定距离阈值
    min_distance_threshold = args.min_distance

    # 碰撞检测半径
    earth_radius = args.earth_radius
    moon_radius = args.moon_radius

    transfer_searcher = TransferSearch(dynamics=dynamics)
    results = transfer_searcher.search(
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        n_alpha=n_alpha,
        n_departure=n_departure,
        max_transfer_time=max_transfer_time,
        intersection_threshold=intersection_threshold,
        min_distance_threshold=min_distance_threshold,
        collision_earth_radius=earth_radius,
        collision_moon_radius=moon_radius,
        integration_dt=dynamics.max_step,
        departure_orbit=dro_orbit,
        arrival_orbit=ro_orbit,
        n_workers=None,
    )

    print(f"\n搜索完成，共找到 {len(results)} 个候选解")

    feasible_results = [r for r in results if transfer_searcher._is_feasible(r)]
    print(f"其中 {len(feasible_results)} 个为可行解")

    # =========================================================================
    # 保存结果
    # =========================================================================
    output_dir = project_root / "output/transfer"
    output_file = output_dir / (
        f"search_results_{n_departure}-{n_alpha}-{alpha_min:g}-{alpha_max:g}-"
        f"{max_transfer_time:.6f}_{int(time.time())}.json"
    )

    def _json_safe(x):
        """将 NumPy 标量/数组及嵌套结构转为 JSON 可序列化的 Python 类型。"""
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
                "departure_orbit_name": r.get("departure_orbit_name"),
                "arrival_orbit_name": r.get("arrival_orbit_name"),
                "departure_time": r.get("departure_time"),
                "departure_state": r.get("departure_state"),
                "alpha": r.get("alpha"),
                "transfer_time": r.get("transfer_time"),
                "min_distance": r.get("min_distance"),
                "min_distance_idx": r.get("min_distance_idx"),
                "intersection_found": r.get("intersection_found"),
                "intersection_point": r.get("intersection_point"),
                "intersection_idx": r.get("intersection_idx"),
                "local_minimum_found": r.get("local_minimum_found"),
                "local_minimum_distance": r.get("local_minimum_distance"),
                "collision_found": r.get("collision_found"),
                "collision_body": r.get("collision_body"),
                "status": r.get("status"),
                "is_feasible": transfer_searcher._is_feasible(r),
                "dv_departure": r.get("dv_departure"),
                "dv_insertion": r.get("dv_insertion"),
                "min_distance_orbit_idx": r.get("min_distance_orbit_idx"),
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
