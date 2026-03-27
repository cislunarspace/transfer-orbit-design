"""
DRO-RO 网格搜索

使用方法:
    1. 修改下方 "参数配置" 部分
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

# =============================================================================
# 参数配置
# =============================================================================

# 轨道数据文件路径
project_root = Path(__file__).resolve().parent.parent.parent
DRO_FILE = project_root / "output/dro/dro_31_3857199098.json"
RO_FILE = project_root / "output/ro/ro_31_3857328571.json"

# 并行数，1=单线程，None=cpu核数
N_WORKERS = None

# 搜索参数
N_DEPARTURE = 200  # 出发点采样数量
N_ALPHA = 10  # α 方向网格点数
MAX_TRANSFER_TIME = 100.0 / TU  # 最大转移时间

# alpha 参数搜索范围
ALPHA_MIN = 0.5
ALPHA_MAX = 2.5

# 可行解判定条件
INTERSECTION_THRESHOLD = 0.001  # 相交判定距离阈值 //TODO 这个值需要审核
MIN_DISTANCE_THRESHOLD = 100.0 / DU  # 候选解距离阈值

# 碰撞检测半径
EARTH_RADIUS = 200 / DU
MOON_RADIUS = 100 / DU

# 积分器设置
DT = 1.0 / (24.0 * TU)  # 积分步长
INTEGRATOR = "DOP853"  # 积分器

def print_search_config():
    print("=" * 70)
    print("DRO-RO 转移轨道网格搜索")
    print("=" * 70)
    print(f"\n搜索配置:")
    print(f"  并行 worker 数 n_workers: {N_WORKERS}（None=CPU 核数；默认多进程）")
    print(f"  出发点数量: {N_DEPARTURE}")
    print(f"  α范围: [{ALPHA_MIN:.2f}, {ALPHA_MAX:.2f}], n={N_ALPHA}")
    print(f"  最大转移时间: {MAX_TRANSFER_TIME:.1f} TU")
    _est_out = max(int(MAX_TRANSFER_TIME / DT) + 1, 2)
    print(
        f"  输出时间步长（1 小时）: {DT:.8f} TU  "
        f"(每 1 TU ≈ {1.0 / DT:.0f} 步；{MAX_TRANSFER_TIME:.1f} TU 上约 {_est_out} 个输出点)"
    )
    print(f"  相交阈值: {INTERSECTION_THRESHOLD:.6f}")
    print(f"  候选解阈值: {MIN_DISTANCE_THRESHOLD:.6f}")
    print(f"  碰撞半径: 地球={EARTH_RADIUS*DU:.4f}, 月球={MOON_RADIUS*DU:.4f}")

def main() -> None:
    # 打印搜索参数设置
    print_search_config()

    # 加载系统
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = INTEGRATOR
    dynamics.rtol = 1e-12 # 相对积分容差
    dynamics.atol = 1e-12 # 绝对积分容差
    dynamics.max_step = DT

    # 加载轨道数据
    dro_orbit = load_orbit_from_json(str(DRO_FILE))
    ro_orbit = load_orbit_from_json(str(RO_FILE))

    print(f"  DRO周期: {dro_orbit.period:.4f} TU, 状态数: {len(dro_orbit.states)}")
    print(f"  RO周期: {ro_orbit.period:.4f} TU, 状态数: {len(ro_orbit.states)}")

    # 创建转移搜索实例
    transfer_searcher = TransferSearch(system=system, dynamics=dynamics)

    # 配置搜索参数
    transfer_searcher.alpha_min = ALPHA_MIN
    transfer_searcher.alpha_max = ALPHA_MAX
    transfer_searcher.n_alpha = N_ALPHA
    transfer_searcher.n_departure = N_DEPARTURE
    transfer_searcher.max_transfer_time = MAX_TRANSFER_TIME
    transfer_searcher.intersection_threshold = INTERSECTION_THRESHOLD
    transfer_searcher.min_distance_threshold = MIN_DISTANCE_THRESHOLD
    transfer_searcher.collision_earth_radius = EARTH_RADIUS
    transfer_searcher.collision_moon_radius = MOON_RADIUS
    transfer_searcher.integration_dt = DT

    print(f"\ne2m2e transfer 模块初始化完成")
    print(f"  系统: μ = {system.mu:.6e}")
    print(f"  积分器: {dynamics.integrator}")
    print(f"  rtol/atol: {dynamics.rtol:g} / {dynamics.atol:g}")
    print(f"  max_step: {dynamics.max_step:.8f} TU")
    print(f"  搜索实例已创建")

    print("\n" + "=" * 70)
    print("开始网格搜索")
    print("=" * 70)

    transfer_searcher.set_departure_orbit(dro_orbit)
    transfer_searcher.set_arrival_orbit(ro_orbit)

    results = transfer_searcher.search(n_workers=N_WORKERS)

    print(f"\n搜索完成，共找到 {len(results)} 个候选解")

    feasible_results = [r for r in results if transfer_searcher._is_feasible(r)]
    print(f"其中 {len(feasible_results)} 个为可行解")

    output_dir = project_root / "output/transfer"
    output_file = output_dir / (
        f"search_results_{N_DEPARTURE}-{N_ALPHA}-{ALPHA_MIN:g}-{ALPHA_MAX:g}-"
        f"{MAX_TRANSFER_TIME:.6f}_{timestampNow()}.json"
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
