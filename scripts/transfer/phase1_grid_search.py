"""
DRO到RO转移轨道设计 - 第一阶段：网格搜索

用法:
    python phase1_grid_search.py --dro dro_family.json --ro ro_31_family.json
"""

import sys
import glob
import argparse
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import e2m2e
from scripts.utils.common import MU

OUTPUT_DIR = project_root / "output"

# =============================================================================
# 1. 解析命令行参数
# =============================================================================
parser = argparse.ArgumentParser(description="DRO到RO转移轨道设计 - 网格搜索阶段")
parser.add_argument("--dro", type=str, required=True, help="DRO轨道数据JSON文件")
parser.add_argument("--ro", type=str, required=True, help="RO轨道数据JSON文件")
parser.add_argument("--dro-index", type=int, default=0, help="DRO轨道索引")
parser.add_argument("--ro-index", type=int, default=0, help="RO轨道索引")
args = parser.parse_args()

# =============================================================================
# 2. 加载轨道数据
# =============================================================================
dro_files = glob.glob(args.dro)
ro_files = glob.glob(args.ro)

if not dro_files:
    raise FileNotFoundError(f"未找到DRO文件: {args.dro}")
if not ro_files:
    raise FileNotFoundError(f"未找到RO文件: {args.ro}")

print(f"加载DRO: {dro_files[0]}")
print(f"加载RO: {ro_files[0]}")

dro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(dro_files[0])
ro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(ro_files[0])

# =============================================================================
# 3. 系统与动力学模型初始化
# =============================================================================
system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

# 提取指定索引的轨道
dro_orbit = dro_data.orbits[args.dro_index]
ro_orbit = ro_data.orbits[args.ro_index]

# 出发点: DRO远地点(x最大)
dro_states = np.array(dro_orbit.states)
x_max_idx = np.argmax(dro_states[:, 0])
departure_state = dro_states[x_max_idx]

print(f"\n轨道信息:")
print(f"  DRO周期: {dro_orbit.period:.4f} TU")
print(f"  RO周期: {ro_orbit.period:.4f} TU")
print(f"  出发点状态: {departure_state}")

# =============================================================================
# 4. 网格搜索
# =============================================================================
print("\n" + "=" * 60)
print("第一阶段: 网格搜索")
print("=" * 60)

# 搜索参数设置
alpha_range = (0.5, 2.5)
transfer_time_range = (1.0, 30.0)
n_alpha = 21

print(f"α范围: [{alpha_range[0]}, {alpha_range[1]}]")
print(f"转移时间范围: [{transfer_time_range[0]}, {transfer_time_range[1]}] TU")
print(f"采样点: {n_alpha} x {n_alpha}")

# 创建搜索器
searcher = e2m2e.transfer.dro_ro_search.DROROTransferSearch(
    system=system, dynamics=dynamics, max_transfer_time=transfer_time_range[1]
)

# 执行网格搜索
feasible_solutions = searcher.grid_search(
    departure_orbit=dro_orbit,
    arrival_orbit=ro_orbit,
    alpha_range=alpha_range,
    beta_range=(-0.5, 0.5),
    n_alpha=n_alpha,
    n_beta=21,
    n_departure=50,
)

print(f"\n找到 {len(feasible_solutions)} 个可行解")

if not feasible_solutions:
    print("错误: 网格搜索未找到可行解")
    sys.exit(1)

# 保存所有可行解
output_path = OUTPUT_DIR / "transfer" / "grid_search_results.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

# 转换为可序列化格式
results_data = []
for sol in feasible_solutions:
    results_data.append(
        {
            "alpha": sol.alpha,
            "transfer_time": sol.transfer_time,
            "t_ins": sol.t_ins,
            "dv1": sol.dv1,
            "dv2": sol.dv2,
            "total_dv": sol.dv1 + sol.dv2,
            "feasible": sol.feasible,
        }
    )

import json

with open(output_path, "w") as f:
    json.dump(results_data, f, indent=2)

# 选择最优解(ΔV最小)
best_guess = min(feasible_solutions, key=lambda x: x.dv1 + x.dv2)
print(f"\n最优初始猜测:")
print(f"  α = {best_guess.alpha:.6f}")
print(f"  T = {best_guess.transfer_time:.6f} TU")
print(f"  t_ins = {best_guess.t_ins:.6f} TU")
print(f"  ΔV1 = {best_guess.dv1:.6f} DU/TU")
print(f"  ΔV2 = {best_guess.dv2:.6f} DU/TU")
print(f"  总ΔV = {best_guess.dv1 + best_guess.dv2:.6f} DU/TU")

print(f"\n结果已保存: {output_path}")
