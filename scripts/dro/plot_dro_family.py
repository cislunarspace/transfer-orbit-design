from pathlib import Path
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import e2m2e
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization.plotting import OrbitVisualizer, compute_stability_for_family

project_root = Path(__file__).resolve().parent.parent.parent
from scripts.utils.common import MU

# =============================================================================
# 加载轨道数据
# =============================================================================
family_name = "dro_family_0.141886-0.9-0.005_3857117507"
output_dir = project_root / "output" / "dro"
family_path = output_dir / f"{family_name}.json"
system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
family_result = OrbitFamily.load_from_file(filename=family_path, system=system)

n_orbits = len(family_result)
print(f"加载了 {n_orbits} 条DRO轨道")

# =============================================================================
# 计算Jacobi常数和稳定性指数
# =============================================================================
print("正在计算Jacobi常数...")
jacobi_values = family_result.get_jacobi_constants().tolist()
print(f"Jacobi常数范围: {min(jacobi_values):.6f} ~ {max(jacobi_values):.6f}")
print("正在计算稳定性指数...")
stability_values = compute_stability_for_family(family_result, family_result.system)
print(f"稳定性指数范围: {min(stability_values):.6f} ~ {max(stability_values):.6f}")

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


# =============================================================================
# 1. 全局2D视图（XY平面）
# =============================================================================
fig_global_2d, ax_global_2d = plt.subplots(figsize=(12, 10))

# 绘制种子轨道（第一条）
seed_orbit = family_result[0]
seed_jacobi = jacobi_values[0]
seed_stability = stability_values[0]
label = f"Seed DRO (C={seed_jacobi:.4f}, λmax={seed_stability:.4f})"
orbit_plotter.plot_2d_projection(
    seed_orbit, plane="xy", color="red", label=label, ax=ax_global_2d
)

# 绘制其他轨道（从第二条开始）
for idx in range(1, n_orbits):
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
    f"DRO Family in Earth-Moon CR3BP (XY Plane) - {n_orbits} orbits\n"
    f"C = [{jacobi_min:.4f}, {jacobi_max:.4f}], λmax = [{min(stability_values):.4f}, {max(stability_values):.4f}]",
    fontsize=12,
)
ax_global_2d.legend(loc="upper right", fontsize=10, markerscale=1.0, framealpha=0.9)
ax_global_2d.set_aspect("equal")

plt.tight_layout()
plt.savefig(
    output_dir / f"{family_name}_global_2d_view.png", dpi=300, bbox_inches="tight"
)
plt.show()


# =============================================================================
# 2. 全局3D视图
# =============================================================================
fig_global_3d = plt.figure(figsize=(14, 10))
ax_global_3d = fig_global_3d.add_subplot(111, projection="3d")

# 全局3D视图参数
global_center_x = 0.5  # 地球和月球的中点
global_center_y = 0.0
global_center_z = 0.0
global_radius = 0.65

# 绘制种子轨道
label_3d = f"Seed DRO (C={seed_jacobi:.4f})"
orbit_plotter.plot_3d_orbit(
    seed_orbit, color="red", label=label_3d, ax=ax_global_3d, show_start=True
)

# 绘制其他轨道
for idx in range(1, n_orbits):
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
    f"DRO Family in Earth-Moon CR3BP (3D View) - {n_orbits} orbits\n"
    f"C = [{jacobi_min:.4f}, {jacobi_max:.4f}], λmax = [{min(stability_values):.4f}, {max(stability_values):.4f}]",
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

# 设置视角：地球在左侧、月球在右侧
ax_global_3d.view_init(elev=0, azim=-90)

plt.tight_layout()
plt.savefig(
    output_dir / f"{family_name}_global_3d_view.png", dpi=300, bbox_inches="tight"
)
plt.show()


# =============================================================================
# 3. Jacobi常数-周期-稳定性图（双纵轴）
# =============================================================================
fig_jacobi, ax1 = plt.subplots(figsize=(12, 7))

# 左纵轴：周期
color_period = "tab:blue"
ax1.set_xlabel("Jacobi Constant", fontsize=12)
ax1.set_ylabel("Period (nondimensional)", color=color_period, fontsize=12)
(line_period,) = ax1.plot(
    jacobi_values,
    family_result.periods,
    "o-",
    color=color_period,
    markersize=5,
    label="Period",
)
ax1.tick_params(axis="y", labelcolor=color_period)

# 右纵轴：稳定性指数
ax2 = ax1.twinx()
color_stability = "tab:red"
ax2.set_ylabel("Stability Index (λmax)", color=color_stability, fontsize=12)
(line_stability,) = ax2.plot(
    jacobi_values,
    stability_values,
    "s-",
    color=color_stability,
    markersize=5,
    label="Stability Index (λmax)",
)
ax2.tick_params(axis="y", labelcolor=color_stability)

# 设置标题
ax1.set_title(
    f"DRO Family: Jacobi Constant vs Period and Stability\n(n = {n_orbits} orbits)",
    fontsize=13,
)

# 添加图例
lines = [line_period, line_stability]
labels = [l.get_label() for l in lines]
labels_str = [str(l.get_label()) for l in lines]
ax1.legend(lines, labels_str, loc="upper right", fontsize=10)

# 网格
ax1.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(
    output_dir / f"{family_name}_jacobi_period_stability.png",
    dpi=300,
    bbox_inches="tight",
)
plt.show()


# =============================================================================
# 4. 局部2D放大视图
# =============================================================================
fig_zoom_2d, ax_zoom_2d = plt.subplots(figsize=(12, 10))

# 局部放大区域参数
zoom_center_x = 0.99
zoom_center_y = 0.0
zoom_range = 0.40

# 绘制种子轨道
label_zoom_seed = f"Seed DRO (C={seed_jacobi:.4f})"
orbit_plotter.plot_2d_projection(
    seed_orbit, plane="xy", color="red", label=label_zoom_seed, ax=ax_zoom_2d
)

# 绘制其他轨道
for idx in range(1, n_orbits):
    orbit = family_result[idx]
    norm_jacobi = (jacobi_values[idx] - jacobi_min) / jacobi_range
    color = cmap(norm_jacobi)
    orbit_plotter.plot_2d_projection(
        orbit, plane="xy", color=color, show_start=False, ax=ax_zoom_2d
    )

# 添加主次天体和平动点
orbit_plotter.plot_primary_bodies(ax=ax_zoom_2d)
orbit_plotter.plot_libration_points(ax=ax_zoom_2d)

# 添加颜色条
sm_zoom = plt.cm.ScalarMappable(
    cmap=cmap, norm=Normalize(vmin=jacobi_min, vmax=jacobi_max)
)
sm_zoom.set_array([])
cbar_zoom = plt.colorbar(sm_zoom, ax=ax_zoom_2d, shrink=0.8)
cbar_zoom.set_label("Jacobi Constant", fontsize=12)

# 设置坐标轴范围
ax_zoom_2d.set_xlim(zoom_center_x - zoom_range, zoom_center_x + zoom_range)
ax_zoom_2d.set_ylim(zoom_center_y - zoom_range, zoom_center_y + zoom_range)

# 设置标签和标题
ax_zoom_2d.set_xlabel("X (nondimensional)", fontsize=12)
ax_zoom_2d.set_ylabel("Y (nondimensional)", fontsize=12)
ax_zoom_2d.set_title(
    f"DRO Family (Zoomed View near Moon)\n"
    f"X: [{zoom_center_x - zoom_range:.2f}, {zoom_center_x + zoom_range:.2f}], Y: [±{zoom_range:.2f}]",
    fontsize=12,
)
ax_zoom_2d.legend(loc="upper right", fontsize=10, markerscale=1.0, framealpha=0.9)
ax_zoom_2d.set_aspect("equal")

plt.tight_layout()
plt.savefig(
    output_dir / f"{family_name}_local_2d_view.png", dpi=300, bbox_inches="tight"
)
plt.show()


# =============================================================================
# 5. 局部3D放大视图
# =============================================================================
seed_label_3d = f"Seed DRO (C={seed_jacobi:.4f})"
ax_zoom_3d = orbit_plotter.plot_3d_orbit_family(
    family_result,
    jacobi_values=jacobi_values,
    center=(zoom_center_x, zoom_center_y, 0.0),
    radius=zoom_range,
    show_colorbar=True,
    show_legend=True,
    seed_label=seed_label_3d,
)

# 设置视角：地球在左侧、月球在右侧
ax_zoom_3d.view_init(elev=0, azim=-90)

plt.tight_layout()
plt.savefig(
    output_dir / f"{family_name}_local_3d_view.png", dpi=300, bbox_inches="tight"
)
plt.show()


# =============================================================================
# 6. 综合概览图（四子图）
# =============================================================================
fig_overview = plt.figure(figsize=(18, 14))

# 子图1：全局2D视图
ax1 = fig_overview.add_subplot(221)
orbit_plotter.plot_2d_projection(
    seed_orbit, plane="xy", color="red", label=f"Seed (C={seed_jacobi:.4f})", ax=ax1
)
for idx in range(1, n_orbits):
    orbit = family_result[idx]
    norm_jacobi = (jacobi_values[idx] - jacobi_min) / jacobi_range
    color = cmap(norm_jacobi)
    orbit_plotter.plot_2d_projection(
        orbit, plane="xy", color=color, show_start=False, ax=ax1
    )
orbit_plotter.plot_primary_bodies(ax=ax1)
orbit_plotter.plot_libration_points(ax=ax1)
sm_ov = plt.cm.ScalarMappable(
    cmap=cmap, norm=Normalize(vmin=jacobi_min, vmax=jacobi_max)
)
sm_ov.set_array([])
cbar_ov = plt.colorbar(sm_ov, ax=ax1, shrink=0.8)
cbar_ov.set_label("Jacobi Constant", fontsize=10)
ax1.set_title(f"Global XY View ({n_orbits} orbits)", fontsize=11)
ax1.set_xlabel("X", fontsize=10)
ax1.set_ylabel("Y", fontsize=10)
ax1.legend(loc="upper right", fontsize=8)
ax1.set_aspect("equal")

# 子图2：局部2D视图
ax2 = fig_overview.add_subplot(222)
orbit_plotter.plot_2d_projection(
    seed_orbit, plane="xy", color="red", label=f"Seed", ax=ax2
)
for idx in range(1, n_orbits):
    orbit = family_result[idx]
    norm_jacobi = (jacobi_values[idx] - jacobi_min) / jacobi_range
    color = cmap(norm_jacobi)
    orbit_plotter.plot_2d_projection(
        orbit, plane="xy", color=color, show_start=False, ax=ax2
    )
orbit_plotter.plot_primary_bodies(ax=ax2)
orbit_plotter.plot_libration_points(ax=ax2)
ax2.set_xlim(zoom_center_x - zoom_range, zoom_center_x + zoom_range)
ax2.set_ylim(zoom_center_y - zoom_range, zoom_center_y + zoom_range)
ax2.set_title("Zoomed XY View", fontsize=11)
ax2.set_xlabel("X", fontsize=10)
ax2.set_ylabel("Y", fontsize=10)
ax2.legend(loc="upper right", fontsize=8)
ax2.set_aspect("equal")

# 子图3：Jacobi-周期-稳定性
ax3 = fig_overview.add_subplot(223)
ax3.set_xlabel("Jacobi Constant", fontsize=10)
ax3.set_ylabel("Period", color="tab:blue", fontsize=10)
(line_p,) = ax3.plot(
    jacobi_values, family_result.periods, "o-", color="tab:blue", markersize=4
)
ax3.tick_params(axis="y", labelcolor="tab:blue")
ax3_right = ax3.twinx()
ax3_right.set_ylabel("λmax", color="tab:red", fontsize=10)
(line_s,) = ax3_right.plot(
    jacobi_values, stability_values, "s-", color="tab:red", markersize=4
)
ax3_right.tick_params(axis="y", labelcolor="tab:red")
ax3.set_title("Jacobi vs Period & Stability", fontsize=11)
ax3.legend([line_p, line_s], ["Period", "λmax"], loc="upper right", fontsize=8)
ax3.grid(True, alpha=0.3)

# 子图4：3D视图
ax4 = fig_overview.add_subplot(224, projection="3d")
orbit_plotter.plot_3d_orbit(
    seed_orbit, color="red", label="Seed", ax=ax4, show_start=True
)
for idx in range(1, n_orbits):
    orbit = family_result[idx]
    norm_jacobi = (jacobi_values[idx] - jacobi_min) / jacobi_range
    color = cmap(norm_jacobi)
    orbit_plotter.plot_3d_orbit(orbit, color=color, ax=ax4, show_start=False)
orbit_plotter.plot_primary_bodies(ax=ax4, is_3d=True)
ax4.set_xlim(global_center_x - global_radius, global_center_x + global_radius)
ax4.set_ylim(global_center_y - global_radius, global_center_y + global_radius)
ax4.set_zlim(global_center_z - global_radius, global_center_z + global_radius)
ax4.set_title("3D View", fontsize=11)
ax4.set_xlabel("X", fontsize=10)
ax4.set_ylabel("Y", fontsize=10)
ax4.set_zlabel("Z", fontsize=10)
ax4.view_init(elev=0, azim=-90)

fig_overview.suptitle(
    f"DRO Family Overview - Earth-Moon CR3BP (n = {n_orbits})",
    fontsize=14,
    fontweight="bold",
)
plt.tight_layout()
plt.savefig(
    output_dir / f"{family_name}_dro_family_overview.png", dpi=300, bbox_inches="tight"
)
plt.show()


print("\n所有图表已保存到 output/dro/ 目录:")
print(f"  - {family_name}_global_2d_view.png      : 全局2D视图")
print(f"  - {family_name}_global_3d_view.png      : 全局3D视图")
print(f"  - {family_name}_jacobi_period_stability.png : Jacobi常数-周期-稳定性图")
print(f"  - {family_name}_local_2d_view.png       : 局部2D放大视图")
print(f"  - {family_name}_local_3d_view.png       : 局部3D放大视图")
print(f"  - {family_name}_dro_family_overview.png  : 综合概览图")
