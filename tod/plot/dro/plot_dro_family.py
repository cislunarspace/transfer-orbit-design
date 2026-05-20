import argparse
import logging
import sys
import warnings
from pathlib import Path

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization import FamilyPlotter
from e2m2e.algorithms.stability import StabilityAnalysis

from tod.commons.common import MU
from tod.commons.plot_helpers import apply_standard_plot_config
from tod.commons.common import find_project_root

logger = logging.getLogger(__name__)
project_root = find_project_root(Path(__file__))


def parse_args():
    parser = argparse.ArgumentParser(description="绘制 DRO 轨道族")
    parser.add_argument("--json-file", type=str, default=None, help="轨道族 JSON 文件路径")
    parser.add_argument("--plot-global-2d", action="store_true", help="绘制 DRO 轨道族在 XY 平面的全局 2D 视图")
    parser.add_argument("--plot-global-3d", action="store_true", help="绘制 DRO 轨道族在 3D 空间的全局视图")
    parser.add_argument("--plot-center", type=str, default="moon", choices=["moon", "earth", "emb"],
                        help="3D 视图的绘图中心：moon=月球, earth=地球, emb=地月质心")
    parser.add_argument("--plot-elev", type=float, default=20.0, help="3D 视图仰角（度）")
    parser.add_argument("--plot-azim", type=float, default=-60.0, help="3D 视图方位角（度）")
    parser.add_argument("--plot-jacobi-stability", action="store_true", help="绘制 Jacobi 常数与周期、稳定性的关系曲线")
    parser.add_argument("--no-show", action="store_true", help="只保存图片，不弹窗显示")
    return parser.parse_args()


def get_center_coordinates(center_type: str, mu: float) -> tuple[float, float, float]:
    """根据中心类型返回旋转坐标系中的坐标。

    Args:
        center_type: "moon", "earth", 或 "emb"
        mu: 地月质量比

    Returns:
        (x, y, z) 坐标元组
    """
    if center_type == "moon":
        return (1.0 - mu, 0.0, 0.0)
    elif center_type == "earth":
        return (0.0, 0.0, 0.0)
    elif center_type == "emb":
        return (mu, 0.0, 0.0)
    else:
        raise ValueError(f"Unknown center type: {center_type}")


def main() -> None:
    args = parse_args()
    output_dir = project_root / "output" / "dro"

    # 如果所有绘图开关都未启用，输出警告并跳过
    if not args.plot_global_2d and not args.plot_global_3d and not args.plot_jacobi_stability:
        logger.warning("未选择任何图表，跳过绘制")
        return

    if args.json_file:
        family_path = Path(args.json_file)
        family_name = family_path.stem
    else:
        family_name = "dro_31_family_0.141886-0.9-0.005_1779175978"
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

    # =============================================================================
    # 计算 Jacobi 常数（全局2D视图和稳定性图都需要）
    # =============================================================================
    logger.info("正在计算Jacobi常数...")
    jacobi_values = family_result.get_jacobi_constants().tolist()
    logger.info(f"Jacobi常数范围: {min(jacobi_values):.6f} ~ {max(jacobi_values):.6f}")

    # 仅在需要稳定性图时才计算（计算代价较高）
    if args.plot_jacobi_stability:
        logger.info("正在计算稳定性指数...")
        stability_values = []
        for i in range(len(family_result)):
            orbit = family_result[i]
            stability_analysis = StabilityAnalysis(orbit=orbit)
            stability_indices = stability_analysis.compute_stability_index()
            stability_values.append(stability_indices.get("broucke", 0.0))
        logger.info(f"稳定性指数范围: {min(stability_values):.6f} ~ {max(stability_values):.6f}")

    plotter = FamilyPlotter(system, config)

    # =============================================================================
    # 1. Global 2D view
    # =============================================================================
    if args.plot_global_2d:
        plotter.plot_family_2d(
            family_result, jacobi_values,
            save_path=str(output_dir / f"{family_name}_global_2d_view.png"),
            step=5
        )

    # =============================================================================
    # 2. Global 3D view (configurable center)
    # =============================================================================
    if args.plot_global_3d:
        import matplotlib.pyplot as plt
        import math

        center = get_center_coordinates(args.plot_center, MU)
        elev_deg = args.plot_elev
        azim_deg = args.plot_azim

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*Tight layout.*")
            fig_3d, ax_3d = plotter.plot_family_3d(
                family_result, jacobi_values,
                title=f"DRO Family in Earth-Moon CR3BP (3D) — {n_orbits} orbits\n"
                      f"Center: {args.plot_center.title()}, Elev: {elev_deg:.1f}°, Azim: {azim_deg:.1f}°",
                center=center,
                radius=1.5,
                elev=elev_deg,
                azim=azim_deg,
                show_bodies=True,
                show_libration=True,
                show_colorbar=True,
                step=5,
                show=False,
            )
        plt.savefig(output_dir / f"{family_name}_global_3d_view.png", dpi=300, bbox_inches="tight")
        if not args.no_show:
            plt.show()
        else:
            plt.close(fig_3d)

    # =============================================================================
    # 3. Jacobi-Period-Stability
    # =============================================================================
    if args.plot_jacobi_stability:
        plotter.plot_jacobi_period_stability(
            jacobi_values, family_result.periods, stability_values,
            save_path=str(output_dir / f"{family_name}_jacobi_period_stability.png"),
        )

    logger.info("\n所有图表已保存到 output/dro/ 目录:")
    if args.plot_global_2d:
        logger.info(f"  - {family_name}_global_2d_view.png      : 全局2D视图")
    if args.plot_global_3d:
        logger.info(f"  - {family_name}_global_3d_view.png      : 全局3D视图")
    if args.plot_jacobi_stability:
        logger.info(f"  - {family_name}_jacobi_period_stability.png : Jacobi常数-周期-稳定性图")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        logger.debug("使用代码内置调试参数")
    main()
