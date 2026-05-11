import argparse
import sys
from pathlib import Path
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization import FamilyPlotter
from e2m2e.algorithms.stability import StabilityAnalysis

from tod.commons.common import MU
from tod.commons.plot_helpers import apply_standard_plot_config
from tod.commons.common import find_project_root
import logging

logger = logging.getLogger(__name__)
project_root = find_project_root(Path(__file__))


def parse_args():
    parser = argparse.ArgumentParser(description="绘制 DRO 轨道族")
    parser.add_argument("--json-file", type=str, default=None, help="轨道族 JSON 文件路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = project_root / "output" / "dro"

    if args.json_file:
        family_path = Path(args.json_file)
        family_name = family_path.stem
    else:
        family_name = "dro_family_0.141886-0.9-0.005_3857978855"
        family_path = output_dir / f"{family_name}.json"

    # =============================================================================
    # Configuration
    # =============================================================================
    config = apply_standard_plot_config()          # 将配置应用到 matplotlib 全局参数

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    if not family_path.exists():
        logger.info(f"数据文件不存在: {family_path}")
        logger.info("请先运行生成脚本，或更新文件路径")
        raise SystemExit(1)

    family_result = OrbitFamily.load_from_file(filename=family_path, system=system)

    n_orbits = len(family_result)
    logger.info(f"加载了 {n_orbits} 条DRO轨道")

    logger.info("正在计算Jacobi常数...")
    jacobi_values = family_result.get_jacobi_constants().tolist()
    logger.info(f"Jacobi常数范围: {min(jacobi_values):.6f} ~ {max(jacobi_values):.6f}")

    logger.info("正在计算稳定性指数...")
    stability_values = []
    for i in range(len(family_result)):
        orbit = family_result[i]
        stability_analysis = StabilityAnalysis(orbit=orbit)
        stability_indices = stability_analysis.compute_stability_index()
        stability_values.append(stability_indices.get("broucke", 0.0))
    logger.info(f"稳定性指数范围: {min(stability_values):.6f} ~ {max(stability_values):.6f}")

    plotter = FamilyPlotter(system, config)

    jmin, jmax = min(jacobi_values), max(jacobi_values)
    smin, smax = min(stability_values), max(stability_values)

    # =============================================================================
    # 1. Global 2D view
    # =============================================================================
    plotter.plot_family_2d(
        family_result, jacobi_values,
        # title=f"DRO Family in Earth-Moon CR3BP (XY Plane) - {n_orbits} orbits\n"
            #   f"C = [{jmin:.4f}, {jmax:.4f}], λmax = [{smin:.4f}, {smax:.4f}]",
        save_path=str(output_dir / f"{family_name}_global_2d_view.png"),
        step=5
    )

    # =============================================================================
    # 3. Jacobi-Period-Stability
    # =============================================================================
    plotter.plot_jacobi_period_stability(
        jacobi_values, family_result.periods, stability_values,
        # title=f"DRO Family: Jacobi Constant vs Period and Stability\n(n = {n_orbits} orbits)",
        save_path=str(output_dir / f"{family_name}_jacobi_period_stability.png"),
    )

    logger.info("\n所有图表已保存到 output/dro/ 目录:")
    logger.info(f"  - {family_name}_global_2d_view.png      : 全局2D视图")
    logger.info(f"  - {family_name}_jacobi_period_stability.png : Jacobi常数-周期-稳定性图")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        logger.debug("使用代码内置调试参数")
    main()
