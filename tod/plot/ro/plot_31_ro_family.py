"""
可视化 3:1 共振轨道族

本脚本实现：
1. 加载3:1 RO轨道族数据
2. 计算Jacobi常数和稳定性指数
3. 创建2D和3D可视化
4. 创建周期-稳定性参数图

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization import FamilyPlotter
from e2m2e.algorithms.stability import StabilityAnalysis
from tod.commons.common import MU, TU
from tod.commons.plot_helpers import apply_standard_plot_config
from tod.commons.common import find_project_root
import logging

logger = logging.getLogger(__name__)
project_root = find_project_root(Path(__file__))


def parse_args():
    parser = argparse.ArgumentParser(description="绘制 3:1 共振轨道族")
    parser.add_argument("--json-file", type=str, default=None, help="轨道族 JSON 文件路径")
    parser.add_argument("--start", type=int, default=-1, help="起始轨道索引，-1 表示从第一条")
    parser.add_argument("--end", type=int, default=-1, help="结束轨道索引（含），-1 表示到最后一条")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = project_root / "output" / "ro"

    if args.json_file:
        family_path = Path(args.json_file)
        family_name = family_path.stem
    else:
        family_name = "ro_31_family_-0.8905--0.8304999999999999-0.001_3857720079"
        family_path = output_dir / f"{family_name}.json"

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    if not family_path.exists():
        logger.info(f"数据文件不存在: {family_path}")
        logger.info("请先运行生成脚本，或更新文件路径")
        raise SystemExit(1)

    family_result = OrbitFamily.load_from_file(filename=family_path, system=system)

    n_orbits = len(family_result)
    logger.info(f"加载了 {n_orbits} 条 3:1 RO轨道")

    # =============================================================================
    # 绘制范围控制变量
    # =============================================================================
    PLOT_START_IDX = args.start
    PLOT_END_IDX = args.end

    if PLOT_START_IDX == -1 and PLOT_END_IDX == -1:
        plot_start = 0
        plot_end = n_orbits - 1
    elif PLOT_START_IDX == -1:
        plot_start = 0
        plot_end = min(PLOT_END_IDX, n_orbits - 1)
    elif PLOT_END_IDX == -1:
        plot_start = min(PLOT_START_IDX, n_orbits - 1)
        plot_end = n_orbits - 1
    else:
        plot_start = min(PLOT_START_IDX, n_orbits - 1)
        plot_end = min(PLOT_END_IDX, n_orbits - 1)

    n_orbits_to_plot = plot_end - plot_start + 1
    logger.info(f"将绘制第 {plot_start} 至 第 {plot_end} 条轨道，共 {n_orbits_to_plot} 条")

    # =============================================================================
    # 计算Jacobi常数和稳定性指数
    # =============================================================================
    logger.info("正在计算Jacobi常数和稳定性指数...")

    subset_family = OrbitFamily(system=system)
    for i in range(plot_start, plot_end + 1):
        subset_family.add_orbit(family_result[i])

    jacobi_values = family_result.get_jacobi_constants().tolist()
    jacobi_values_subset = [jacobi_values[i] for i in range(plot_start, plot_end + 1)]
    periods_subset = [family_result.periods[i] for i in range(plot_start, plot_end + 1)]
    stability_values_subset = []
    for i in range(plot_start, plot_end + 1):
        orbit = family_result[i]
        stability_analysis = StabilityAnalysis(orbit=orbit)
        stability_indices = stability_analysis.compute_stability_index()
        stability_values_subset.append(stability_indices.get("broucke", 0.0))
    logger.info(f"Jacobi常数范围: {min(jacobi_values):.6f} ~ {max(jacobi_values):.6f}")
    logger.info(f"稳定性指数范围: {min(stability_values_subset):.6f} ~ {max(stability_values_subset):.6f}")

    sort_idx = np.argsort(jacobi_values_subset)
    jacobi_sorted = np.array(jacobi_values_subset)[sort_idx].tolist()
    periods_sorted = np.array(periods_subset)[sort_idx].tolist()
    stability_sorted = np.array(stability_values_subset)[sort_idx].tolist()

    target_period = 2 * np.pi

    # =============================================================================
    # 创建绘图器
    # =============================================================================
    config = apply_standard_plot_config()
    plotter = FamilyPlotter(system, config)

    jacobi_min = min(jacobi_values_subset)
    jacobi_max = max(jacobi_values_subset)
    seed_orbit = family_result[0]
    seed_jacobi = jacobi_values[0]
    seed_stability = stability_values_subset[0]

    # =============================================================================
    # 1. 2D视图（XY平面）
    # =============================================================================
    fig_2d, ax_2d = plotter.plot_family_2d(
        subset_family,
        jacobi_values_subset,
        title=(
            f"3:1 Resonant Orbit Family in Earth-Moon CR3BP (XY Plane) - {n_orbits} orbits\n"
            f"C = [{jacobi_min:.4f}, {jacobi_max:.4f}], "
            f"λmax = [{min(stability_values_subset):.4f}, {max(stability_values_subset):.4f}]"
        ),
        plane="xy",
        show=False,
    )
    plotter.plot_2d_projection(
        seed_orbit,
        color="red",
        label=f"Seed 3:1 RO (C={seed_jacobi:.4f}, λmax={seed_stability:.4f})",
        ax=ax_2d,
    )
    plt.tight_layout()
    plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")

    # =============================================================================
    # 2. 3D视图
    # =============================================================================
    fig_3d, ax_3d = plotter.plot_family_3d(
        subset_family,
        jacobi_values_subset,
        title=(
            f"3:1 Resonant Orbit Family in Earth-Moon CR3BP (3D View) - {n_orbits} orbits\n"
            f"C = [{jacobi_min:.4f}, {jacobi_max:.4f}], "
            f"λmax = [{min(stability_values_subset):.4f}, {max(stability_values_subset):.4f}]"
        ),
        center=(-0.85, 0, 0),
        radius=0.5,
        elev=0,
        azim=-90,
        show=False,
    )
    plotter.plot_3d_orbit(
        seed_orbit,
        color="red",
        label=f"Seed 3:1 RO (C={seed_jacobi:.4f})",
        ax=ax_3d,
        show_start=True,
    )
    plt.tight_layout()
    plt.savefig(output_dir / f"{family_name}_3d_view.png", dpi=300, bbox_inches="tight")

    # =============================================================================
    # 3. Jacobi常数-周期-稳定性图
    # =============================================================================
    plotter.plot_jacobi_period_stability(
        jacobi_sorted,
        periods_sorted,
        stability_sorted,
        title=(
            f"3:1 Resonant Orbit Family - Period and Stability\n"
            f"Period Target: {target_period:.4f} TU ({target_period * TU:.2f} days)"
        ),
        target_period=target_period,
        save_path=str(output_dir / f"{family_name}_period_stability.png"),
        show=False,
    )

    logger.info(f"\n完成！图像已保存到 output/ro/ 目录")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        sys.argv += [
            "--start", "-1",                              # 起始轨道索引，-1 表示从第一条
            "--end", "-1",                                # 结束轨道索引（含），-1 表示到最后一条
        ]
        logger.debug("使用代码内置调试参数")
    main()
