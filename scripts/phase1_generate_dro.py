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

import datetime

import matplotlib
import e2m2e

# matplotlib.use("Agg")  # 非交互式后端，用于服务器环境或批量处理时避免图形界面

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
# 地月系统质量比，μ = m2/(m1+m2)，其中m1为地球质量，m2为月球质量
MU = 1.21506683e-2  # Mass ratio of the Earth–moon system

# 太阳的无量纲质量，用于后续考虑太阳引力摄动
M_SUN = 3.28900541e5  # Nondimensional mass of the sun

# 太阳的无量纲角速度，描述太阳在旋转坐标系中的运动
OMEGA_SUN = 9.25195985e-1  # Nondimensional angular velocity of the sun

# 太阳到地月系统的无量纲距离
RHO = 3.88811143e2  # Nondimensional sun–(Earth–moon) distance

# 距离单位：1 DU = 384405 km，地月平均距离
DU = 3.84405000e5  # Distance unit km

# 时间单位：1 TU = 4.34811305 天，地月系统的特征时间尺度
TU = 4.34811305  # Time unit days

# 速度单位：1 VU = 1023.23281 m/s，基于DU和TU计算得出
VU = 1023.23281  # Velocity unit m/s

# 目标DRO
# 论文中作者是通过初值猜测和延拓法得到了DRO轨道组，然后在轨道族中找到了周期接近2:1和3:1的DRO。
# 我们也将采用同样的策略。
#
# DRO轨道特点：
# 1. 逆行轨道（retrograde），相对于月球运动方向相反
# 2. 距离较远（distant），通常位于月球轨道之外
# 3. 具有周期性，在旋转坐标系中闭合
# 4. 关于x轴对称，满足对称性条件
#
# 算法原理：
# 1. 微分修正法（Differential Correction）：通过迭代修正初始状态，使轨道满足周期条件
# 2. 对称性条件：对于2D对称DRO，满足 y(0)=0, vx(0)=0, y(T/2)=0, vx(T/2)=0
# 3. 自然延拓法（Natural Continuation）：从一个已知解出发，通过参数连续变化得到轨道族
#
# 关键参数：
# - Jacobi常数（Cj）：运动积分，表征轨道能量
# - 稳定性指标：通过单值矩阵特征值判断轨道稳定性
# - 共振比：轨道周期与月球轨道周期的比值


# ============================================================
# 主程序
# ============================================================
def main():
    """
    主函数：生成DRO轨道族

    步骤：
    1. 创建CR3BP系统
    2. 设置微分修正器
    3. 提供初始猜测
    4. 进行微分修正得到精确的DRO轨道
    5. 可视化结果
    """

    # 1. 使用e2m2e库创建系统，为后续计算提供常数接口、数据存储等功能
    # 创建圆形限制性三体问题（CR3BP）系统，指定质量比和主次天体
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")

    # 可选：计算拉格朗日点位置（平动点）
    # system.compute_libration_points()  # 根据系统常数计算拉格朗日点位置
    # system.info()  # 打印系统信息

    # 创建动力学模型，用于计算状态转移矩阵和微分方程
    dynamic = e2m2e.core.dynamics.CR3BP_Dynamics(system)

    # 创建微分修正器，用于将近似轨道修正为精确周期轨道
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic)

    # 设置2D对称轨道修正模式：固定x0，修正其他参数
    # 这种模式适用于关于x轴对称的轨道，如DRO
    corrector.setup_2D_symmetric_x_fixed_x0()

    # 2. 生成DRO族
    # 设置初值：基于论文或前期计算结果
    x0 = 0.79188556619742  # 初始x坐标（无量纲）
    vy0 = 0.53682  # 初始y方向速度（无量纲）

    # 初始状态向量：[x, y, z, vx, vy, vz]
    # 对于2D对称DRO：y=0, z=0, vx=0, vz=0, vy待修正
    states = [[x0, 0, 0, 0, 0, 0]]

    # 初始时间猜测（无量纲时间）
    times = [
        3
    ]  # //TODO 这个时间参数好像是无效的，在后续e2m2e.core.Orbit的导入中是无效参数

    # 创建初始轨道猜测对象
    initial_guess = e2m2e.core.Orbit(states, times, system)

    # 设置初始周期猜测（这个值通常通过前期计算或文献获得）
    # 注意：这个值是刚刚计算出来的。计算出一次之后，就可以知道x0对应的period和vy0，
    # 然后在这个点上去使用自然延拓，就可以得到整个轨道族。
    initial_guess.period = 3.420385

    # 执行微分修正迭代，将近似轨道修正为精确的周期轨道
    seed_DRO = corrector.iterate_correction(initial_guess)

    # 3. 可视化结果
    # 创建轨道可视化器
    orbit_plotter = e2m2e.visualization.OrbitVisualizer(system)

    # 绘制2D投影（XY平面）
    orbit_plotter.plot_2d_projection(seed_DRO, plane="xy", label="Seed DRO")

    # 再次绘制XY平面投影（可设置不同颜色和标签）
    orbit_plotter.plot_2d_projection(
        seed_DRO, plane="xy", color="red", label="XY Projection"
    )

    # 添加主次天体（地球和月球）到图中
    orbit_plotter.plot_primary_bodies(ax=orbit_plotter.axes)

    # 添加拉格朗日点（平动点）到图中
    orbit_plotter.plot_libration_points(ax=orbit_plotter.axes)

    # 显示图形
    orbit_plotter.show()

    print("计算完成...")
    print(f"DRO轨道参数：")
    print(f"  初始x坐标: {x0}")
    print(f"  轨道周期: {seed_DRO.period if hasattr(seed_DRO, 'period') else 'N/A'} TU")
    print(
        f"  周期对应时间: {seed_DRO.period * TU if hasattr(seed_DRO, 'period') else 'N/A'} 天"
    )

    # 后续步骤建议：
    # 1. 保存轨道数据到文件
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    seed_DRO.save_to_file(
        f"out/seed_DRO_{timestamp}.json"
    )  # 将轨道数据保存为JSON文件
    # 2. //TODO 使用自然延拓法生成DRO轨道族
    print(1)
    # 3. 计算Jacobi常数和稳定性指标
    # 4. 寻找特定共振比（如2:1, 3:1）的DRO


if __name__ == "__main__":
    """
    程序入口点
    当直接运行此脚本时执行main()函数
    """
    main()
