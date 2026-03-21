"""
交互式轨道检查器 (Interactive Orbit Inspector)

本脚本实现：
1. 加载轨道族数据
2. 以debug模式逐步遍历每条轨道
3. 每次按Enter后在新窗口绘制一条轨道，方便检查轨道质量

使用方法：
- 在VS Code中以debug模式运行此脚本
- 每次按Enter键会绘制下一条轨道
- 关闭窗口后按Enter继续下一条
- 输入 'q' 退出程序
- 输入 's' 跳过若干条轨道
- 输入 'j' 跳转到指定轨道

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

import sys
from pathlib import Path

# 将项目根目录添加到 sys.path，确保可以导入 scripts.utils
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import e2m2e
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization.plotting import OrbitVisualizer
from scripts.utils.common import MU
import matplotlib.pyplot as plt

plt.ion()  # 开启交互模式


# =============================================================================
# 配置区 - 修改这里选择要检查的轨道族
# =============================================================================
# 轨道族数据文件
FAMILY_NAME = "dro_family_0.6-0.8-0.005_3856837265"  # 3:2 RO 轨道族
# FAMILY_NAME = "ro_31_family_-1.0--0.7-0.005_3856827709"  # 3:1 RO 轨道族
# FAMILY_NAME = "dro_family_0.6-0.8-0.005_3856837322"  # DRO 轨道族

FAMILY_PATH = project_root / "scripts" / "output" / "dro" / f"{FAMILY_NAME}.json"

# 可视化配置
PLANE = "xy"  # 投影平面: "xy", "xz", "yz"
SHOW_3D = False  # 是否同时显示3D视图 (注意: 3D模式在某些环境下有matplotlib bug)
FIGURE_SIZE = (10, 8)  # 图形大小


# =============================================================================
# 主程序
# =============================================================================
# 创建全局图形窗口
fig = plt.figure(figsize=FIGURE_SIZE)

def compute_orbit_jacobi(orbit, system):
    """计算单条轨道的Jacobi常数"""
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    try:
        return dynamics.compute_jacobi_constant(orbit.states[0])
    except Exception:
        return None


def main():
    # 加载系统
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    
    # 加载轨道族
    print(f"加载轨道族: {FAMILY_NAME}")
    family = OrbitFamily.load_from_file(filename=FAMILY_PATH, system=system)
    n_orbits = len(family)
    print(f"共 {n_orbits} 条轨道")
    
    # 创建可视化器
    orbit_plotter = OrbitVisualizer(system=system)
    orbit_plotter.figsize = FIGURE_SIZE
    
    # 主循环
    current_idx = 0
    
    print("\n" + "=" * 60)
    print("交互式轨道检查器")
    print("=" * 60)
    print("按 Enter: 绘制下一条轨道")
    print("输入 'q': 退出程序")
    print("输入 's N': 跳过N条轨道")
    print("输入 'j N': 跳转到第N条轨道")
    print("输入 'r': 重新绘制当前轨道")
    print("=" * 60 + "\n")
    
    while True:
        # 显示当前轨道信息
        orbit = family[current_idx]
        jacobi_vals = orbit.jacobi_constants
        if jacobi_vals is not None and len(jacobi_vals) > 0:
            jacobi = jacobi_vals[0]
        else:
            jacobi = compute_orbit_jacobi(orbit, system)
        period = orbit.period if orbit.period else 0.0
        
        print(f"\n[{current_idx + 1}/{n_orbits}] 轨道信息:")
        print(f"  状态向量: [{orbit.states[0][0]:.6f}, {orbit.states[0][1]:.6f}, "
              f"{orbit.states[0][2]:.6f}, {orbit.states[0][3]:.6f}, "
              f"{orbit.states[0][4]:.6f}, {orbit.states[0][5]:.6f}]")
        print(f"  Jacobi常数: {jacobi:.6f}")
        print(f"  周期: {period:.4f} TU ({period * 4.348:.4f} days)")
        
        # 清除上一帧
        fig.clf()
        
        # 2D投影
        if SHOW_3D:
            ax_2d = fig.add_subplot(1, 2, 1)
            ax_3d = fig.add_subplot(1, 2, 2, projection='3d')
        else:
            ax_2d = fig.add_subplot(111)
            ax_3d = None
        
        # 绘制主天体和平动点
        orbit_plotter.plot_primary_bodies(ax=ax_2d)
        orbit_plotter.plot_libration_points(ax=ax_2d)
        
        # 绘制轨道
        label = f"Orbit {current_idx + 1} (C={jacobi:.4f})"
        orbit_plotter.plot_2d_projection(
            orbit, plane=PLANE, color="blue", label=label, ax=ax_2d
        )
        ax_2d.set_title(f"XY Plane - Orbit {current_idx + 1}/{n_orbits}")
        ax_2d.legend(loc="upper right")
        ax_2d.set_aspect("equal")
        
        # 3D视图
        if SHOW_3D:
            orbit_plotter.plot_primary_bodies(ax=ax_3d, is_3d=True)
            orbit_plotter.plot_libration_points(ax=ax_3d, is_3d=True, show_labels=True)
            orbit_plotter.plot_3d_orbit(
                orbit, color="blue", label=label, ax=ax_3d
            )
            ax_3d.set_title(f"3D View - Orbit {current_idx + 1}/{n_orbits}")
            ax_3d.legend(loc="upper right")
        
        plt.tight_layout()
        fig.canvas.draw()
        fig.canvas.flush_events()
        
        try:
            user_input = input("\n命令 (Enter继续, q退出, s跳过, j跳转, r重绘): ").strip().lower()
        except EOFError:
            # 非交互环境
            break
        
        if user_input == 'q':
            print("退出程序")
            break
        elif user_input.startswith('s '):
            # 跳过N条轨道
            try:
                skip_n = int(user_input.split()[1])
                current_idx = min(current_idx + skip_n, n_orbits - 1)
                print(f"跳转到轨道 {current_idx + 1}")
            except (ValueError, IndexError):
                print("无效的跳过数量")
        elif user_input.startswith('j '):
            # 跳转到指定轨道
            try:
                target = int(user_input.split()[1])
                current_idx = max(0, min(target - 1, n_orbits - 1))
                print(f"跳转到轨道 {current_idx + 1}")
            except (ValueError, IndexError):
                print("无效的轨道编号")
        elif user_input == 'r':
            # 重新绘制当前轨道（不前进）
            print(f"重绘轨道 {current_idx + 1}")
            continue
        else:
            # 下一条轨道
            if current_idx < n_orbits - 1:
                current_idx += 1
            else:
                print("已到达最后一条轨道")
                break
    
    print(f"\n检查完成，共检查了 {current_idx + 1} 条轨道")


if __name__ == "__main__":
    main()
