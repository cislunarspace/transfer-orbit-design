"""
可视化共振轨道族

本脚本实现：
1. 加载RO轨道族数据
2. 计算Jacobi常数和稳定性指数
3. 创建2D和3D可视化
4. 创建周期-稳定性参数图

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

import e2m2e
from e2m2e.core import OrbitFamily, CR3BP_System
from e2m2e.visualization.plotting import OrbitVisualizer, compute_stability_for_family

from scripts.utils.common import MU

# =============================================================================
# 轨道族配置
# =============================================================================
FAMILY_CONFIGS = {
    "3:2": {
        "filename": "ro_32_family.json",
        "target_period": 4 * np.pi,  # 4π ≈ 12.566 TU
        "label": "3:2",
    },
    "3:1": {
        "filename": "ro_31_family.json",
        "target_period": 2 * np.pi,  # 2π ≈ 6.283 TU
        "label": "3:1",
    },
}

import numpy as np


def load_family(config_name, system):
    """加载RO轨道族

    参数:
        config_name: str, "3:2" 或 "3:1"
        system: CR3BP_System对象

    返回:
        OrbitFamily对象或None
    """
    config = FAMILY_CONFIGS[config_name]
    family_path = f"output/ro/{config['filename']}"

    print(f"加载 {config['label']} RO轨道族: {family_path}")
    family = OrbitFamily.load_from_file(filename=family_path, system=system)

    if family is not None and len(family) > 0:
        print(f"  成功加载 {len(family)} 条轨道")
        return family
    else:
        print(f"  加载失败")
        return None


def plot_ro_family_2d(family, config_name, system):
    """绘制RO族2D视图

    参数:
        family: OrbitFamily对象
        config_name: str, "3:2" 或 "3:1"
        system: CR3BP_System对象
    """
    config = FAMILY_CONFIGS[config_name]
    label = config["label"]
    n_orbits = len(family)

    # 计算Jacobi常数
    jacobi_values = family.get_jacobi_constants().tolist()
    jacobi_min, jacobi_max = min(jacobi_values), max(jacobi_values)

    # 创建可视化器
    orbit_plotter = OrbitVisualizer(system=system)
    orbit_plotter.primary_body_color = "blue"
    orbit_plotter.secondary_body_color = "silver"
    orbit_plotter.libration_point_colors = ["gray"] * 5
    orbit_plotter.libration_point_markers = ["^"] * 5
    orbit_plotter.libration_point_sizes = [60] * 5

    # 颜色映射
    cmap = matplotlib.colormaps["coolwarm"]
    jacobi_range = jacobi_max - jacobi_min if jacobi_max != jacobi_min else 1.0

    # 创建图形
    fig, ax = plt.subplots(figsize=(12, 10))

    # 绘制所有轨道
    for idx in range(n_orbits):
        orbit = family[idx]
        norm_jacobi = (jacobi_values[idx] - jacobi_min) / jacobi_range
        color = cmap(norm_jacobi)
        orbit_plotter.plot_2d_projection(
            orbit, plane="xy", color=color, show_start=(idx == 0), ax=ax
        )

    # 添加主次天体
    orbit_plotter.plot_primary_bodies(ax=ax)
    orbit_plotter.plot_libration_points(ax=ax)

    # 添加颜色条
    sm = plt.cm.ScalarMappable(
        cmap=cmap, norm=Normalize(vmin=jacobi_min, vmax=jacobi_max)
    )
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
    cbar.set_label("Jacobi Constant", fontsize=12)

    # 设置标签和标题
    ax.set_xlabel("X (nondimensional)", fontsize=12)
    ax.set_ylabel("Y (nondimensional)", fontsize=12)
    ax.set_title(
        f"{label} Resonant Orbit Family in Earth-Moon CR3BP (XY Plane)\n"
        f"{n_orbits} orbits, C = [{jacobi_min:.4f}, {jacobi_max:.4f}]",
        fontsize=12,
    )
    ax.legend(loc="upper right", fontsize=10)
    ax.set_aspect("equal")

    plt.tight_layout()

    # 保存图形
    output_path = f"output/ro/{label}_ro_family_2d.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"2D视图已保存: {output_path}")
    plt.show()


def plot_ro_family_3d(family, config_name, system):
    """绘制RO族3D视图

    参数:
        family: OrbitFamily对象
        config_name: str, "3:2" 或 "3:1"
        system: CR3BP_System对象
    """
    config = FAMILY_CONFIGS[config_name]
    label = config["label"]
    n_orbits = len(family)

    # 计算Jacobi常数
    jacobi_values = family.get_jacobi_constants().tolist()
    jacobi_min, jacobi_max = min(jacobi_values), max(jacobi_values)

    # 创建可视化器
    orbit_plotter = OrbitVisualizer(system=system)
    orbit_plotter.primary_body_color = "blue"
    orbit_plotter.secondary_body_color = "silver"

    # 颜色映射
    cmap = matplotlib.colormaps["coolwarm"]
    jacobi_range = jacobi_max - jacobi_min if jacobi_max != jacobi_min else 1.0

    # 创建3D图形
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection="3d")

    # 全局3D视图参数
    center_x = -0.9 if label == "3:2" else -0.85
    radius = 0.5

    # 绘制所有轨道
    for idx in range(n_orbits):
        orbit = family[idx]
        norm_jacobi = (jacobi_values[idx] - jacobi_min) / jacobi_range
        color = cmap(norm_jacobi)
        orbit_plotter.plot_3d_orbit(
            orbit, color=color, show_start=(idx == 0), ax=ax
        )

    # 添加主次天体和平动点
    orbit_plotter.plot_primary_bodies(ax=ax, is_3d=True)
    orbit_plotter.plot_libration_points(ax=ax, is_3d=True)

    # 设置坐标轴范围
    ax.set_xlim(center_x - radius, center_x + radius)
    ax.set_ylim(-radius, radius)
    ax.set_zlim(-radius, radius)

    # 设置标签
    ax.set_xlabel("X (nondimensional)", fontsize=12)
    ax.set_ylabel("Y (nondimensional)", fontsize=12)
    ax.set_zlabel("Z (nondimensional)", fontsize=12)
    ax.set_title(
        f"{label} Resonant Orbit Family in Earth-Moon CR3BP (3D View)\n"
        f"{n_orbits} orbits, C = [{jacobi_min:.4f}, {jacobi_max:.4f}]",
        fontsize=12,
    )

    # 添加颜色条
    sm = plt.cm.ScalarMappable(
        cmap=cmap, norm=Normalize(vmin=jacobi_min, vmax=jacobi_max)
    )
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.1)
    cbar.set_label("Jacobi Constant", fontsize=11)

    # 设置视角
    ax.view_init(elev=0, azim=-90)

    plt.tight_layout()

    # 保存图形
    output_path = f"output/ro/{label}_ro_family_3d.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"3D视图已保存: {output_path}")
    plt.show()


def plot_ro_family_period_stability(family, config_name, system):
    """绘制RO族周期-稳定性图

    参数:
        family: OrbitFamily对象
        config_name: str, "3:2" 或 "3:1"
        system: CR3BP_System对象
    """
    config = FAMILY_CONFIGS[config_name]
    label = config["label"]
    target_period = config["target_period"]

    # 计算Jacobi常数和稳定性指数
    jacobi_values = family.get_jacobi_constants().tolist()
    stability_values = compute_stability_for_family(family, system)

    # 创建双纵轴图
    fig, ax1 = plt.subplots(figsize=(12, 7))

    # 左纵轴：周期
    color_period = "tab:blue"
    ax1.set_xlabel("Jacobi Constant", fontsize=12)
    ax1.set_ylabel("Period (nondimensional)", color=color_period, fontsize=12)
    (line_period,) = ax1.plot(
        jacobi_values,
        family.periods,
        "o-",
        color=color_period,
        markersize=5,
        label="Period",
    )
    ax1.tick_params(axis="y", labelcolor=color_period)

    # 添加目标周期线
    ax1.axhline(y=target_period, color="green", linestyle="--", alpha=0.7,
                label=f"Target Period ({target_period:.4f})")

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
        f"{label} Resonant Orbit Family - Period and Stability\n"
        f"Period Target: {target_period:.4f} TU ({target_period * 4.348:.2f} days)",
        fontsize=12,
    )

    # 合并图例
    lines = [line_period, line_stability]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper right", fontsize=10)

    plt.tight_layout()

    # 保存图形
    output_path = f"output/ro/{label}_ro_family_period_stability.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"周期-稳定性图已保存: {output_path}")
    plt.show()


# =============================================================================
# 主程序
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="RO族可视化")
    parser.add_argument(
        "--family",
        choices=["32", "31", "both"],
        default="both",
        help="选择要可视化的RO族",
    )
    parser.add_argument(
        "--plots",
        choices=["2d", "3d", "period", "all"],
        default="all",
        help="选择要生成的图表类型",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("共振轨道(RO)族可视化")
    print("=" * 60)

    # 创建系统
    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

    families_to_plot = []
    if args.family in ["32", "both"]:
        families_to_plot.append("3:2")
    if args.family in ["31", "both"]:
        families_to_plot.append("3:1")

    for config_name in families_to_plot:
        print(f"\n处理 {config_name} RO族...")
        family = load_family(config_name, system)
        if family is None:
            continue

        if args.plots in ["2d", "all"]:
            plot_ro_family_2d(family, config_name, system)

        if args.plots in ["3d", "all"]:
            plot_ro_family_3d(family, config_name, system)

        if args.plots in ["period", "all"]:
            plot_ro_family_period_stability(family, config_name, system)

    print(f"\n{'=' * 60}")
    print("完成！")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
