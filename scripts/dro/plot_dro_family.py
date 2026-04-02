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
    title=32,
    label=28,
    tick=26,
    legend=28,
    colorbar=26,
    suptitle=36,
    lp_label=32,
    title_y_offset=-0.12,
    title_y_offset_3d=-0.08,
    title_y_offset_dual=-0.18,
    title_y_offset_subplot=-0.15,
)
config.apply_rcparams()

# =============================================================================
# Load data
# =============================================================================
family_name = "dro_family_0.141886-0.9-0.005_3857978855"
output_dir = project_root / "output" / "dro"
family_path = output_dir / f"{family_name}.json"
system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
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
    title=f"DRO Family in Earth-Moon CR3BP (XY Plane) - {n_orbits} orbits\n"
          f"C = [{jmin:.4f}, {jmax:.4f}], λmax = [{smin:.4f}, {smax:.4f}]",
    save_path=str(output_dir / f"{family_name}_global_2d_view.png"),
)

# =============================================================================
# 2. Global 3D view
# =============================================================================
plotter.plot_family_3d(
    family_result, jacobi_values,
    title=f"DRO Family in Earth-Moon CR3BP (3D View) - {n_orbits} orbits\n"
          f"C = [{jmin:.4f}, {jmax:.4f}], λmax = [{smin:.4f}, {smax:.4f}]",
    center=(0.5, 0.0, 0.0), radius=0.65, elev=0, azim=-90,
    save_path=str(output_dir / f"{family_name}_global_3d_view.png"),
)

# =============================================================================
# 3. Jacobi-Period-Stability
# =============================================================================
plotter.plot_jacobi_period_stability(
    jacobi_values, family_result.periods, stability_values,
    title=f"DRO Family: Jacobi Constant vs Period and Stability\n(n = {n_orbits} orbits)",
    save_path=str(output_dir / f"{family_name}_jacobi_period_stability.png"),
)

# =============================================================================
# 4. Zoomed 2D view (near Moon)
# =============================================================================
zoom_center_x, zoom_range = 0.99, 0.40
plotter.plot_family_2d(
    family_result, jacobi_values,
    title=f"DRO Family (Zoomed View near Moon)\n"
          f"X: [{zoom_center_x - zoom_range:.2f}, {zoom_center_x + zoom_range:.2f}], Y: [±{zoom_range:.2f}]",
    xlim=(zoom_center_x - zoom_range, zoom_center_x + zoom_range),
    ylim=(-zoom_range, zoom_range),
    save_path=str(output_dir / f"{family_name}_local_2d_view.png"),
)

# =============================================================================
# 5. Zoomed 3D view
# =============================================================================
plotter.plot_family_3d(
    family_result, jacobi_values,
    title=f"DRO Family (3D Zoomed View near Moon)\n"
          f"X: [{zoom_center_x - zoom_range:.2f}, {zoom_center_x + zoom_range:.2f}], "
          f"Y/Z: [±{zoom_range:.2f}], {n_orbits} orbits",
    center=(zoom_center_x, 0.0, 0.0), radius=zoom_range, elev=0, azim=-90,
    save_path=str(output_dir / f"{family_name}_local_3d_view.png"),
)

# =============================================================================
# 6. Overview (4 subplots)
# =============================================================================
plotter.plot_family_overview(
    family_result, jacobi_values, family_result.periods, stability_values,
    suptitle=f"DRO Family Overview - Earth-Moon CR3BP (n = {n_orbits})",
    center_3d=(0.5, 0.0, 0.0), radius_3d=0.65,
    zoom_xlim=(zoom_center_x - zoom_range, zoom_center_x + zoom_range),
    zoom_ylim=(-zoom_range, zoom_range),
    elev=0, azim=-90,
    save_path=str(output_dir / f"{family_name}_dro_family_overview.png"),
)

print("\n所有图表已保存到 output/dro/ 目录:")
print(f"  - {family_name}_global_2d_view.png      : 全局2D视图")
print(f"  - {family_name}_global_3d_view.png      : 全局3D视图")
print(f"  - {family_name}_jacobi_period_stability.png : Jacobi常数-周期-稳定性图")
print(f"  - {family_name}_local_2d_view.png       : 局部2D放大视图")
print(f"  - {family_name}_local_3d_view.png       : 局部3D放大视图")
print(f"  - {family_name}_dro_family_overview.png  : 综合概览图")
