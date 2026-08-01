# pyright: reportAttributeAccessIssue=false
"""plot_interactive_orbit_inspector 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.inspection.plot_interactive_orbit_inspector --help
"""

import argparse
import logging
import sys
from pathlib import Path

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

import e2m2e
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization.base import OrbitVisualizer
from tod.commons.constants import MU, TU
from tod.plot.config import apply_standard_plot_config, style_colorbar
from tod.commons.input_contract import (
    InputFileRequest,
    InputResolutionError,
    resolve_input_file,
)
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable
from tod.commons.paths import find_project_root

logger = logging.getLogger(__name__)
project_root = find_project_root(Path(__file__))

PLOT_CONFIG = apply_standard_plot_config()

def parse_args():
    """解析命令行参数。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="交互式轨道检查器", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--json-file", type=str, default=None, help="轨道族 JSON 文件路径"
    )
    parser.add_argument(
        "--auto-latest", action="store_true",
        help="选最新的 ro_*.json 或 dro_*.json",
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

# 旧的 ``DEFAULT_FAMILY_NAME`` 硬编码默认文件被 issue #183 移除：
# - ``--json-file`` 必填或使用 ``--auto-latest`` 自动选最新
# - 直跑 ``python -m tod.plot.inspection.plot_interactive_orbit_inspector``
#   不再自动注入默认参数（见 ``__main__`` 块注释）

# 全局图形窗口（在 main() 中初始化）
fig = None

def compute_orbit_jacobi(orbit, system):
    """计算单条轨道的Jacobi常数"""
    dynamics = e2m2e.core.CR3BP_Dynamics(system=system)
    try:
        return dynamics.compute_jacobi_constant(orbit.states[0])
    # compute_jacobi_constant 是纯 numpy 计算，只在数值溢出/非法值时失败
    except (FloatingPointError, ValueError):
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

    # 解析参数：按 issue #183 契约解析 --json-file 或 --auto-latest
    parser_obj = argparse.ArgumentParser(prog="plot_interactive_orbit_inspector", description="交互式轨道检查器")
    try:
        # 默认在 output/ro 下搜；若 ro 下没有 ro_*.json，回退到 output/dro
        # （保持旧版「dro_ 前缀走 output/dro」分类行为，但仍然不硬编码文件名）
        ro_root = project_root / "output" / "ro"
        dro_root = project_root / "output" / "dro"
        primary_root = ro_root if ro_root.is_dir() else dro_root
        primary_pattern = "ro_*.json" if primary_root is ro_root else "dro_*.json"

        _family_path = resolve_input_file(
            InputFileRequest(
                explicit_path=Path(args.json_file) if args.json_file else None,
                auto_latest=bool(args.auto_latest),
                search_root=primary_root,
                pattern=primary_pattern,
                flag="--json-file",
                auto_latest_flag="--auto-latest",
            )
        )
        _family_name = _family_path.stem
    except InputResolutionError as exc:
        msg = str(exc)
        if exc.candidates or exc.remaining:
            msg = f"{msg}\n候选 (修改时间新→旧):\n{exc.format_candidates()}"
        parser_obj.error(msg)
        return  # unreachable; parser.error exits 2

    _plane = args.plane
    _show_3d = args.show_3d
    _figure_size = tuple(args.fig_size)

    plt.ion()  # 开启交互模式

    # 创建全局图形窗口
    fig = plt.figure(figsize=_figure_size)

    # 加载系统
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    # 加载轨道族
    logger.info(f"加载轨道族: {_family_name}")
    family = OrbitFamily.load_from_file(filename=_family_path, system=system)
    n_orbits = len(family)
    logger.info(f"共 {n_orbits} 条轨道")

    # 预计算所有轨道的Jacobi常数
    logger.info("正在计算Jacobi常数...")
    jacobi_values = precompute_jacobi_for_family(family, system)
    jacobi_min = min(jacobi_values)
    jacobi_max = max(jacobi_values)
    logger.info(f"Jacobi常数范围: {jacobi_min:.6f} ~ {jacobi_max:.6f}")

    # 计算全局轴范围
    logger.info("正在计算轴范围...")
    xlim, ylim = compute_global_axis_limits(family, plane=_plane)
    logger.info(f"轴范围: [{xlim:.3f}, {ylim:.3f}]")

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

    logger.info("\n" + "=" * 60)
    logger.info("交互式轨道检查器")
    logger.info("=" * 60)
    logger.info("按 Enter: 绘制下一条轨道")
    logger.info("输入 'q': 退出程序")
    logger.info("输入 's N': 跳过N条轨道")
    logger.info("输入 'j N': 跳转到第N条轨道")
    logger.info("输入 'r': 重新绘制当前轨道")
    logger.info("=" * 60 + "\n")

    while True:
        # 显示当前轨道信息
        orbit = family[current_idx]
        jacobi = jacobi_values[current_idx]
        period = orbit.period if orbit.period else 0.0

        logger.info(f"\n[{current_idx + 1}/{n_orbits}] 轨道信息:")
        logger.info(
            f"  状态向量: [{orbit.states[0][0]:.6f}, {orbit.states[0][1]:.6f}, "
            f"{orbit.states[0][2]:.6f}, {orbit.states[0][3]:.6f}, "
            f"{orbit.states[0][4]:.6f}, {orbit.states[0][5]:.6f}]"
        )
        logger.info(f"  Jacobi常数: {jacobi:.6f}")
        logger.info(f"  周期: {period:.4f} TU ({period * TU:.4f} days)")

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
            logger.info("退出程序")
            break
        elif user_input.startswith("s "):
            # 跳过N条轨道
            try:
                skip_n = int(user_input.split()[1])
                current_idx = min(current_idx + skip_n, n_orbits - 1)
                logger.info(f"跳转到轨道 {current_idx + 1}")
            except (ValueError, IndexError):
                logger.info("无效的跳过数量")
        elif user_input.startswith("j "):
            # 跳转到指定轨道
            try:
                target = int(user_input.split()[1])
                current_idx = max(0, min(target - 1, n_orbits - 1))
                logger.info(f"跳转到轨道 {current_idx + 1}")
            except (ValueError, IndexError):
                logger.info("无效的轨道编号")
        elif user_input == "r":
            # 重新绘制当前轨道（不前进）
            logger.info(f"重绘轨道 {current_idx + 1}")
            continue
        else:
            # 下一条轨道
            if current_idx < n_orbits - 1:
                current_idx += 1
            else:
                logger.info("已到达最后一条轨道")
                break

    logger.info(f"\n检查完成，共检查了 {current_idx + 1} 条轨道")

if __name__ == "__main__":
    # 旧版 F5 直跑自动注入默认参数已被 issue #183 移除：
    # 直跑也会进入「需要显式输入」契约失败路径。开发者请显式传：
    #   --json-file <path> 或 --auto-latest
    main()

# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='inspection',
    name='plot_interactive_orbit_inspector',
    description='交互检查',
    script_path='tod/plot/inspection/plot_interactive_orbit_inspector.py',
    group_label='交互式检查',
    cli_params=[
        CliParam('--json-file', '轨道族文件', 'str', '', help='轨道族 JSON 文件路径。'),
        CliParam('--auto-latest', '自动选最新', 'bool', '', help='选最新的 ro_*.json 或 dro_*.json；与 --json-file 互斥。', advanced=True),
        CliParam('--plane', '投影平面', 'str', 'xy', help='投影平面: xy, xz, yz。'),
        CliParam('--show-3d', '显示 3D 视图', 'bool', '', help='同时显示 3D 视图。'),
        CliParam('--fig-size', '图形大小', 'str', '10 8', help='图形大小 (宽 高)。'),
    ],
)
