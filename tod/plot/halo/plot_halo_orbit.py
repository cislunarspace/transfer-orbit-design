"""
可视化 Halo 轨道

本脚本实现：
1. 加载Halo轨道数据
2. 计算Jacobi常数
3. 创建2D和3D可视化
4. 创建Jacobi常数-周期图
"""

import argparse
from pathlib import Path
import sys
from tod.commons.common import find_project_root
import logging

logger = logging.getLogger(__name__)
project_root = find_project_root(Path(__file__))

sys.path.insert(0, str(project_root))

from tod.commons.plot_helpers import apply_standard_plot_config

PLOT_CONFIG = apply_standard_plot_config()

import json

import numpy as np
import matplotlib.pyplot as plt
import e2m2e
from e2m2e.core import Orbit, OrbitFamily, CR3BP_System
from e2m2e.visualization import FamilyPlotter

from tod.commons.common import MU


def parse_args():
    parser = argparse.ArgumentParser(description="绘制 Halo 轨道族")
    parser.add_argument("--json-file", type=str, default=None, help="轨道族 JSON 文件路径")
    parser.add_argument("--start", type=int, default=-1, help="起始轨道索引，-1 表示从第一条")
    parser.add_argument("--end", type=int, default=-1, help="结束轨道索引（含），-1 表示到最后一条")
    return parser.parse_args()


def compute_view_bounds(all_states: np.ndarray) -> tuple:
    """根据轨道状态数组计算 2D 与 3D 视图的边界参数。

    Returns:
        (xlim_2d, ylim_2d, center_3d, radius_3d)
    """
    x_min, x_max = all_states[:, 0].min(), all_states[:, 0].max()
    y_min, y_max = all_states[:, 1].min(), all_states[:, 1].max()
    z_min, z_max = all_states[:, 2].min(), all_states[:, 2].max()
    x_pad = max(0.05, (x_max - x_min) * 0.1)
    z_pad = max(0.05, (z_max - z_min) * 0.1)
    xlim_2d = (float(x_min - x_pad), float(x_max + x_pad))
    ylim_2d = (float(z_min - z_pad), float(z_max + z_pad))

    center_3d = (float((x_min + x_max) / 2), float((y_min + y_max) / 2), float((z_min + z_max) / 2))
    radius_3d = float(max(x_max - x_min, y_max - y_min, z_max - z_min) / 2 + max(x_pad, z_pad))
    return xlim_2d, ylim_2d, center_3d, radius_3d


def _load_family(family_path: Path, system: CR3BP_System) -> OrbitFamily:
    """加载轨道族 JSON 文件并返回 OrbitFamily 对象。"""
    with open(family_path, "r") as f:
        data = json.load(f)

    if "orbits" in data:
        return OrbitFamily.load_from_file(filename=family_path, system=system)

    orbit = Orbit.load_from_file(filename=family_path, system=system)
    family = OrbitFamily(system=system)
    family.add_orbit(orbit)
    return family


def _resolve_plot_range(start_idx: int, end_idx: int, n_orbits: int) -> tuple[int, int]:
    """解析 --start/--end 参数，返回 (plot_start, plot_end) 索引。"""
    if start_idx == -1 and end_idx == -1:
        return 0, n_orbits - 1
    if start_idx == -1:
        return 0, min(end_idx, n_orbits - 1)
    if end_idx == -1:
        return min(start_idx, n_orbits - 1), n_orbits - 1
    return min(start_idx, n_orbits - 1), min(end_idx, n_orbits - 1)


def _plot_2d_view(
    plotter: FamilyPlotter,
    subset_family: OrbitFamily,
    jacobi_subset: list[float],
    seed_orbit: Orbit,
    seed_jacobi: float,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    output_dir: Path,
    family_name: str,
    n_orbits: int,
) -> None:
    """绘制全局 2D 视图（XZ 平面）。"""
    jmin, jmax = min(jacobi_subset), max(jacobi_subset)
    _, ax_2d = plotter.plot_family_2d(
        subset_family, jacobi_subset,
        title=f"Halo Orbit Family in Earth-Moon CR3BP (XZ Plane) - {n_orbits} orbits\n"
              f"C = [{jmin:.4f}, {jmax:.4f}]",
        plane="xz",
        show_bodies=True, show_libration=True, show_colorbar=True,
        xlim=xlim, ylim=ylim,
        show=False,
    )
    plotter.plot_2d_projection(
        seed_orbit, plane="xz", color="red",
        label=f"Seed Halo (C={seed_jacobi:.4f})",
        ax=ax_2d,
    )
    plt.tight_layout()
    plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")
    plt.show()


def _plot_3d_view(
    plotter: FamilyPlotter,
    subset_family: OrbitFamily,
    jacobi_subset: list[float],
    seed_orbit: Orbit,
    seed_jacobi: float,
    center_3d: tuple[float, float, float],
    radius_3d: float,
    output_dir: Path,
    family_name: str,
    n_orbits: int,
) -> None:
    """绘制全局 3D 视图。"""
    jmin, jmax = min(jacobi_subset), max(jacobi_subset)
    _, ax_3d = plotter.plot_family_3d(
        subset_family, jacobi_subset,
        title=f"Halo Orbit Family in Earth-Moon CR3BP (3D View) - {n_orbits} orbits\n"
              f"C = [{jmin:.4f}, {jmax:.4f}]",
        center=center_3d, radius=radius_3d, elev=20, azim=-60,
        show=False,
    )
    plotter.plot_3d_orbit(
        seed_orbit, color="red",
        label=f"Seed Halo (C={seed_jacobi:.4f})",
        ax=ax_3d, show_start=True,
    )
    plt.tight_layout()
    plt.savefig(output_dir / f"{family_name}_3d_view.png", dpi=300, bbox_inches="tight")
    plt.show()


def _plot_jacobi_period(
    plotter: FamilyPlotter,
    jacobi_sorted: list[float],
    periods_sorted: list[float],
    output_dir: Path,
    family_name: str,
    n_orbits: int,
) -> None:
    """绘制 Jacobi 常数-周期图。"""
    plotter.plot_jacobi_period(
        jacobi_sorted, periods_sorted,
        title=f"Halo Orbit Family - Period\n(n = {n_orbits} orbits)",
        save_path=str(output_dir / f"{family_name}_jacobi_period.png"),
        show=True,
    )


def main(plot1: int = 1, plot2: int = 1, plot3: int = 1) -> None:
    args = parse_args()
    output_dir = project_root / "output" / "halo"

    if args.json_file:
        family_path = Path(args.json_file)
        family_name = family_path.stem
    else:
        family_name = "halo_L1_N_family_3857278981"
        family_path = output_dir / f"{family_name}.json"

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    try:
        family_result = _load_family(family_path, system)
    except FileNotFoundError:
        logger.error(f"文件不存在: {family_path}")
        logger.info("请先生成Halo轨道数据，运行: python -m tod.generates.cr3bp.halo.generate_halo_family")
        sys.exit(1)

    n_orbits = len(family_result)
    logger.info(f"加载了 {n_orbits} 条 Halo 轨道")

    plot_start, plot_end = _resolve_plot_range(args.start, args.end, n_orbits)
    n_orbits_to_plot = plot_end - plot_start + 1
    logger.info(f"将绘制第 {plot_start} 至 第 {plot_end} 条轨道，共 {n_orbits_to_plot} 条")

    subset_family = OrbitFamily(system=system)
    for i in range(plot_start, plot_end + 1):
        subset_family.add_orbit(family_result[i])

    logger.info("正在计算Jacobi常数...")
    jacobi_values = family_result.get_jacobi_constants().tolist()
    jacobi_subset = [jacobi_values[i] for i in range(plot_start, plot_end + 1)]
    logger.info(f"Jacobi常数范围: {min(jacobi_subset):.6f} ~ {max(jacobi_subset):.6f}")

    sort_idx = np.argsort(jacobi_subset)
    jacobi_sorted = np.array(jacobi_subset)[sort_idx].tolist()
    periods_sorted = np.array(subset_family.periods)[sort_idx].tolist()

    plotter = FamilyPlotter(system, PLOT_CONFIG)
    plotter.primary_body_size = 60
    plotter.secondary_body_size = 30
    plotter.libration_point_sizes = [20, 20, 20, 20, 20]

    all_states = np.vstack([orbit.states for orbit in subset_family])
    xlim_2d, ylim_2d, center_3d, radius_3d = compute_view_bounds(all_states)
    seed_orbit = family_result[0]
    seed_jacobi = jacobi_values[0]

    if plot1:
        _plot_2d_view(plotter, subset_family, jacobi_subset, seed_orbit, seed_jacobi,
                      xlim_2d, ylim_2d, output_dir, family_name, n_orbits)
    if plot2:
        _plot_3d_view(plotter, subset_family, jacobi_subset, seed_orbit, seed_jacobi,
                      center_3d, radius_3d, output_dir, family_name, n_orbits)
    if plot3:
        _plot_jacobi_period(plotter, jacobi_sorted, periods_sorted,
                            output_dir, family_name, n_orbits)

    logger.info(f"\n图表已保存到 {output_dir} 目录:")
    if plot1:
        logger.info(f"  - {family_name}_2d_view.png           : 全局2D视图 (XZ平面)")
    if plot2:
        logger.info(f"  - {family_name}_3d_view.png           : 全局3D视图")
    if plot3:
        logger.info(f"  - {family_name}_jacobi_period.png     : Jacobi常数-周期图")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--start", "-1",                              # 起始轨道索引，-1 表示从第一条
            "--end", "-1",                                # 结束轨道索引（含），-1 表示到最后一条
        ]
        # 待绘制轨道文件位置（修改此变量即可切换轨道文件）
        filepath = ""
        if filepath:
            sys.argv += ["--json-file", filepath]
        # 调试开关：1 = 绘制，0 = 跳过
        plot1 = 0  # 全局2D视图（XZ平面）
        plot2 = 1  # 全局3D视图
        plot3 = 0  # Jacobi常数-周期图
        logger.debug("使用代码内置调试参数")
        main(plot1=plot1, plot2=plot2, plot3=plot3)
    else:
        main()
