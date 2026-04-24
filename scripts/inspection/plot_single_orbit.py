"""
绘制单条轨道

从 JSON 文件加载单条 Orbit 对象并绘制 2D 和 3D 视图。

与 OrbitFamily 的区别：
- Orbit 对象直接包含 states, times, period 等属性
- 加载使用 Orbit.load_from_file() 而非 OrbitFamily.load_from_file()
"""

import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent
from scripts.utils.common import MU, TU

import matplotlib
import matplotlib.pyplot as plt
import e2m2e
from e2m2e.core import Orbit, CR3BP_System
from e2m2e.visualization.base import OrbitVisualizer


def parse_args():
    parser = argparse.ArgumentParser(description="绘制单条轨道")
    parser.add_argument(
        "--json-file", type=str, default=None, help="轨道 JSON 文件路径"
    )
    return parser.parse_args()


DEFAULT_ORBIT_FILENAME = "ro_31_3857030320.json"


def main():
    args = parse_args()

    output_dir = project_root / "output" / "ro"

    if args.json_file:
        orbit_path = Path(args.json_file)
        orbit_filename = orbit_path.name
    else:
        orbit_filename = DEFAULT_ORBIT_FILENAME
        orbit_path = output_dir / orbit_filename

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    orbit = Orbit.load_from_file(filename=orbit_path, system=system)

    print(f"加载轨道: {orbit_filename}")
    print(f"  状态数: {len(orbit.states)}")
    if orbit.period is None:
        raise ValueError("orbit period is None")
    print(f"  周期: {orbit.period:.6f} TU ({orbit.period * TU:.2f} days)")
    if orbit.jacobi_constants is not None:
        print(f"  Jacobi常数: {orbit.jacobi_constants[0]:.6f}")

    _jacobi_title = (
        f"Jacobi = {orbit.jacobi_constants[0]:.4f}"
        if orbit.jacobi_constants is not None
        else "Jacobi = N/A"
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

    # =============================================================================
    # 1. XY 平面 2D 视图
    # =============================================================================
    fig_2d, ax_2d = plt.subplots(figsize=(10, 8))

    orbit_plotter.plot_2d_projection(
        orbit, plane="xy", color="blue", label="3:1 RO", ax=ax_2d
    )
    orbit_plotter.plot_primary_bodies(ax=ax_2d)
    orbit_plotter.plot_libration_points(ax=ax_2d)

    ax_2d.set_xlabel("X (nondimensional)", fontsize=12)
    ax_2d.set_ylabel("Y (nondimensional)", fontsize=12)
    ax_2d.set_title(
        f"Single Orbit (XY Plane)\nPeriod = {orbit.period:.4f} TU, {_jacobi_title}",
        fontsize=12,
    )
    ax_2d.legend(loc="upper right", fontsize=10)
    ax_2d.set_aspect("equal")

    plt.tight_layout()
    plt.savefig(
        output_dir / f"{orbit_filename.replace('.json', '_2d.png')}",
        dpi=300,
        bbox_inches="tight",
    )
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
        orbit, color="blue", label="3:1 RO", ax=ax_3d, show_start=True
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
        f"Single Orbit (3D View)\nPeriod = {orbit.period:.4f} TU, {_jacobi_title}",
        fontsize=12,
    )
    ax_3d.legend(loc="upper right", fontsize=10)

    # 设置视角：侧视
    ax_3d.view_init(elev=20, azim=-60)

    plt.tight_layout()
    plt.savefig(
        output_dir / f"{orbit_filename.replace('.json', '_3d.png')}",
        dpi=300,
        bbox_inches="tight",
    )
    plt.show()

    # =============================================================================
    # 3. 多平面 2D 视图 (XY, XZ, YZ)
    # =============================================================================
    fig_multi, axes = plt.subplots(1, 3, figsize=(18, 6))

    for ax, plane, title in zip(
        axes, ["xy", "xz", "yz"], ["XY Plane", "XZ Plane", "YZ Plane"]
    ):
        orbit_plotter.plot_2d_projection(
            orbit, plane=plane, color="blue", label="3:1 RO", ax=ax
        )
        orbit_plotter.plot_primary_bodies(ax=ax)
        orbit_plotter.plot_libration_points(ax=ax)
        ax.set_xlabel("X (nondimensional)", fontsize=10)
        ax.set_ylabel(
            "Y (nondimensional)" if plane == "xy" else "Z (nondimensional)", fontsize=10
        )
        ax.set_title(title, fontsize=12)
        ax.legend(loc="upper right", fontsize=8)
        ax.set_aspect("equal")

    plt.tight_layout()
    plt.savefig(
        output_dir / f"{orbit_filename.replace('.json', '_multi_2d.png')}",
        dpi=300,
        bbox_inches="tight",
    )
    plt.show()

    print(f"\n轨道图已保存至 {output_dir}")


if __name__ == "__main__":
    main()
