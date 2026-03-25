"""
DRO-RO 网格搜索

使用方法:
    1. 修改下方 "参数配置" 部分
    2. 确保轨道数据JSON文件存在
    3. 运行: python grid_search.py
"""

import json
from pathlib import Path

import e2m2e
from e2m2e.transfer import DROTransferSearch, load_orbit_from_json

from scripts.utils.common import DU, MU, TU

project_root = Path(__file__).resolve().parent.parent.parent

# =============================================================================
# 参数配置
# =============================================================================

# 轨道数据文件路径（相对本仓库根目录；与当前工作目录无关）
DRO_FILE = project_root / "output/dro/dro_31_3857117441.json"
RO_FILE = project_root / "output/ro/ro_31_3857122799.json"

# 并行：1 = 串行（便于调试 _search_single_departure）；None = 使用 e2m2e 默认（cpu 核数）
# N_WORKERS = 1
N_WORKERS = None

# 搜索参数
N_DEPARTURE = 200  # 出发点采样数量 (范围: 50-500)
N_ALPHA = 101  # α方向网格点数 (范围: 51-501)
# 最大转移时间：10 天（e2m2e 内为无量纲 TU；1 TU ≈ 4.348 天，见 scripts.utils.common.TU）
MAX_TRANSFER_TIME = 10.0 / TU

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

# DOP853，rtol/atol=1e-12；输出步长 1 小时（无量纲）
DT = 1.0 / (24.0 * TU)
INTEGRATOR = "DOP853"


print("=" * 70)
print("DRO-RO 转移轨道网格搜索")
print("=" * 70)
print(f"\n搜索配置:")
print(f"  并行线程数 n_workers: {N_WORKERS}（None 表示使用 CPU 核数）")
print(f"  出发点数量: {N_DEPARTURE}")
print(f"  α范围: [{ALPHA_MIN:.2f}, {ALPHA_MAX:.2f}], n={N_ALPHA}")
print(f"  最大转移时间: {MAX_TRANSFER_TIME:.1f} TU")
_est_out = max(int(MAX_TRANSFER_TIME / DT) + 1, 2)
print(
    f"  输出时间步长（1 小时）: {DT:.8f} TU  "
    f"(每 1 TU ≈ {1.0/DT:.0f} 步；{MAX_TRANSFER_TIME:.1f} TU 上约 {_est_out} 个输出点)"
)
print(f"  相交阈值: {INTERSECTION_THRESHOLD:.6f}")
print(f"  候选解阈值: {MIN_DISTANCE_THRESHOLD:.6f}")
print(f"  碰撞半径: 地球={EARTH_RADIUS:.4f}, 月球={MOON_RADIUS:.4f}")


# =============================================================================
# e2m2e Transfer 模块初始化
# =============================================================================

system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
dynamics.integrator = INTEGRATOR
dynamics.rtol = 1e-12
dynamics.atol = 1e-12
dynamics.max_step = DT

# 加载轨道数据
print(f"\n加载轨道数据:")
print(f"  DRO: {DRO_FILE}")
print(f"  RO: {RO_FILE}")

dro_orbit = load_orbit_from_json(DRO_FILE)
ro_orbit = load_orbit_from_json(RO_FILE)

print(f"  DRO周期: {dro_orbit.period:.4f} TU, 状态数: {len(dro_orbit.states)}")
print(f"  RO周期: {ro_orbit.period:.4f} TU, 状态数: {len(ro_orbit.states)}")

transfer_search = DROTransferSearch(system=system, dynamics=dynamics)

transfer_search.alpha_min = ALPHA_MIN
transfer_search.alpha_max = ALPHA_MAX
transfer_search.n_alpha = N_ALPHA
transfer_search.n_departure = N_DEPARTURE
transfer_search.max_transfer_time = MAX_TRANSFER_TIME
transfer_search.intersection_threshold = INTERSECTION_THRESHOLD
transfer_search.min_distance_threshold = MIN_DISTANCE_THRESHOLD
transfer_search.collision_earth_radius = EARTH_RADIUS
transfer_search.collision_moon_radius = MOON_RADIUS
transfer_search.integration_dt = DT

print(f"\ne2m2e transfer 模块初始化完成")
print(f"  系统: μ = {system.mu:.6e}")
print(f"  积分器: {dynamics.integrator}")
print(f"  rtol/atol: {dynamics.rtol:g} / {dynamics.atol:g}")
print(f"  max_step: {dynamics.max_step:.8f} TU")
print(f"  搜索实例已创建")


# =============================================================================
# 执行网格搜索
# =============================================================================

print("\n" + "=" * 70)
print("开始网格搜索")
print("=" * 70)

transfer_search.set_departure_orbit(dro_orbit)
transfer_search.set_arrival_orbit(ro_orbit)

results = transfer_search.search(n_workers=N_WORKERS)

print(f"\n搜索完成，共找到 {len(results)} 个候选解")

feasible_results = [r for r in results if transfer_search._is_feasible(r)]
print(f"其中 {len(feasible_results)} 个为可行解")


# =============================================================================
# 保存结果到JSON
# =============================================================================

OUTPUT_FILE = project_root / "output/transfer/search_results.json"

def _json_safe(x):
    """JSON 序列化 numpy 标量/数组"""
    if x is None:
        return None
    if hasattr(x, "tolist"):
        return x.tolist()
    return x


def serialize_result(r):
    """序列化单条搜索结果（不含 transfer_trajectory）"""
    return {
        "departure_orbit_name": r.get("departure_orbit_name"),
        "arrival_orbit_name": r.get("arrival_orbit_name"),
        "departure_time": r.get("departure_time"),
        "departure_state": _json_safe(r.get("departure_state")),
        "alpha": r.get("alpha"),
        "transfer_time": r.get("transfer_time"),
        "min_distance": _json_safe(r.get("min_distance")),
        "min_distance_idx": r.get("min_distance_idx"),
        "intersection_found": r.get("intersection_found"),
        "intersection_point": _json_safe(r.get("intersection_point")),
        "intersection_idx": r.get("intersection_idx"),
        "local_minimum_found": r.get("local_minimum_found"),
        "local_minimum_distance": _json_safe(r.get("local_minimum_distance")),
        "collision_found": r.get("collision_found"),
        "collision_body": r.get("collision_body"),
        "status": r.get("status"),
        "is_feasible": transfer_search._is_feasible(r),
        "dv_departure": _json_safe(r.get("dv_departure")),
    }

results_data = [serialize_result(r) for r in results]

Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results_data, f, indent=2, ensure_ascii=False)

print(f"\n结果已保存到: {OUTPUT_FILE}")
print(f"  总候选解: {len(results_data)}")
print(f"  可行解: {len(feasible_results)}")


