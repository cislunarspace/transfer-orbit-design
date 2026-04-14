import argparse
from pathlib import Path
import matplotlib
import e2m2e
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization import PlotConfig, FamilyPlotter, compute_stability_for_family

project_root = Path(__file__).resolve().parent.parent.parent
from scripts.utils.common import MU

# =============================================================================
# Configuration
# =============================================================================
config = PlotConfig(
    title=32,                    # 子图标题字号
    label=28,                    # 坐标轴标签字号
    tick=26,                     # 刻度标签字号
    legend=28,                   # 图例字号
    colorbar=26,                 # 色标字号
    suptitle=36,                 # 总标题字号
    lp_label=32,                 # Lagrange点标注字号
    title_y_offset=-0.12,        # 2D子图标题Y方向偏移
    title_y_offset_3d=-0.08,     # 3D子图标题Y方向偏移
    title_y_offset_dual=-0.18,   # 双子图标题Y方向偏移
    title_y_offset_subplot=-0.15,# 多子图标题Y方向偏移
)
config.apply_rcparams()          # 将配置应用到 matplotlib 全局参数


def parse_args():
    parser = argparse.ArgumentParser(description="绘制 DRO 轨道族")
    parser.add_argument("--json-file", type=str, default=None, help="轨道族 JSON 文件路径")
    return parser.parse_args()


# =============================================================================
# Load data
# =============================================================================
args = parse_args()
output_dir = project_root / "output" / "dro"

if args.json_file:
    family_path = Path(args.json_file)
    family_name = family_path.stem
else:
    family_name = "dro_family_0.141886-0.9-0.005_3857978855"
    family_path = output_dir / f"{family_name}.json"

system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

if not family_path.exists():
    print(f"数据文件不存在: {family_path}")
    print("请先运行生成脚本，或更新文件路径")
    raise SystemExit(1)

family_result = OrbitFamily.load_from_file(filename=family_path, system=system)

n_orbits = len(family_result)
print(f"加载了 {n_orbits} 条DRO轨道")

print("正在计算Jacobi常数...")
jacobi_values = family_result.get_jacobi_constants().tolist()
print(f"Jacobi常数范围: {min(jacobi_values):.6f} ~ {max(jacobi_values):.6f}")

print("正在计算稳定性指数...")
stability_values = compute_stability_for_family(family_result, family_result.system)
print(f"稳定性指数范围: {min(stability_values):.6f} ~ {max(stability_values):.6f}")

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

print("\n所有图表已保存到 output/dro/ 目录:")
print(f"  - {family_name}_global_2d_view.png      : 全局2D视图")
print(f"  - {family_name}_jacobi_period_stability.png : Jacobi常数-周期-稳定性图")
