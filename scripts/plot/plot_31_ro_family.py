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

import sys
from pathlib import Path

# ==== 统一项目根目录定位与 utils 导入 ====
project_root = (
    Path(__file__).resolve().parent.parent.parent
)  # .../transfer-orbit-design
scripts_dir = project_root / "scripts"
utils_dir = scripts_dir / "utils"
if str(utils_dir) not in sys.path:
    sys.path.insert(0, str(utils_dir))

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import e2m2e
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization.plotting import OrbitVisualizer, compute_stability_for_family
from scripts.utils.common import MU

# =============================================================================
# 加载轨道数据
# =============================================================================
family_name = "ro_31_family_0.8905--0.8304999999999999-0.001_3856910376"
output_dir = project_root / "output" / "ro"
family_path = output_dir / f"{family_name}.json"
system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
family_result = OrbitFamily.load_from_file(filename=family_path, system=system)

n_orbits = len(family_result)
print(f"加载了 {n_orbits} 条 3:1 RO轨道")

# =============================================================================
# 绘制范围控制变量
# =============================================================================
# PLOT_START_IDX: 起始轨道索引 (0-based)，-1 表示从第一条轨道开始
# PLOT_END_IDX: 结束轨道索引 (0-based, inclusive)，-1 表示到最后一条轨道
# 规则：
#   - 如果 PLOT_START_IDX == -1 且 PLOT_END_IDX == -1：绘制所有轨道
#   - 如果 PLOT_START_IDX == -1：从第一条绘制到 PLOT_END_IDX
#   - 如果 PLOT_END_IDX == -1：从 PLOT_START_IDX 绘制到最后一条
#   - 其他情况：绘制 [PLOT_START_IDX, PLOT_END_IDX] 范围内的轨道
PLOT_START_IDX = -1  # 修改此值控制起始轨道，例如 0, 10, -1
PLOT_END_IDX = 42  # 修改此值控制结束轨道，例如 50, 100, -1

# 计算实际绘制范围
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
# 计算Jacobi常数和稳定性指数（仅针对绘制范围内的轨道）
# =============================================================================
print("正在计算Jacobi常数...")

# 只获取绘制范围内的Jacobi常数
jacobi_values_subset = [
    family_result.get_jacobi_constants()[i] for i in range(plot_start, plot_end + 1)
]
jacobi_values = family_result.get_jacobi_constants().tolist()
print(f"Jacobi常数范围: {min(jacobi_values):.6f} ~ {max(jacobi_values):.6f}")

# 只对绘制范围内的轨道计算稳定性指数
print(f"正在计算第 {plot_start} 至 第 {plot_end} 条轨道的稳定性指数...")
# 创建临时子轨道族用于计算稳定性
from e2m2e.core import OrbitFamily

subset_family = OrbitFamily(family_result.system)
for i in range(plot_start, plot_end + 1):
    subset_family.add_orbit(family_result[i])
stability_values_subset = compute_stability_for_family(
    subset_family, family_result.system
)
# 补齐到完整列表（未计算的轨道填充None）
stability_values = [None] * n_orbits
for i, val in enumerate(stability_values_subset):
    stability_values[plot_start + i] = val
print(
    f"稳定性指数范围: {min(stability_values_subset):.6f} ~ {max(stability_values_subset):.6f}"
)

# =============================================================================
# 创建可视化器
# =============================================================================
orbit_plotter = OrbitVisualizer(system=system)

# 自定义天体颜色
orbit_plotter.primary_body_color = "blue"
orbit_plotter.secondary_body_color = "silver"

# 统一拉格朗日点样式
orbit_plotter.libration_point_colors = ["gray"] * 5
orbit_plotter.libration_point_markers = ["^"] * 5
orbit_plotter.libration_point_sizes = [60] * 5

# 颜色映射
cmap = matplotlib.colormaps["coolwarm"]
jacobi_min = min(jacobi_values)
jacobi_max = max(jacobi_values)
jacobi_range = jacobi_max - jacobi_min if jacobi_max != jacobi_min else 1.0

# 3:1 RO 目标周期
target_period = 2 * np.pi  # 2π ≈ 6.283 TU

# =============================================================================
# 1. 全局2D视图（XY平面）
# =============================================================================
fig_global_2d, ax_global_2d = plt.subplots(figsize=(12, 10))

# 绘制种子轨道（第一条）
seed_orbit = family_result[0]
seed_jacobi = jacobi_values[0]
seed_stability = (
    stability_values[0]
    if stability_values[0] is not None
    else stability_values_subset[0]
)
label = f"Seed 3:1 RO (C={seed_jacobi:.4f}, λmax={seed_stability:.4f})"
orbit_plotter.plot_2d_projection(
    seed_orbit, plane="xy", color="red", label=label, ax=ax_global_2d
)

# 绘制其他轨道（使用绘制范围控制）
# 起始索引为0时跳过（种子轨道已绘制），否则从plot_start开始
orbit_loop_start = 1 if plot_start == 0 else plot_start
for idx in range(orbit_loop_start, plot_end + 1):
    orbit = family_result[idx]
    norm_jacobi = (jacobi_values[idx] - jacobi_min) / jacobi_range
    color = cmap(norm_jacobi)
    orbit_plotter.plot_2d_projection(
        orbit, plane="xy", color=color, show_start=False, ax=ax_global_2d
    )

# 添加主次天体
orbit_plotter.plot_primary_bodies(ax=ax_global_2d)
orbit_plotter.plot_libration_points(ax=ax_global_2d)

# 添加颜色条
sm = plt.cm.ScalarMappable(cmap=cmap, norm=Normalize(vmin=jacobi_min, vmax=jacobi_max))
sm.set_array([])
cbar = plt.colorbar(sm, ax=ax_global_2d, shrink=0.8)
cbar.set_label("Jacobi Constant", fontsize=12)

# 设置标签和标题
ax_global_2d.set_xlabel("X (nondimensional)", fontsize=12)
ax_global_2d.set_ylabel("Y (nondimensional)", fontsize=12)
ax_global_2d.set_title(
    f"3:1 Resonant Orbit Family in Earth-Moon CR3BP (XY Plane) - {n_orbits} orbits\n"
    f"C = [{jacobi_min:.4f}, {jacobi_max:.4f}], λmax = [{min(stability_values_subset):.4f}, {max(stability_values_subset):.4f}]",
    fontsize=12,
)
ax_global_2d.legend(loc="upper right", fontsize=10, markerscale=1.0, framealpha=0.9)
ax_global_2d.set_aspect("equal")

plt.tight_layout()
plt.savefig(output_dir / f"{family_name}_2d_view.png", dpi=300, bbox_inches="tight")
plt.show()

# =============================================================================
# 2. 全局3D视图
# =============================================================================
fig_global_3d = plt.figure(figsize=(14, 10))
ax_global_3d = fig_global_3d.add_subplot(111, projection="3d")

# 全局3D视图参数
global_center_x = -0.85  # 3:1 RO 中心位置
global_center_y = 0.0
global_center_z = 0.0
global_radius = 0.5

# 绘制种子轨道
label_3d = f"Seed 3:1 RO (C={seed_jacobi:.4f})"
orbit_plotter.plot_3d_orbit(
    seed_orbit, color="red", label=label_3d, ax=ax_global_3d, show_start=True
)

# 绘制其他轨道（使用绘制范围控制）
orbit_loop_start = 1 if plot_start == 0 else plot_start
for idx in range(orbit_loop_start, plot_end + 1):
    orbit = family_result[idx]
    norm_jacobi = (jacobi_values[idx] - jacobi_min) / jacobi_range
    color = cmap(norm_jacobi)
    orbit_plotter.plot_3d_orbit(orbit, color=color, ax=ax_global_3d, show_start=False)

# 添加主次天体和平动点
orbit_plotter.plot_primary_bodies(ax=ax_global_3d, is_3d=True)
orbit_plotter.plot_libration_points(ax=ax_global_3d, show_labels=True, is_3d=True)

# 设置坐标轴范围
ax_global_3d.set_xlim(global_center_x - global_radius, global_center_x + global_radius)
ax_global_3d.set_ylim(global_center_y - global_radius, global_center_y + global_radius)
ax_global_3d.set_zlim(global_center_z - global_radius, global_center_z + global_radius)

# 设置标签
ax_global_3d.set_xlabel("X (nondimensional)", fontsize=12)
ax_global_3d.set_ylabel("Y (nondimensional)", fontsize=12)
ax_global_3d.set_zlabel("Z (nondimensional)", fontsize=12)
ax_global_3d.set_title(
    f"3:1 Resonant Orbit Family in Earth-Moon CR3BP (3D View) - {n_orbits} orbits\n"
    f"C = [{jacobi_min:.4f}, {jacobi_max:.4f}], λmax = [{min(stability_values_subset):.4f}, {max(stability_values_subset):.4f}]",
    fontsize=12,
)

# 添加颜色条
sm_3d = plt.cm.ScalarMappable(
    cmap=cmap, norm=Normalize(vmin=jacobi_min, vmax=jacobi_max)
)
sm_3d.set_array([])
cbar_3d = plt.colorbar(sm_3d, ax=ax_global_3d, shrink=0.6, pad=0.1)
cbar_3d.set_label("Jacobi Constant", fontsize=11)

# 图例
ax_global_3d.legend(loc="upper right", fontsize=10)

# 设置视角
ax_global_3d.view_init(elev=0, azim=-90)

plt.tight_layout()
plt.savefig(output_dir / f"{family_name}_3d_view.png", dpi=300, bbox_inches="tight")
plt.show()

# =============================================================================
# 3. Jacobi常数-周期-稳定性图（双纵轴）
# =============================================================================
fig_jacobi, ax1 = plt.subplots(figsize=(12, 7))

# 按 Jacobi 值排序以避免连线交叉
sort_idx = np.argsort(jacobi_values_subset)
jacobi_sorted = np.array(jacobi_values_subset)[sort_idx]
periods_sorted = np.array(family_result.periods[plot_start : plot_end + 1])[sort_idx]
stability_sorted = np.array(stability_values_subset)[sort_idx]

# 左纵轴：周期
color_period = "tab:blue"
ax1.set_xlabel("Jacobi Constant", fontsize=12)
ax1.set_ylabel("Period (nondimensional)", color=color_period, fontsize=12)
(line_period,) = ax1.plot(
    jacobi_sorted,
    periods_sorted,
    "o-",
    color=color_period,
    markersize=5,
    label="Period",
)
ax1.tick_params(axis="y", labelcolor=color_period)

# 添加目标周期线
ax1.axhline(
    y=target_period,
    color="green",
    linestyle="--",
    alpha=0.7,
    label=f"Target Period ({target_period:.4f})",
)

# 右纵轴：稳定性指数（仅绘制范围内的轨道）
ax2 = ax1.twinx()
color_stability = "tab:red"
ax2.set_ylabel("Stability Index (λmax)", color=color_stability, fontsize=12)
(line_stability,) = ax2.plot(
    jacobi_sorted,
    stability_sorted,
    "s-",
    color=color_stability,
    markersize=5,
    label="Stability Index (λmax)",
)
ax2.tick_params(axis="y", labelcolor=color_stability)

# 设置标题
ax1.set_title(
    f"3:1 Resonant Orbit Family - Period and Stability\n"
    f"Period Target: {target_period:.4f} TU ({target_period * 4.348:.2f} days)",
    fontsize=12,
)

# 合并图例
lines = [line_period, line_stability]
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc="upper right", fontsize=10)

plt.tight_layout()
plt.savefig(
    output_dir / f"{family_name}_period_stability.png", dpi=300, bbox_inches="tight"
)
plt.show()

print(f"\n完成！图像已保存到 output/ro/ 目录")
