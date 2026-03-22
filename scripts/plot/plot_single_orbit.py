"""
绘制单条轨道

从 JSON 文件加载单条 Orbit 对象并绘制 2D 和 3D 视图。

与 OrbitFamily 的区别：
- Orbit 对象直接包含 states, times, period 等属性
- 加载使用 Orbit.load_from_file() 而非 OrbitFamily.load_from_file()
"""

import sys
from pathlib import Path

# ==== 统一项目根目录定位与 utils 导入 ====
project_root = (
    Path(__file__).resolve().parent.parent.parent
)  # .../transfer-orbit-design
scripts_dir = project_root / "scripts"
utils_dir = scripts_dir / "utils"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from scripts.utils.params import MU

import matplotlib
import matplotlib.pyplot as plt
import e2m2e
from e2m2e.core import Orbit, CR3BP_System
from e2m2e.visualization.plotting import OrbitVisualizer

# =============================================================================
# 加载单条轨道数据
# =============================================================================
# 使用 Orbit.load_from_file() 加载单条轨道
orbit_filename = "ro_31_3857030320.json"  # 3:1 RO 轨道
output_dir = project_root / "output" / "ro"
orbit_path = output_dir / orbit_filename

system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
orbit = Orbit.load_from_file(filename=orbit_path, system=system)

print(f"加载轨道: {orbit_filename}")
print(f"  状态数: {len(orbit.states)}")
print(f"  周期: {orbit.period:.6f} TU ({orbit.period * 4.348:.2f} days)")
if orbit.jacobi_constants is not None:
    print(f"  Jacobi常数: {orbit.jacobi_constants[0]:.6f}")

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

# =============================================================================
# 1. XY 平面 2D 视图
# =============================================================================
fig_2d, ax_2d = plt.subplots(figsize=(10, 8))

orbit_plotter.plot_2d_projection(
    orbit, plane="xy", color="blue", label="3:1 DRO", ax=ax_2d
)
orbit_plotter.plot_primary_bodies(ax=ax_2d)
orbit_plotter.plot_libration_points(ax=ax_2d)

ax_2d.set_xlabel("X (nondimensional)", fontsize=12)
ax_2d.set_ylabel("Y (nondimensional)", fontsize=12)
ax_2d.set_title(
    f"Single 3:1 DRO Orbit (XY Plane)\n"
    f"Period = {orbit.period:.4f} TU, Jacobi = {orbit.jacobi_constants[0]:.4f}",
    fontsize=12,
)
ax_2d.legend(loc="upper right", fontsize=10)
ax_2d.set_aspect("equal")

plt.tight_layout()
plt.savefig(output_dir / f"{orbit_filename.replace('.json', '_2d.png')}", dpi=300, bbox_inches="tight")
plt.show()

# =============================================================================
# 2. 3D 视图
# =============================================================================
fig_3d = plt.figure(figsize=(12, 10))
ax_3d = fig_3d.add_subplot(111, projection="3d")

# 计算轨道范围以设置视角
x_range = orbit.states[:, 0].max() - orbit.states[:, 0].min()
y_range = orbit.states[:, 1].max() - orbit.states[:, 1].min()
z_range = orbit.states[:, 2].max() - orbit.states[:, 2].min()
center_x = orbit.states[:, 0].mean()
center_y = orbit.states[:, 1].mean()
center_z = orbit.states[:, 2].mean()
max_range = max(x_range, y_range, z_range) / 2 * 1.2

orbit_plotter.plot_3d_orbit(
    orbit, color="blue", label="3:1 DRO", ax=ax_3d, show_start=True
)
orbit_plotter.plot_primary_bodies(ax=ax_3d, is_3d=True)
orbit_plotter.plot_libration_points(ax=ax_3d, show_labels=True, is_3d=True)

# 设置坐标轴范围
ax_3d.set_xlim(center_x - max_range, center_x + max_range)
ax_3d.set_ylim(center_y - max_range, center_y + max_range)
ax_3d.set_zlim(center_z - max_range, center_z + max_range)

ax_3d.set_xlabel("X (nondimensional)", fontsize=12)
ax_3d.set_ylabel("Y (nondimensional)", fontsize=12)
ax_3d.set_zlabel("Z (nondimensional)", fontsize=12)
ax_3d.set_title(
    f"Single 3:1 DRO Orbit (3D View)\n"
    f"Period = {orbit.period:.4f} TU, Jacobi = {orbit.jacobi_constants[0]:.4f}",
    fontsize=12,
)
ax_3d.legend(loc="upper right", fontsize=10)

# 设置视角：侧视
ax_3d.view_init(elev=20, azim=-60)

plt.tight_layout()
plt.savefig(output_dir / f"{orbit_filename.replace('.json', '_3d.png')}", dpi=300, bbox_inches="tight")
plt.show()

# =============================================================================
# 3. 多平面 2D 视图 (XY, XZ, YZ)
# =============================================================================
fig_multi, axes = plt.subplots(1, 3, figsize=(18, 6))

for ax, plane, title in zip(axes, ["xy", "xz", "yz"], ["XY Plane", "XZ Plane", "YZ Plane"]):
    orbit_plotter.plot_2d_projection(
        orbit, plane=plane, color="blue", label="3:1 DRO", ax=ax
    )
    orbit_plotter.plot_primary_bodies(ax=ax)
    orbit_plotter.plot_libration_points(ax=ax)
    ax.set_xlabel("X (nondimensional)", fontsize=10)
    ax.set_ylabel("Y (nondimensional)" if plane == "xy" else "Z (nondimensional)", fontsize=10)
    ax.set_title(title, fontsize=12)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_aspect("equal")

plt.tight_layout()
plt.savefig(output_dir / f"{orbit_filename.replace('.json', '_multi_2d.png')}", dpi=300, bbox_inches="tight")
plt.show()

print(f"\n轨道图已保存至 {output_dir}")
