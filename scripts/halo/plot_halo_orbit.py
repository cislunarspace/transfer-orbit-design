"""
可视化 Halo 轨道

本脚本实现：
1. 加载Halo轨道数据
2. 计算Jacobi常数和稳定性指数
3. 创建2D和3D可视化
4. 创建周期-稳定性参数图
"""

from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent.parent

import numpy as np
import matplotlib.pyplot as plt
import e2m2e
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization import PlotConfig, FamilyPlotter, compute_stability_for_family

from scripts.utils.common import MU

# =============================================================================
# 加载轨道数据
# =============================================================================
family_name = "halo_L1_N_family_3857278981"
output_dir = project_root / "output" / "halo"
family_path = output_dir / f"{family_name}.json"

system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

try:
    family_result = OrbitFamily.load_from_file(filename=family_path, system=system)
    n_orbits = len(family_result)
    print(f"加载了 {n_orbits} 条 Halo 轨道")
except FileNotFoundError:
    print(f"[error] 文件不存在: {family_path}")
    print("请先生成Halo轨道数据，运行: python scripts/generate/generate_halo_family.py")
    sys.exit(1)

# =============================================================================
# 绘制范围控制变量
# =============================================================================
PLOT_START_IDX = -1
PLOT_END_IDX = -1

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

subset_family = OrbitFamily(system=system)
for i in range(plot_start, plot_end + 1):
    subset_family.add_orbit(family_result[i])

# =============================================================================
# 计算Jacobi常数和稳定性指数
# =============================================================================
print("正在计算Jacobi常数...")
jacobi_values = family_result.get_jacobi_constants().tolist()
jacobi_subset = [jacobi_values[i] for i in range(plot_start, plot_end + 1)]
print(f"Jacobi常数范围: {min(jacobi_subset):.6f} ~ {max(jacobi_subset):.6f}")

print("正在计算稳定性指数...")
stability_values = compute_stability_for_family(family_result, family_result.system)
stability_subset = [stability_values[i] for i in range(plot_start, plot_end + 1)]
print(f"稳定性指数范围: {min(stability_subset):.6f} ~ {max(stability_subset):.6f}")

sort_idx = np.argsort(jacobi_subset)
jacobi_sorted = np.array(jacobi_subset)[sort_idx].tolist()
periods_sorted = np.array(subset_family.periods)[sort_idx].tolist()
stability_sorted = np.array(stability_subset)[sort_idx].tolist()

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

jmin, jmax = min(jacobi_subset), max(jacobi_subset)
smin, smax = min(stability_subset), max(stability_subset)
seed_orbit = family_result[0]
seed_jacobi = jacobi_values[0]
seed_stability = stability_values[0]

# =============================================================================
# 1. 全局2D视图（XZ平面 - Halo轨道的特征平面）
# =============================================================================
fig_2d, ax_2d = plotter.plot_family_2d(
    subset_family, jacobi_subset,
    title=f"Halo Orbit Family in Earth-Moon CR3BP (XZ Plane) - {n_orbits} orbits\n"
          f"C = [{jmin:.4f}, {jmax:.4f}], λmax = [{smin:.4f}, {smax:.4f}]",
    plane="xz",
    show_bodies=True, show_libration=True, show_colorbar=True,
    show=False,
)
plotter.plot_2d_projection(
    seed_orbit, plane="xz", color="red",
    label=f"Seed Halo (C={seed_jacobi:.4f}, λmax={seed_stability:.4f})",
    ax=ax_2d,
)
plt.tight_layout()
plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")
plt.show()

# =============================================================================
# 2. 全局3D视图
# =============================================================================
fig_3d, ax_3d = plotter.plot_family_3d(
    subset_family, jacobi_subset,
    title=f"Halo Orbit Family in Earth-Moon CR3BP (3D View) - {n_orbits} orbits\n"
          f"C = [{jmin:.4f}, {jmax:.4f}], λmax = [{smin:.4f}, {smax:.4f}]",
    center=(0.9, 0, 0), radius=0.4, elev=20, azim=-60,
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

# =============================================================================
# 3. Jacobi常数-周期-稳定性图（双纵轴）
# =============================================================================
plotter.plot_jacobi_period_stability(
    jacobi_sorted, periods_sorted, stability_sorted,
    title=f"Halo Orbit Family - Period and Stability\n(n = {n_orbits} orbits)",
    save_path=output_dir / f"{family_name}_period_stability.png",
    show=True,
)

# =============================================================================
# 4. 综合概览图（四子图）
# =============================================================================
plotter.plot_family_overview(
    subset_family, jacobi_subset, subset_family.periods, stability_subset,
    suptitle=f"Halo Orbit Family Overview - Earth-Moon CR3BP (n = {n_orbits})",
    plane="xz", center_3d=(0.9, 0, 0), radius_3d=0.4,
    elev=20, azim=-60,
    save_path=output_dir / f"{family_name}_overview.png",
    show=True,
)

print(f"\n所有图表已保存到 {output_dir} 目录:")
print(f"  - {family_name}_2d_view.png           : 全局2D视图 (XZ平面)")
print(f"  - {family_name}_3d_view.png           : 全局3D视图")
print(f"  - {family_name}_period_stability.png  : Jacobi常数-周期-稳定性图")
print(f"  - {family_name}_overview.png           : 综合概览图")
