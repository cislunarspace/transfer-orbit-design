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

import argparse
import sys
from pathlib import Path


import e2m2e
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization.base import OrbitVisualizer
from tod.commons.common import MU, TU
from tod.commons.plot_helpers import apply_standard_plot_config, style_colorbar
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable
from tod.commons.common import find_project_root
project_root = find_project_root(Path(__file__))

PLOT_CONFIG = apply_standard_plot_config()


def parse_args():
    parser = argparse.ArgumentParser(description="交互式轨道检查器")
    parser.add_argument(
        "--json-file", type=str, default=None, help="轨道族 JSON 文件路径"
    )
    parser.add_argument(
        "--plane", type=str, default="xy", choices=["xy", "xz", "yz"], help="投影平面"
    )
    parser.add_argument(
        "--show-3d", action="store_true", default=False, help="同时显示3D视图"
    )
    parser.add_argument(
        "--fig-size", type=int, nargs=2, default=[10, 8], help="图形大小 (宽 高)"
    )
    return parser.parse_args()


DEFAULT_FAMILY_NAME = "ro_31_family_0.8905--0.8304999999999999-0.001_3856910376"


# 全局图形窗口（在 main() 中初始化）
fig = None


def compute_orbit_jacobi(orbit, system):
    """计算单条轨道的Jacobi常数"""
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    try:
        return dynamics.compute_jacobi_constant(orbit.states[0])
    except Exception:
        return None


def precompute_jacobi_for_family(family, system):
    """预计算轨道族所有轨道的Jacobi常数"""
    jacobi_list = []
    for orbit in family:
        jacobi_vals = orbit.jacobi_constants
        if jacobi_vals is not None and len(jacobi_vals) > 0:
            jacobi_list.append(jacobi_vals[0])
        else:
            jacobi_list.append(compute_orbit_jacobi(orbit, system))
    return jacobi_list


def compute_global_axis_limits(family, plane="xy", margin=1.15):
    """根据轨道族计算全局轴范围，确保所有轨道都能显示在同一窗口"""
    if not family:
        return -1.0, 1.0

    all_coords = {"x": [], "y": [], "z": []}

    for orbit in family:
        states = orbit.states
        for state in states:
            x, y, z = state[0], state[1], state[2]
            all_coords["x"].extend([x])
            all_coords["y"].extend([y])
            all_coords["z"].extend([z])

    if plane == "xy":
        max_val = max(
            max(abs(v) for v in all_coords["x"]), max(abs(v) for v in all_coords["y"])
        )
    elif plane == "xz":
        max_val = max(
            max(abs(v) for v in all_coords["x"]), max(abs(v) for v in all_coords["z"])
        )
    elif plane == "yz":
        max_val = max(
            max(abs(v) for v in all_coords["y"]), max(abs(v) for v in all_coords["z"])
        )
    else:
        raise ValueError(f"Unknown plane: {plane!r}. Expected 'xy', 'xz', or 'yz'.")

    limit = max_val * margin
    return -limit, limit


def main():
    global fig

    args = parse_args()

    # 解析参数
    if args.json_file:
        _family_path = Path(args.json_file)
        _family_name = _family_path.stem
    else:
        _family_name = DEFAULT_FAMILY_NAME
        if _family_name.startswith("dro_"):
            _family_dir = project_root / "output" / "dro"
        else:
            _family_dir = project_root / "output" / "ro"
        _family_path = _family_dir / f"{_family_name}.json"

    _plane = args.plane
    _show_3d = args.show_3d
    _figure_size = tuple(args.fig_size)

    plt.ion()  # 开启交互模式

    # 创建全局图形窗口
    fig = plt.figure(figsize=_figure_size)

    # 加载系统
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    # 加载轨道族
    print(f"加载轨道族: {_family_name}")
    family = OrbitFamily.load_from_file(filename=_family_path, system=system)
    n_orbits = len(family)
    print(f"共 {n_orbits} 条轨道")

    # 预计算所有轨道的Jacobi常数
    print("正在计算Jacobi常数...")
    jacobi_values = precompute_jacobi_for_family(family, system)
    jacobi_min = min(jacobi_values)
    jacobi_max = max(jacobi_values)
    print(f"Jacobi常数范围: {jacobi_min:.6f} ~ {jacobi_max:.6f}")

    # 计算全局轴范围
    print("正在计算轴范围...")
    xlim, ylim = compute_global_axis_limits(family, plane=_plane)
    print(f"轴范围: [{xlim:.3f}, {ylim:.3f}]")

    # 创建可视化器
    orbit_plotter = OrbitVisualizer(system=system)
    orbit_plotter.config.figsize_2d = _figure_size

    # 设置天体和拉格朗日点样式（参考 plot_32_ro_family.py）
    orbit_plotter.primary_body_color = "blue"
    orbit_plotter.secondary_body_color = "silver"
    orbit_plotter.libration_point_colors = ["gray"] * 5
    orbit_plotter.libration_point_markers = ["^"] * 5
    orbit_plotter.libration_point_sizes = [60] * 5

    # 颜色映射
    cmap = matplotlib.colormaps["coolwarm"]

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
        jacobi = jacobi_values[current_idx]
        period = orbit.period if orbit.period else 0.0

        print(f"\n[{current_idx + 1}/{n_orbits}] 轨道信息:")
        print(
            f"  状态向量: [{orbit.states[0][0]:.6f}, {orbit.states[0][1]:.6f}, "
            f"{orbit.states[0][2]:.6f}, {orbit.states[0][3]:.6f}, "
            f"{orbit.states[0][4]:.6f}, {orbit.states[0][5]:.6f}]"
        )
        print(f"  Jacobi常数: {jacobi:.6f}")
        print(f"  周期: {period:.4f} TU ({period * TU:.4f} days)")

        # 清除上一帧
        fig.clf()

        # 2D投影
        if _show_3d:
            ax_2d = fig.add_subplot(1, 2, 1)
            ax_3d = fig.add_subplot(1, 2, 2, projection="3d")
        else:
            ax_2d = fig.add_subplot(111)
            ax_3d = None

        # 根据Jacobi值计算颜色
        norm_jacobi = (
            (jacobi - jacobi_min) / (jacobi_max - jacobi_min)
            if jacobi_max != jacobi_min
            else 0.5
        )
        orbit_color = cmap(norm_jacobi)

        # 绘制主天体和平动点
        orbit_plotter.plot_primary_bodies(ax=ax_2d)
        orbit_plotter.plot_libration_points(ax=ax_2d)

        # 绘制轨道
        label = f"Orbit {current_idx + 1} (C={jacobi:.4f})"
        orbit_plotter.plot_2d_projection(
            orbit,
            plane=_plane,
            color=orbit_color,  # type: ignore[arg-type]
            label=label,
            ax=ax_2d,
        )
        ax_2d.set_title(f"XY Plane - Orbit {current_idx + 1}/{n_orbits}")
        ax_2d.legend(loc="upper right")
        ax_2d.set_aspect("equal")

        # 设置统一的轴范围
        ax_2d.set_xlim(xlim, ylim)
        ax_2d.set_ylim(xlim, ylim)

        # 添加颜色条
        sm = plt.cm.ScalarMappable(
            cmap=cmap, norm=Normalize(vmin=jacobi_min, vmax=jacobi_max)
        )
        sm.set_array([])
        divider = make_axes_locatable(ax_2d)
        cax = divider.append_axes("right", size="2%", pad=0.1)
        cbar = plt.colorbar(sm, cax=cax)
        style_colorbar(cbar, PLOT_CONFIG, "Jacobi Constant")

        # 3D视图
        if _show_3d:
            if ax_3d is None:
                raise RuntimeError("3D axis not initialized")
            orbit_plotter.plot_primary_bodies(ax=ax_3d, is_3d=True)
            orbit_plotter.plot_libration_points(ax=ax_3d, is_3d=True, show_labels=True)
            orbit_plotter.plot_3d_orbit(orbit, color=orbit_color, label=label, ax=ax_3d)  # type: ignore[arg-type]
            ax_3d.set_title(f"3D View - Orbit {current_idx + 1}/{n_orbits}")
            ax_3d.legend(loc="upper right")

        plt.tight_layout()
        fig.canvas.draw()
        fig.canvas.flush_events()

        try:
            user_input = (
                input("\n命令 (Enter继续, q退出, s跳过, j跳转, r重绘): ")
                .strip()
                .lower()
            )
        except EOFError:
            # 非交互环境
            break

        if user_input == "q":
            print("退出程序")
            break
        elif user_input.startswith("s "):
            # 跳过N条轨道
            try:
                skip_n = int(user_input.split()[1])
                current_idx = min(current_idx + skip_n, n_orbits - 1)
                print(f"跳转到轨道 {current_idx + 1}")
            except (ValueError, IndexError):
                print("无效的跳过数量")
        elif user_input.startswith("j "):
            # 跳转到指定轨道
            try:
                target = int(user_input.split()[1])
                current_idx = max(0, min(target - 1, n_orbits - 1))
                print(f"跳转到轨道 {current_idx + 1}")
            except (ValueError, IndexError):
                print("无效的轨道编号")
        elif user_input == "r":
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
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--plane", "xy",                              # 投影平面
            "--fig-size", "10", "8",                      # 图形大小 (宽 高)
        ]
        print("[debug] 使用代码内置调试参数")
    main()
