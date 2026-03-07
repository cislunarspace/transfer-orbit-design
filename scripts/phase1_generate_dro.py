"""
阶段一：任务轨道生成 — DRO族

生成完整的Distant Retrograde Orbit (DRO)族，计算Jacobi常数与稳定性指标。

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6

DRO是月球远距离逆行轨道（Broucke Family F），具有以下对称性：
  - 关于x轴对称
  - 初始状态 [x0, 0, 0, 0, vy0, 0]，其中vy0 < 0（逆行）
  - 半周期条件：y(T/2) = 0, vx(T/2) = 0

论文参数：
  μ = 1.21506683 × 10⁻² (地月系统质量比)
  DU = 3.84405 × 10⁵ km, TU = 4.34811305 天
"""

import numpy as np
import matplotlib
from e2m2e import DifferentialCorrection, CR3BP_Dynamics

matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
from pathlib import Path
import json

import e2m2e

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
MU = 1.21506683e-2   # Mass ratio of the Earth–moon system
M_SUN = 3.28900541e5 # Nondimensional mass of the sun
OMEGA_SUN = 9.25195985e-1 # Nondimensional angular velocity of the sun
RHO = 3.88811143e2 # Nondimensional sun–(Earth–moon) distance
DU = 3.84405000e5       # Distance unit km
TU = 4.34811305      # Time unit days
VU = 1023.23281      # Velocity unit m/s

# 目标DRO
# 论文中作者是通过初值猜测和延拓法得到了DRO轨道组，然后在轨道族中找到了周期接近2:1和3:1的DRO。
# 我们也将采用同样的策略。

# ============================================================
# 主程序
# ============================================================
def main():
    # 1. 使用e2m2e库创建系统，为后续计算提供常数接口、数据存储等功能
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon") # 直接使用高精度常数
    system.compute_libration_points() # 根据系统常数计算拉格朗日点位置
    system.info()
    # 2. 生成DRO族
    dynamic = CR3BP_Dynamics(system)
    differentialcorrection = DifferentialCorrection(dynamic)
    seed_DRO = differentialcorrection.setup_2D_symmetric_x_fixed_x0(0.79188556619742)
    family_data = generate_dro_family(system, n_orbits=120, verbose=True)
    if family_data is None:
        print("DRO族生成失败！")
        return
    
    # 3. 计算Jacobi常数和稳定性
    family_data = compute_jacobi_and_stability(family_data, verbose=True)
    
    # 4. 识别目标DRO
    family_data = identify_target_dros(family_data, verbose=True)
    
    # 5. 精确修正目标DRO到精确共振周期
    print(f"\n{'='*60}")
    print("精确修正目标DRO")
    print(f"{'='*60}")
    
    for name, target_T in [("2:1 DRO", T_DRO_21), ("3:1 DRO", T_DRO_31)]:
        key = 'dro_21' if '2:1' in name else 'dro_31'
        guess_state = family_data[key]['state']
        
        orbit, result = refine_target_dro(system, target_T, guess_state, target_T / 2)
        if orbit is not None:
            print(f"\n{name} 精确修正成功:")
            print(f"  T = {result['period']:.12f} (目标: {target_T:.12f})")
            print(f"  x0 = {result['state'][0]:.12f}")
            print(f"  vy0 = {result['state'][4]:.12f}")
            print(f"  误差 = {result['error']:.2e}")
            family_data[key]['refined_state'] = result['state'].copy()
            family_data[key]['refined_period'] = result['period']
            family_data[key]['refined_orbit'] = orbit
        else:
            print(f"\n{name} 精确修正失败: {result['termination_reason']}")
    
    # 6. 保存和绘图
    output_dir = Path(__file__).parent.parent / "output" / "phase1_dro"
    save_family_data(family_data, output_dir)
    plot_dro_family(family_data, output_dir)
    
    print(f"\n{'='*60}")
    print("Phase 1 DRO族生成完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
