"""
DRO-RO转移轨道网格搜索 V2

使用修正后的搜索算法 (dro_ro_search_v2.py) 进行网格搜索。
相比V1版本，修复了以下bug:
- BUG-001: departure_orbit=arrival_orbit 引用错误
- BUG-002: α,β速度扰动计算错误
- BUG-003: O(n²)嵌套循环效率低
- BUG-004: 缺少碰撞检测

用法:
    修改下方参数后直接运行: python grid_search.py

论文: Cui et al. - 2025 - Two-impulse transfers from lunar distant retrograde orbits to resonant orbits
"""

from pathlib import Path
from datetime import datetime

from e2m2e.core.system import CR3BP_System
from e2m2e.core.dynamics import CR3BP_Dynamics
from e2m2e.transfer.dro_ro_search_v2 import (
    DROROTransferSearchV2,
    TransferSearchConfig,
    load_orbit_from_json,
    save_search_results,
)
from scripts.utils.common import MU

# =============================================================================
# 搜索参数配置
# =============================================================================

# 输入文件
DRO_FILE = "output/dro/dro_31_3857029810.json"  # DRO轨道文件
RO_FILE = "output/ro/ro_31_3857030320.json"  # RO轨道文件

# 搜索参数 (按论文Table 3设置)
N_DEPARTURE = 5  # 出发点采样数量
N_ALPHA = 3  # α方向网格点数 (切向速度比)
N_BETA = 3  # β方向网格点数 (法向速度比)
MAX_TRANSFER_TIME = 15.0  # 最大转移时间 (CR3BP无量纲时间)

# α, β 搜索范围 (论文Table 3)
ALPHA_MIN = 0.5
ALPHA_MAX = 2.5
BETA_MIN = -0.5
BETA_MAX = 0.5

# 输出目录
OUTPUT_DIR = "output/transfer"

# 并行worker数量 (Windows建议使用较小值)
N_WORKERS = 1  # 暂时使用串行，Windows多进程有兼容问题

# =============================================================================


def main():
    global timestamp
    timestamp = int(datetime.now().timestamp())

    print("=" * 60)
    print("DRO-RO转移轨道网格搜索 V2")
    print("=" * 60)

    # 加载轨道数据
    print(f"\n加载DRO轨道: {DRO_FILE}")
    dro_orbit = load_orbit_from_json(DRO_FILE)
    dro_name = Path(DRO_FILE).stem

    print(f"加载RO轨道: {RO_FILE}")
    ro_orbit = load_orbit_from_json(RO_FILE)
    ro_name = Path(RO_FILE).stem

    # 创建CR3BP系统
    print(f"\n初始化CR3BP系统 (μ={MU})")
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)

    # 创建搜索配置
    config = TransferSearchConfig(
        alpha_min=ALPHA_MIN,
        alpha_max=ALPHA_MAX,
        n_alpha=N_ALPHA,
        beta_min=BETA_MIN,
        beta_max=BETA_MAX,
        n_beta=N_BETA,
        n_departure=N_DEPARTURE,
        max_transfer_time=MAX_TRANSFER_TIME,
    )

    print(f"\n搜索参数:")
    print(f"  出发点数量: {config.n_departure}")
    print(f"  α范围: [{config.alpha_min}, {config.alpha_max}], n={config.n_alpha}")
    print(f"  β范围: [{config.beta_min}, {config.beta_max}], n={config.n_beta}")
    print(f"  最大转移时间: {config.max_transfer_time}")
    print(f"  总候选解数量: {config.n_departure * config.n_alpha * config.n_beta}")

    # 创建搜索器
    searcher = DROROTransferSearchV2(
        system=system,
        dynamics=dynamics,
        config=config,
    )

    # 执行网格搜索
    print(f"\n开始网格搜索...")
    print("-" * 60)

    results = searcher.grid_search(
        departure_orbit=dro_orbit,
        arrival_orbit=ro_orbit,
        verbose=True,
        n_workers=N_WORKERS,
    )

    print("-" * 60)

    # 统计结果
    total = len(results)
    feasible = [r for r in results if r.is_feasible]
    collision = [r for r in results if r.collision_found]
    intersection = [r for r in results if r.intersection_found]
    local_min = [r for r in results if r.local_minimum_found]

    print(f"\n搜索结果统计:")
    print(f"  总候选解: {total}")
    print(f"  可行解: {len(feasible)}")
    print(f"  碰撞: {len(collision)}")
    print(f"  相交: {len(intersection)}")
    print(f"  局部最小: {len(local_min)}")

    # 保存结果
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存完整结果 (JSON格式)
    output_file = output_dir / f"search_v2_{dro_name}_{ro_name}_{timestamp}.json"
    save_search_results(results, str(output_file))
    print(f"\n结果已保存: {output_file}")

    # 保存可行解详情
    if feasible:
        feasible_file = (
            output_dir / f"feasible_v2_{dro_name}_{ro_name}_{timestamp}.json"
        )
        save_search_results(feasible, str(feasible_file))
        print(f"可行解详情: {feasible_file}")

        # 打印前5个最佳可行解
        print(f"\n前5个最佳可行解 (按min_distance排序):")
        feasible_sorted = sorted(feasible, key=lambda r: r.min_distance)[:5]
        for i, r in enumerate(feasible_sorted):
            print(
                f"  {i + 1}. α={r.alpha:.4f}, β={r.beta:.4f}, "
                f"min_dist={r.min_distance:.6f}, "
                f"transfer_time={r.transfer_time:.4f}"
            )

    print("\n" + "=" * 60)
    print("搜索完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
