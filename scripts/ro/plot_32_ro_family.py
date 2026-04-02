"""
可视化 3:2 共振轨道族

本脚本实现：
1. 加载3:2 RO轨道族数据
2. 计算Jacobi常数和稳定性指数
3. 创建2D和3D可视化
4. 创建周期-稳定性参数图

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

import numpy as np
import matplotlib.pyplot as plt
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization import PlotConfig, FamilyPlotter, compute_stability_for_family
from scripts.utils.common import MU

# =============================================================================
# 加载轨道数据
# =============================================================================
family_name = "ro_32_family_-1.2--0.8-0.005_3857719350"
output_dir = project_root / "output" / "ro"
family_path = output_dir / f"{family_name}.json"
system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
family_result = OrbitFamily.load_from_file(filename=family_path, system=system)

n_orbits = len(family_result)
print(f"加载了 {n_orbits} 条 3:2 RO轨道")

# =============================================================================
# 绘制范围控制变量
# =============================================================================
PLOT_START_IDX = -1
PLOT_END_IDX = 42

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
print(f"将绘制第 {plot_start} 至 第 {plot_end} 条轨道，共 {n_orbits_to_plot} 条")

# =============================================================================
# 计算Jacobi常数和稳定性指数
# =============================================================================
print("正在计算Jacobi常数...")
jacobi_values = family_result.get_jacobi_constants().tolist()
print(f"Jacobi常数范围: {min(jacobi_values):.6f} ~ {max(jacobi_values):.6f}")

print("正在计算稳定性指数...")
stability_values = compute_stability_for_family(family_result, system)
print(f"稳定性指数范围: {min(stability_values):.6f} ~ {max(stability_values):.6f}")

subset_family = OrbitFamily(system)
for i in range(plot_start, plot_end + 1):
    subset_family.add_orbit(family_result[i])
jacobi_values_subset = jacobi_values[plot_start : plot_end + 1]

target_period = 4 * np.pi

# =============================================================================
# 创建绘图器
# =============================================================================
config = PlotConfig(
    title=32, label=28, tick=26, legend=28, colorbar=26, suptitle=36, lp_label=32,
    title_y_offset=-0.12, title_y_offset_3d=-0.08, title_y_offset_dual=-0.18,
    title_y_offset_subplot=-0.15,
)
config.apply_rcparams()
plotter = FamilyPlotter(system, config)

jacobi_min = min(jacobi_values_subset)
jacobi_max = max(jacobi_values_subset)
seed_orbit = family_result[0]
seed_jacobi = jacobi_values[0]
seed_stability = stability_values[0]

# =============================================================================
# 1. 2D视图（XY平面）
# =============================================================================
fig_2d, ax_2d = plotter.plot_family_2d(
    subset_family,
    jacobi_values_subset,
    title=(
        f"3:2 Resonant Orbit Family in Earth-Moon CR3BP (XY Plane) - {n_orbits} orbits\n"
        f"C = [{jacobi_min:.4f}, {jacobi_max:.4f}], "
        f"λmax = [{min(stability_values):.4f}, {max(stability_values):.4f}]"
    ),
    plane="xy",
    show=False,
)
plotter.plot_2d_projection(
    seed_orbit,
    color="red",
    label=f"Seed 3:2 RO (C={seed_jacobi:.4f}, λmax={seed_stability:.4f})",
    ax=ax_2d,
)
plt.tight_layout()
plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")
plt.show()

# =============================================================================
# 2. 3D视图
# =============================================================================
fig_3d, ax_3d = plotter.plot_family_3d(
    subset_family,
    jacobi_values_subset,
    title=(
        f"3:2 Resonant Orbit Family in Earth-Moon CR3BP (3D View) [{plot_start}-{plot_end}]\n"
        f"C = [{jacobi_min:.4f}, {jacobi_max:.4f}], "
        f"λmax = [{min(stability_values):.4f}, {max(stability_values):.4f}]"
    ),
    center=(-0.9, 0, 0),
    radius=0.5,
    elev=0,
    azim=-90,
    show=False,
)
plotter.plot_3d_orbit(
    seed_orbit,
    color="red",
    label=f"Seed 3:2 RO (C={seed_jacobi:.4f})",
    ax=ax_3d,
    show_start=True,
)
plt.tight_layout()
plt.savefig(output_dir / f"{family_name}_3d_view.png", dpi=300, bbox_inches="tight")
plt.show()

# =============================================================================
# 3. Jacobi常数-周期-稳定性图
# =============================================================================
plotter.plot_jacobi_period_stability(
    jacobi_values,
    list(family_result.periods),
    stability_values,
    title=(
        f"3:2 Resonant Orbit Family - Period and Stability\n"
        f"Period Target: {target_period:.4f} TU ({target_period * 4.348:.2f} days)"
    ),
    target_period=target_period,
    save_path=output_dir / f"{family_name}_period_stability.png",
    show=True,
)

print(f"\n完成！图像已保存到 output/ro/ 目录")
