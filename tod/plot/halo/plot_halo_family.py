"""
绘制 Halo 轨道族

本脚本实现：
1. 加载 Halo 轨道数据
2. 计算 Jacobi 常数
3. 计算稳定性指数
4. 创建 2D 和 3D 可视化
5. 创建 Jacobi 常数-周期-稳定性联合图

用法::

    # 2D 视图
    python -m tod.plot.halo.plot_halo_family --json-file output/halo/halo_L1_N_family_*.json --view-2d

    # 3D 视图
    python -m tod.plot.halo.plot_halo_family --json-file output/halo/halo_L1_N_family_*.json --view-3d

    # Jacobi-周期-稳定性联合图
    python -m tod.plot.halo.plot_halo_family --json-file output/halo/halo_L1_N_family_*.json --jacobi-period-stability

    # 组合多个视图
    python -m tod.plot.halo.plot_halo_family --json-file output/halo/halo_L1_N_family_*.json --view-2d --view-3d --jacobi-period-stability

    # 指定轨道范围
    python -m tod.plot.halo.plot_halo_family --json-file output/halo/halo_L1_N_family_*.json --view-2d --start 0 --end 50
"""

from __future__ import annotations

import argparse
import json
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

import warnings

import matplotlib.pyplot as plt
import numpy as np
from e2m2e.algorithms.stability import StabilityAnalysis
from e2m2e.core import Orbit, OrbitFamily, CR3BP_System
from e2m2e.visualization import FamilyPlotter
from tod.commons.common import MU, find_project_root
from tod.commons.plot_helpers import apply_standard_plot_config

logger = logging.getLogger(__name__)
project_root = find_project_root(Path(__file__))

PLOT_CONFIG = apply_standard_plot_config()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="绘制 Halo 轨道族")
    parser.add_argument(
        "--json-file",
        type=str,
        default=None,
        help="轨道族 JSON 文件路径",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=-1,
        help="起始轨道索引，-1 表示从第一条",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=-1,
        help="结束轨道索引（含），-1 表示到最后一条",
    )
    # 图表选择
    parser.add_argument(
        "--view-2d",
        action="store_true",
        help="绘制 Halo 轨道族在 XZ 平面的 2D 视图",
    )
    parser.add_argument(
        "--view-3d",
        action="store_true",
        help="绘制 Halo 轨道族的 3D 示意图",
    )
    parser.add_argument(
        "--jacobi-period-stability",
        action="store_true",
        help="绘制 Jacobi 常数-周期-稳定性联合图",
    )
    return parser.parse_args()


def compute_view_bounds(all_states: np.ndarray) -> tuple:
    """根据轨道状态数组计算 2D 与 3D 视图的边界参数。

    Returns:
        (xlim_2d, ylim_2d, center_3d, radius_3d)
    """
    if all_states.size == 0:
        return (0.8, 1.2), (-0.3, 0.3), (1.0, 0.0, 0.0), 0.4
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


def _compute_stability_indices(family: OrbitFamily) -> list[float]:
    """计算轨道族的稳定性指数。"""
    stability_values = []
    for i in range(len(family)):
        orbit = family[i]
        stability_analysis = StabilityAnalysis(orbit=orbit)
        stability_indices = stability_analysis.compute_stability_index()
        stability_values.append(stability_indices.get("broucke", 0.0))
    return stability_values


def _plot_2d_view(
    plotter: FamilyPlotter,
    subset_family: OrbitFamily,
    jacobi_subset: list[float],
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    output_dir: Path,
    family_name: str,
    n_orbits: int,
) -> None:
    """绘制全局 2D 视图（XZ 平面）。"""
    jmin, jmax = min(jacobi_subset), max(jacobi_subset)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*Tight layout.*")
        plotter.plot_family_2d(
            subset_family,
            jacobi_subset,
            title=f"Halo Orbit Family in Earth-Moon CR3BP (XZ Plane) - {n_orbits} orbits\n"
            f"C = [{jmin:.4f}, {jmax:.4f}]",
            plane="xz",
            show_bodies=True,
            show_libration=True,
            show_colorbar=True,
            xlim=xlim,
            ylim=ylim,
            show=False,
        )
    plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")
    plt.show()


def _plot_3d_view(
    plotter: FamilyPlotter,
    subset_family: OrbitFamily,
    jacobi_subset: list[float],
    center_3d: tuple[float, float, float],
    radius_3d: float,
    output_dir: Path,
    family_name: str,
    n_orbits: int,
) -> None:
    """绘制全局 3D 视图。"""
    jmin, jmax = min(jacobi_subset), max(jacobi_subset)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*Tight layout.*")
        plotter.plot_family_3d(
            subset_family,
            jacobi_subset,
            title=f"Halo Orbit Family in Earth-Moon CR3BP (3D View) - {n_orbits} orbits\n"
            f"C = [{jmin:.4f}, {jmax:.4f}]",
            center=center_3d,
            radius=radius_3d,
            elev=20,
            azim=-60,
            show=False,
        )
    plt.savefig(output_dir / f"{family_name}_3d_view.png", dpi=300, bbox_inches="tight")
    plt.show()


def _plot_jacobi_period_stability(
    plotter: FamilyPlotter,
    jacobi_sorted: list[float],
    periods_sorted: list[float],
    stability_sorted: list[float],
    output_dir: Path,
    family_name: str,
    n_orbits: int,
) -> None:
    """绘制 Jacobi 常数-周期-稳定性联合图。"""
    plotter.plot_jacobi_period_stability(
        jacobi_sorted,
        periods_sorted,
        stability_sorted,
        title=f"Halo Orbit Family - Period and Stability (n = {n_orbits})",
        save_path=str(output_dir / f"{family_name}_period_stability.png"),
        show=True,
    )


def main(
    plot1: bool | None = None,
    plot2: bool | None = None,
    plot3: bool | None = None,
) -> None:
    args = parse_args()

    # 从 CLI 参数或函数参数获取绘图开关
    if plot1 is None:
        plot1 = bool(args.view_2d)
    if plot2 is None:
        plot2 = bool(args.view_3d)
    if plot3 is None:
        plot3 = bool(args.jacobi_period_stability)

    # 如果所有绘图开关都未启用，输出警告并跳过
    if not plot1 and not plot2 and not plot3:
        logger.warning("未选择任何图表，跳过绘制")
        return

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
        logger.info("请先生成 Halo 轨道数据，运行: python -m tod.generates.cr3bp.halo.generate_halo_family")
        sys.exit(1)

    n_orbits = len(family_result)
    logger.info(f"加载了 {n_orbits} 条 Halo 轨道")

    plot_start, plot_end = _resolve_plot_range(args.start, args.end, n_orbits)
    n_orbits_to_plot = plot_end - plot_start + 1
    logger.info(f"将绘制第 {plot_start} 至 第 {plot_end} 条轨道，共 {n_orbits_to_plot} 条")

    subset_family = OrbitFamily(system=system)
    for i in range(plot_start, plot_end + 1):
        subset_family.add_orbit(family_result[i])

    logger.info("正在计算 Jacobi 常数...")
    jacobi_values = family_result.get_jacobi_constants().tolist()
    jacobi_subset = [jacobi_values[i] for i in range(plot_start, plot_end + 1)]
    logger.info(f"Jacobi 常数范围: {min(jacobi_subset):.6f} ~ {max(jacobi_subset):.6f}")

    stability_subset: list[float] = []
    if plot3:
        logger.info("正在计算稳定性指数（可能较慢）...")
        stability_values = _compute_stability_indices(family_result)
        stability_subset = [stability_values[i] for i in range(plot_start, plot_end + 1)]
        logger.info(f"λmax 范围: {min(stability_subset):.6f} ~ {max(stability_subset):.6f}")

    sort_idx = np.argsort(jacobi_subset)
    jacobi_sorted = np.array(jacobi_subset)[sort_idx].tolist()
    periods_sorted = np.array(subset_family.periods)[sort_idx].tolist()
    # stability_subset 仅在 plot3=True 时非空，因此 stability_sorted 可能与 jacobi_sorted 长度不一致
    stability_sorted = np.array(stability_subset)[sort_idx].tolist() if stability_subset else []

    plotter = FamilyPlotter(system, PLOT_CONFIG)
    # 60/30 是平动点 marker 大小，用于 L1-L5 标注
    plotter.libration_point_sizes = [20, 20, 20, 20, 20]
    # 图标缩放使用 PLOT_CONFIG 中的默认值（primary_body_icon_scale=0.25）

    all_states = np.vstack([orbit.states for orbit in subset_family])
    xlim_2d, ylim_2d, center_3d, radius_3d = compute_view_bounds(all_states)

    if plot1:
        _plot_2d_view(plotter, subset_family, jacobi_subset,
                      xlim_2d, ylim_2d, output_dir, family_name, n_orbits)
    if plot2:
        _plot_3d_view(plotter, subset_family, jacobi_subset,
                      center_3d, radius_3d, output_dir, family_name, n_orbits)
    if plot3:
        _plot_jacobi_period_stability(plotter, jacobi_sorted, periods_sorted, stability_sorted,
                                      output_dir, family_name, n_orbits)

    logger.info(f"\n图表已保存到 {output_dir} 目录:")
    if plot1:
        logger.info(f"  - {family_name}_2d_view.png           : 全局 2D 视图 (XZ 平面)")
    if plot2:
        logger.info(f"  - {family_name}_3d_view.png           : 全局 3D 视图")
    if plot3:
        logger.info(f"  - {family_name}_period_stability.png  : Jacobi 常数-周期-稳定性图")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    if len(sys.argv) == 1:
        sys.argv += [
            "--start", "-1",
            "--end", "-1",
        ]
        # 待绘制轨道文件位置（修改此变量即可切换轨道文件）
        filepath = r"C:\Users\ouyan\codes\transfer-orbit-design\output\halo\halo_L1_N_0.1_1778419695.json"
        if filepath:
            sys.argv += ["--json-file", filepath]
        # 调试开关：1 = 绘制，0 = 跳过
        plot1 = 0  # 全局 2D 视图（XZ 平面）
        plot2 = 1  # 全局 3D 视图
        plot3 = 0  # Jacobi 常数-周期-稳定性图
        logger.debug("使用代码内置调试参数")
        main(plot1=plot1, plot2=plot2, plot3=plot3)
    else:
        main()
