import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from matplotlib import pyplot as plt

from Class.CR3BP_Dynamics import CR3BP_Dynamics
from Class.CR3BP_System import CR3BP_System
from Class.Continuation import Continuation
from Class.DifferentialCorrection import DifferentialCorrection
from Class.Orbit import Orbit
from Class.StabilityAnalysis import StabilityAnalysis
from Class.Visualization import Visualization, ProjectionPlane

# 设置中文字体
plt.rcParams["font.sans-serif"] = ["SimHei"]  # 或者 ['Microsoft YaHei']、['KaiTi']等
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

# 1. 初始化系统
system = CR3BP_System(mu=0.01215, primary="Earth", secondary="Moon")

# 2. 创建动力学
dynamics = CR3BP_Dynamics(system)
target = {"y": 0.0, "x_dot": 0.0}  # 终点y坐标为0  # 终点x方向速度为0
free_vars = ["y_dot0", "T_half"]

# 3. 设置微分修正
corrector = DifferentialCorrection(dynamics, target, free_vars)

# 存储修正后的轨道
corrected_orbits = []
x0_values = [0.766448755485714, 0.77, 0.78, 0.79, 0.80, 0.81, 0.82, 0.83, 0.84, 0.85]
# x0_values = [0.766448755485714]
for i, x0 in enumerate(x0_values):
    print(f"\n{'=' * 60}")
    print(f"处理 x0 = {x0:.6f} ({i + 1}/{len(x0_values)})")
    print(f"{'=' * 60}")

    corrector.setup_2D_symmetric_x_fixed_x0(x0)

    # 4. 初始猜测
    initial_guess = Orbit(
        states=[[x0, 0, 0, 0, 0.573665890385585, 0]],  # x,y,z,dot_x,dot_y,dot_z
        times=[0],
    )
    initial_guess.period = 6.307498  # 设置轨道周期初始猜测

    # 5. 进行微分修正
    corrected_orbit = corrector.iterate_correction(initial_guess)

    if corrected_orbit is not None:
        corrected_orbits.append(corrected_orbit)
        print(f"✓ x0={x0:.6f} 修正成功")
    else:
        print(f"✗ x0={x0:.6f} 修正失败")

# 绘制微分修正后的轨道示意图
print(f"\n{'=' * 60}")
print("开始绘制修正后的轨道...")
print(f"{'=' * 60}")

# 创建可视化对象
viz = Visualization(system)

# 方式1：分别绘制每个轨道（单独窗口）
for i, orbit in enumerate(corrected_orbits[:5]):  # 只绘制前5个以免窗口太多
    # 创建新图形
    viz.figure = plt.figure(figsize=(10, 8))
    viz.axes = viz.figure.add_subplot(111)

    # 绘制2D投影
    viz.plot_2D_projection(
        orbit,
        plane=ProjectionPlane.XY,
        color=viz.color_cycle[i % len(viz.color_cycle)],
        label=f"x0={x0_values[i]:.3f}",
    )

    # 绘制平动点和主天体
    viz.plot_libration_points()
    viz.plot_primary_bodies()

    # 设置标题和标签
    viz.axes.set_title(
        f"修正后的周期轨道 (x0={x0_values[i]:.6f})", fontsize=viz.title_fontsize
    )
    viz.axes.set_xlabel("X")
    viz.axes.set_ylabel("Y")
    viz.axes.grid(True, alpha=0.3)
    viz.axes.legend()
    viz.axes.set_aspect("equal")

    # 保存图形
    viz.save_figure(f"corrected_orbit_x0_{x0_values[i]:.3f}.png")

    # 显示图形
    viz.show()

# 方式2：将所有轨道绘制在同一张图上进行对比
print("\n绘制轨道对比图...")
viz.figure = plt.figure(figsize=(12, 10))
viz.axes = viz.figure.add_subplot(111)

# 绘制所有修正成功的轨道
for i, orbit in enumerate(corrected_orbits):
    viz.plot_2D_projection(
        orbit,
        plane=ProjectionPlane.XY,
        color=viz.color_cycle[i % len(viz.color_cycle)],
        label=f"x0={x0_values[i]:.3f}",
        show_start=(i == 0),
    )  # 只标记第一个轨道的起点

# 绘制平动点和主天体
viz.plot_libration_points()
viz.plot_primary_bodies()

# 设置图形属性
viz.axes.set_title("修正后的周期轨道族对比", fontsize=14)
viz.axes.set_xlabel("X")
viz.axes.set_ylabel("Y")
viz.axes.grid(True, alpha=0.3)
viz.axes.legend(loc="best", fontsize=8)
viz.axes.set_aspect("equal")

# 保存对比图
viz.save_figure("corrected_orbits_comparison.png")
viz.show()
