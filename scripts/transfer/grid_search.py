"""
DRO-RO 网格搜索

使用方法:
    1. 修改下方 "参数配置" 部分
    2. 确保轨道数据JSON文件存在
    3. 运行: python grid_search.py
"""

import json
from pathlib import Path
from scripts.utils.common import MU, DU, TU

# =============================================================================
# 参数配置
# =============================================================================

# 轨道数据文件路径，单条轨道
DRO_FILE = "output/dro/dro_31_3857199098.json"
RO_FILE = "output/ro/ro_32_family_-1.2--0.8-0.005_3857196959.json"

# 搜索参数
N_DEPARTURE = 200  # 出发点采样数量 (范围: 50-500)
N_ALPHA = 101  # α方向网格点数 (范围: 51-501)
MAX_TRANSFER_TIME = 15.0  # 最大转移时间 (TU)

# alpha 搜索范围
ALPHA_MIN = 0.5
ALPHA_MAX = 2.5

# 筛选阈值
INTERSECTION_THRESHOLD = 0.001  # 相交判定距离 (当距离小于此值认为相交)
MIN_DISTANCE_THRESHOLD = 0.05  # 候选解最小距离阈值

# 碰撞检测半径 (无量纲 DU)
# 地球: 200 km = 200/384405 DU ≈ 0.000520 DU
# 月球: 100 km = 100/384405 DU ≈ 0.000260 DU
EARTH_RADIUS = 200 / DU
MOON_RADIUS = 100 / DU

# 积分配置
# 1 分钟 = 1/6269.28 TU ≈ 0.0001595 TU (1 TU = 4.34811305 天 = 6269.28 分钟)
DT = 1.0 / (24 * 60 * TU)
INTEGRATOR = "rk4"  # //TODO 这里应该要使用更高精度的积分器


print("=" * 70)
print("DRO-RO 转移轨道网格搜索")
print("=" * 70)
print(f"\n搜索配置:")
print(f"  出发点数量: {N_DEPARTURE}")
print(f"  α范围: [{ALPHA_MIN:.2f}, {ALPHA_MAX:.2f}], n={N_ALPHA}")
print(f"  最大转移时间: {MAX_TRANSFER_TIME:.1f} TU")
print(f"  积分步长: {DT}")
print(f"  相交阈值: {INTERSECTION_THRESHOLD:.6f}")
print(f"  候选解阈值: {MIN_DISTANCE_THRESHOLD:.6f}")
print(f"  碰撞半径: 地球={EARTH_RADIUS:.4f}, 月球={MOON_RADIUS:.4f}")


# =============================================================================
# e2m2e Transfer 模块初始化
# =============================================================================

# 导入 e2m2e 及 transfer 模块
import e2m2e
from e2m2e.transfer import (
    load_orbit_from_json,
    DROTransferSearch,
)

# 创建 CR3BP 系统与动力学模型
system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

# 加载轨道数据
print(f"\n加载轨道数据:")
print(f"  DRO: {DRO_FILE}")
print(f"  RO: {RO_FILE}")

dro_orbit = load_orbit_from_json(DRO_FILE)
ro_orbit = load_orbit_from_json(RO_FILE)

print(f"  DRO周期: {dro_orbit.period:.4f} TU, 状态数: {len(dro_orbit.states)}")
print(f"  RO周期: {ro_orbit.period:.4f} TU, 状态数: {len(ro_orbit.states)}")

# 创建网格搜索实例
transfer_search = DROTransferSearch(system=system, dynamics=dynamics)

# 设置搜索参数（直接在实例上赋值）
transfer_search.alpha_min = ALPHA_MIN
transfer_search.alpha_max = ALPHA_MAX
transfer_search.n_alpha = N_ALPHA
transfer_search.n_departure = N_DEPARTURE
transfer_search.max_transfer_time = MAX_TRANSFER_TIME
transfer_search.intersection_threshold = INTERSECTION_THRESHOLD
transfer_search.min_distance_threshold = MIN_DISTANCE_THRESHOLD
transfer_search.collision_earth_radius = EARTH_RADIUS
transfer_search.collision_moon_radius = MOON_RADIUS

print(f"\ne2m2e transfer 模块初始化完成")
print(f"  系统: μ = {system.mu:.6e}")
print(f"  搜索实例已创建")


# =============================================================================
# 执行网格搜索
# =============================================================================

print("\n" + "=" * 70)
print("开始网格搜索")
print("=" * 70)

# 设置轨道
transfer_search.set_departure_orbit(dro_orbit)
transfer_search.set_arrival_orbit(ro_orbit)

# 执行搜索
results = transfer_search.search()

print(f"\n搜索完成，共找到 {len(results)} 个候选解")

# 筛选可行解
feasible_results = [r for r in results if r.is_feasible]
print(f"其中 {len(feasible_results)} 个为可行解")


# =============================================================================
# 保存结果到JSON
# =============================================================================

OUTPUT_FILE = "output/transfer/search_results.json"

def serialize_result(r):
    """将SearchResult转换为可序列化的字典"""
    return {
        "departure_orbit_name": r.departure_orbit_name,
        "arrival_orbit_name": r.arrival_orbit_name,
        "departure_time": r.departure_time,
        "departure_state": r.departure_state.tolist() if r.departure_state is not None else None,
        "alpha": r.alpha,
        "transfer_time": r.transfer_time,
        "min_distance": r.min_distance,
        "min_distance_idx": r.min_distance_idx,
        "intersection_found": r.intersection_found,
        "intersection_point": r.intersection_point.tolist() if r.intersection_point is not None else None,
        "intersection_idx": r.intersection_idx,
        "local_minimum_found": r.local_minimum_found,
        "local_minimum_distance": r.local_minimum_distance,
        "collision_found": r.collision_found,
        "collision_body": r.collision_body,
        "status": r.status,
        "is_feasible": r.is_feasible,
        "dv_departure": r.dv_departure,
    }

# 序列化所有结果
results_data = [serialize_result(r) for r in results]

# 确保输出目录存在
Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)

# 保存到JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results_data, f, indent=2, ensure_ascii=False)

print(f"\n结果已保存到: {OUTPUT_FILE}")
print(f"  总候选解: {len(results_data)}")
print(f"  可行解: {len(feasible_results)}")


