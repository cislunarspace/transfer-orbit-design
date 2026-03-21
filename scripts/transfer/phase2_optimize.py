"""
DRO到RO转移轨道设计 - 第二阶段：SQP优化求解

用法:
    python phase2_optimize.py --dro dro_family.json --ro ro_31_family.json --alpha 1.0 --time 15.0 --t-ins 5.0
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
parser = argparse.ArgumentParser(description="DRO到RO转移轨道设计 - SQP优化阶段")
parser.add_argument("--dro", type=str, required=True, help="DRO轨道数据JSON文件")
parser.add_argument("--ro", type=str, required=True, help="RO轨道数据JSON文件")
parser.add_argument("--dro-index", type=int, default=0, help="DRO轨道索引")
parser.add_argument("--ro-index", type=int, default=0, help="RO轨道索引")
parser.add_argument("--alpha", type=float, required=True, help="初始猜测: α参数")
parser.add_argument("--time", type=float, required=True, help="初始猜测: 转移时间(TU)")
parser.add_argument("--t-ins", type=float, required=True, help="初始猜测: 插入时间(TU)")
parser.add_argument("--relaxed", action="store_true", help="使用松弛速度约束")
parser.add_argument("--vel-tol", type=float, default=5.0, help="速度角度容差(度)")
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
# 4. SQP优化
# =============================================================================
print("\n" + "=" * 60)
print("第二阶段: SQP优化")
print("=" * 60)
print(f"初始猜测:")
print(f"  α = {args.alpha}")
print(f"  T = {args.time} TU")
print(f"  t_ins = {args.t_ins} TU")

# 创建NLP优化器
optimizer = e2m2e.transfer.dro_ro_nlp.DROTRONLPOptimizer(
    system=system,
    dynamics=dynamics,
    departure_orbit=dro_orbit,
    arrival_orbit=ro_orbit,
    departure_state=departure_state,
)

# 构建初始猜测
nlp_initial = e2m2e.transfer.dro_ro_nlp.NLPOptimizationVariables(
    alpha=args.alpha, transfer_time=args.time, t_ins=args.t_ins
)

# 执行优化
result = optimizer.optimize(
    initial_guess=nlp_initial,
    use_relaxed_velocity_constraint=args.relaxed,
    velocity_angle_constraint=np.deg2rad(args.vel_tol),
    verbose=True,
)

# =============================================================================
# 5. 结果输出
# =============================================================================
print("\n" + "=" * 60)
print("优化结果")
print("=" * 60)

if result.success:
    print(f"优化成功!")
    print(f"  α = {result.variables.alpha:.6f}")
    print(f"  T = {result.variables.transfer_time:.6f} TU")
    print(f"  t_ins = {result.variables.t_ins:.6f} TU")
    print(f"  ΔV1 = {result.delta_v1:.6f} DU/TU")
    print(f"  ΔV2 = {result.delta_v2:.6f} DU/TU")
    print(f"  总ΔV = {result.objective_value:.6f} DU/TU")

    # 保存结果
    output_path = OUTPUT_DIR / "transfer" / "optimization_result.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 构建结果字典
    result_dict = {
        "success": result.success,
        "message": result.message,
        "transfer_type": result.transfer_type.value
        if hasattr(result.transfer_type, "value")
        else str(result.transfer_type),
        "variables": {
            "alpha": result.variables.alpha,
            "transfer_time": result.variables.transfer_time,
            "t_ins": result.variables.t_ins,
        },
        "delta_v": {
            "dv1": result.delta_v1,
            "dv2": result.delta_v2,
            "total": result.objective_value,
        },
        "departure_state": departure_state.tolist(),
    }

    import json

    with open(output_path, "w") as f:
        json.dump(result_dict, f, indent=2)

    print(f"\n结果已保存: {output_path}")
else:
    print(f"优化失败: {result.message}")
    sys.exit(1)
