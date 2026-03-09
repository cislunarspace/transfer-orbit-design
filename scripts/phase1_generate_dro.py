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

import matplotlib
import e2m2e

matplotlib.use("Agg")  # 非交互式后端

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
MU = 1.21506683e-2  # Mass ratio of the Earth–moon system
M_SUN = 3.28900541e5  # Nondimensional mass of the sun
OMEGA_SUN = 9.25195985e-1  # Nondimensional angular velocity of the sun
RHO = 3.88811143e2  # Nondimensional sun–(Earth–moon) distance
DU = 3.84405000e5  # Distance unit km
TU = 4.34811305  # Time unit days
VU = 1023.23281  # Velocity unit m/s

# 目标DRO
# 论文中作者是通过初值猜测和延拓法得到了DRO轨道组，然后在轨道族中找到了周期接近2:1和3:1的DRO。
# 我们也将采用同样的策略。


# ============================================================
# 主程序
# ============================================================
def main():
    # 1. 使用e2m2e库创建系统，为后续计算提供常数接口、数据存储等功能
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    # system.compute_libration_points()  # 根据系统常数计算拉格朗日点位置
    # system.info()
    dynamic = e2m2e.core.dynamics.CR3BP_Dynamics(system)
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic)
    corrector.setup_2D_symmetric_x_fixed_x0()
    # 2. 生成DRO族
    # 设置初值
    x0 = 0.79188556619742
    states = [[x0, 0, 0, 0, 0, 0]]
    times = [3]
    initial_guess = e2m2e.core.Orbit(states, times, system)
    initial_guess.period = 3.420385 # 这个值是刚刚计算出来的。计算出一次之后，其实就可以知道x0对应的period和vy0，然后在这个点上去使用自然延拓，就可给得到轨道组。
    seed_DRO = corrector.iterate_correction(initial_guess)
    print("计算完成...")


if __name__ == "__main__":
    main()
