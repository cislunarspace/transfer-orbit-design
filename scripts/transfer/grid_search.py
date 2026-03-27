"""
DRO-RO 网格搜索

使用方法:
    1. 修改 main() 函数中的搜索参数
    2. 确保轨道数据JSON文件存在
    3. 运行: python grid_search.py

输出文件名：``search_results_{nDep}-{nAlpha}-{αmin}-{αmax}-{tmax}_{timestamp}.json``。

Windows 多进程需要 ``if __name__ == "__main__"``，请勿删除末尾保护。
"""

import json
import numpy as np
import e2m2e
from pathlib import Path
from fontTools.misc.timeTools import timestampNow
from e2m2e.transfer import TransferSearch, load_orbit_from_json
from scripts.utils.common import DU, MU, TU


def main() -> None:
    # =========================================================================
    # 搜索参数配置
    # =========================================================================

    # 轨道数据文件路径
    project_root = Path(__file__).resolve().parent.parent.parent
    dro_file = project_root / "output/dro/dro_31_3857199098.json"
    ro_file = project_root / "output/ro/ro_31_3857328571.json"

    # =========================================================================
    # 初始化系统
    # =========================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    system = e2m2e.core.system.CR3BP_System(mu=0.01215, primary="Earth", secondary="Moon")
    system.set_characteristic_scales(
        distance=384400.0,
        period=27.32 * 86400
    )
    dynamic = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamic.integrator = "DOP853" # 修改积分器为DOP853,提高积分精度
    dynamic.rtol = 1e-12
    dynamic.atol = 1e-12
    dynamic.max_step = 1.0 / (24.0 * system.characteristic_length) # 设置积分步长为1天

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
    n_departure = 200
    n_alpha = 10
    max_transfer_time = 100.0 / TU

    # alpha 参数搜索范围
    alpha_min = 0.5
    alpha_max = 2.5

    # 可行解判定条件
    intersection_threshold = 0.001  # 相交判定距离阈值
    min_distance_threshold = 100.0 / DU

    # 碰撞检测半径
    earth_radius = 200 / DU
    moon_radius = 100 / DU

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
        f"{max_transfer_time:.6f}_{timestampNow()}.json"
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
