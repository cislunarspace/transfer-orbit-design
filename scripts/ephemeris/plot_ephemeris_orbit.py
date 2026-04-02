"""
通用星历轨道可视化

从 JSON 文件加载星历修正结果（correct_dro_to_ephemeris.py 输出），
传播各段轨道并生成多维度可视化图表。

支持：
  - 任意轨道类型（DRO、Halo、RO 等）
  - J2000 km 坐标系 / CR3BP synodic 无量纲坐标系 两种展示模式
  - 3D 轨道图、2D 投影图、距离时间曲线、位置连续性验证、残差收敛图

用法:
    修改下方 CONFIG 区域的参数，然后直接运行脚本即可。
    python -m scripts.ephemeris.plot_ephemeris_orbit

依赖:
    e2m2e: SPICEManager, EphemerisSystem, EphemerisDynamics,
           SynodicJ2000Transformation, OrbitVisualizer
    SPICE kernels: de440.bsp, naif0012.tls
"""

from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

import json
import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

import e2m2e
from e2m2e.core import (
    CR3BP_System,
    EphemerisDynamics,
    EphemerisSystem,
    SPICEManager,
    SynodicJ2000Transformation,
)
from e2m2e.visualization.plotting import OrbitVisualizer

from scripts.utils.params import DU, MU, TU

# =============================================================================
# CONFIG — 修改此处参数
# =============================================================================
JSON_FILENAME = "dro_ephemeris_correction_3857940253.json"

DISPLAY_MODE = "both"

OUTPUT_DIR = project_root / "output" / "ephemeris"

# =============================================================================

TU_SECONDS = TU * 86400


def find_spice_kernel():
    kernel_dir = os.environ.get(
        "SPICE_KERNEL_DIR",
        str(project_root.parent / "e2m2e" / "kernels"),
    )
    for name in ["de440.bsp", "de440s.bsp", "de438.bsp"]:
        path = os.path.join(kernel_dir, name)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"SPICE kernel not found in {kernel_dir}. Set SPICE_KERNEL_DIR."
    )


def load_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def propagate_segments(data, eph_dynamics):
    corrected_states = np.array(data["corrected_states"])
    corrected_times = np.array(data["corrected_times_et"])
    n_seg = len(corrected_states) - 1

    all_states = []
    all_times = []

    for i in range(n_seg):
        print(f"  传播段 {i + 1}/{n_seg}...")
        result = eph_dynamics.propagate(
            corrected_states[i],
            (corrected_times[i], corrected_times[i + 1]),
        )
        seg_states = result["states"].T
        seg_times = result["time"]

        if i == 0:
            all_states.append(seg_states)
            all_times.append(seg_times)
        else:
            all_states.append(seg_states[1:])
            all_times.append(seg_times[1:])

    full_states = np.vstack(all_states)
    full_times = np.concatenate(all_times)

    return full_states, full_times


def get_body_positions(spice, times_et, bodies, origin="EARTH", frame="J2000"):
    positions = {}
    for body in bodies:
        if body == origin:
            continue
        pos = np.array([spice.get_body_position(body, t, frame, origin) for t in times_et])
        positions[body] = pos
    return positions


def convert_to_synodic(states_j2000, times_et, data, spice):
    cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    syn_j2000 = SynodicJ2000Transformation(cr3bp_system=cr3bp_system, spice=spice)
    reference_et = spice.utc_to_et(data["reference_epoch"])

    t_syn = (times_et - reference_et) / TU_SECONDS
    states_syn = syn_j2000.batch_j2000_to_synodic(states_j2000, t_syn, reference_et)

    return states_syn, t_syn, cr3bp_system


# =============================================================================
# 1. J2000 3D 轨道图
# =============================================================================
def plot_j2000_3d(full_states, body_positions, data, save_prefix):
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection="3d")

    ax.plot(
        full_states[:, 0] / 1e3,
        full_states[:, 1] / 1e3,
        full_states[:, 2] / 1e3,
        "b-", linewidth=0.8, label="Orbit",
    )

    patch_states = np.array(data["corrected_states"])
    ax.scatter(
        patch_states[:, 0] / 1e3,
        patch_states[:, 1] / 1e3,
        patch_states[:, 2] / 1e3,
        c="red", s=30, marker="o", label="Patch points", zorder=5,
    )

    ax.scatter([0], [0], [0], c="blue", s=120, marker="o", label="Earth", zorder=5)

    if "MOON" in body_positions:
        moon_pos = body_positions["MOON"]
        ax.scatter(
            moon_pos[:, 0] / 1e3,
            moon_pos[:, 1] / 1e3,
            moon_pos[:, 2] / 1e3,
            c="silver", s=40, marker="o", alpha=0.3, label="Moon positions",
        )
        mid = len(moon_pos) // 2
        ax.scatter(
            moon_pos[mid, 0] / 1e3,
            moon_pos[mid, 1] / 1e3,
            moon_pos[mid, 2] / 1e3,
            c="gray", s=80, marker="o", label="Moon (mid)", zorder=5,
        )

    ax.set_xlabel("X (×10³ km)", fontsize=11)
    ax.set_ylabel("Y (×10³ km)", fontsize=11)
    ax.set_zlabel("Z (×10³ km)", fontsize=11)
    ax.set_title(
        f"Ephemeris Orbit — J2000 Frame\n"
        f"Epoch: {data['reference_epoch']}, Bodies: {', '.join(data['bodies'])}",
        fontsize=12,
    )
    ax.legend(loc="upper right", fontsize=9)

    ax.view_init(elev=25, azim=-60)

    plt.tight_layout()
    plt.savefig(save_prefix + "_j2000_3d.png", dpi=300, bbox_inches="tight")
    plt.show()


# =============================================================================
# 2. J2000 2D 投影图 (XY / XZ / YZ)
# =============================================================================
def plot_j2000_2d_projections(full_states, body_positions, data, save_prefix):
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    plane_labels = [("X", "Y"), ("X", "Z"), ("Y", "Z")]
    plane_indices = [(0, 1), (0, 2), (1, 2)]
    plane_names = ["XY", "XZ", "YZ"]

    patch_states = np.array(data["corrected_states"])

    for ax, (i, j), (lx, ly), name in zip(axes, plane_indices, plane_labels, plane_names):
        ax.plot(
            full_states[:, i] / 1e3,
            full_states[:, j] / 1e3,
            "b-", linewidth=0.8,
        )
        ax.scatter(
            patch_states[:, i] / 1e3,
            patch_states[:, j] / 1e3,
            c="red", s=25, marker="o", zorder=5,
        )
        ax.scatter([0], [0], c="blue", s=80, marker="o", zorder=5, label="Earth")

        if "MOON" in body_positions:
            moon_pos = body_positions["MOON"]
            ax.scatter(
                moon_pos[:, i] / 1e3,
                moon_pos[:, j] / 1e3,
                c="silver", s=15, marker=".", alpha=0.3,
            )
            mid = len(moon_pos) // 2
            ax.scatter(
                [moon_pos[mid, i] / 1e3],
                [moon_pos[mid, j] / 1e3],
                c="gray", s=60, marker="o", zorder=5, label="Moon",
            )

        ax.set_xlabel(f"{lx} (×10³ km)", fontsize=10)
        ax.set_ylabel(f"{ly} (×10³ km)", fontsize=10)
        ax.set_title(f"{name} Plane (J2000)", fontsize=11)
        ax.set_aspect("equal")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_prefix + "_j2000_2d.png", dpi=300, bbox_inches="tight")
    plt.show()


# =============================================================================
# 3. Synodic 无量纲坐标可视化 (2D + 3D)
# =============================================================================
def plot_synodic_views(states_syn, t_syn, cr3bp_system, data, save_prefix):
    plotter = OrbitVisualizer(system=cr3bp_system)
    plotter.primary_body_color = "blue"
    plotter.secondary_body_color = "silver"
    plotter.libration_point_colors = ["gray"] * 5
    plotter.libration_point_markers = ["^"] * 5
    plotter.libration_point_sizes = [60] * 5

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    plane_names = ["xy", "xz", "yz"]
    plane_titles = ["XY Plane", "XZ Plane", "YZ Plane"]

    for ax, plane, title in zip(axes, plane_names, plane_titles):
        plotter.plot_2d_projection(states_syn, plane=plane, color="blue", ax=ax)
        plotter.plot_primary_bodies(ax=ax)
        plotter.plot_libration_points(ax=ax)
        ax.set_title(f"Synodic Frame — {title}", fontsize=11)
        ax.set_aspect("equal")

    plt.tight_layout()
    plt.savefig(save_prefix + "_synodic_2d.png", dpi=300, bbox_inches="tight")
    plt.show()

    fig_3d = plt.figure(figsize=(14, 10))
    ax_3d = fig_3d.add_subplot(111, projection="3d")
    plotter.plot_3d_orbit(states_syn, color="blue", label="Ephemeris orbit", ax=ax_3d, show_start=True)
    plotter.plot_primary_bodies(ax=ax_3d, is_3d=True)
    plotter.plot_libration_points(ax=ax_3d, show_labels=True, is_3d=True)

    x = states_syn[:, 0]
    y = states_syn[:, 1]
    z = states_syn[:, 2]
    cx, cy, cz = x.mean(), y.mean(), z.mean()
    r = max(x.max() - x.min(), y.max() - y.min(), z.max() - z.min()) / 2 * 1.2
    ax_3d.set_xlim(cx - r, cx + r)
    ax_3d.set_ylim(cy - r, cy + r)
    ax_3d.set_zlim(cz - r, cz + r)
    ax_3d.set_xlabel("X (nondimensional)", fontsize=11)
    ax_3d.set_ylabel("Y (nondimensional)", fontsize=11)
    ax_3d.set_zlabel("Z (nondimensional)", fontsize=11)
    ax_3d.set_title("Ephemeris Orbit — Synodic Frame (3D)", fontsize=12)
    ax_3d.legend(fontsize=9)
    ax_3d.view_init(elev=25, azim=-60)

    plt.tight_layout()
    plt.savefig(save_prefix + "_synodic_3d.png", dpi=300, bbox_inches="tight")
    plt.show()


# =============================================================================
# 4. 距离时间曲线
# =============================================================================
def plot_distance_curve(full_states, full_times, spice, data, save_prefix):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    times_days = (full_times - full_times[0]) / 86400.0

    dist_earth = np.linalg.norm(full_states[:, :3], axis=1) / 1e3
    ax1.plot(times_days, dist_earth, "b-", linewidth=1)
    ax1.set_ylabel("Distance to Earth (×10³ km)", fontsize=11)
    ax1.set_title("Distance to Earth & Moon vs Time", fontsize=12)
    ax1.grid(True, alpha=0.3)

    moon_positions = get_body_positions(spice, full_times, data["bodies"])
    if "MOON" in moon_positions:
        dist_moon = np.linalg.norm(full_states[:, :3] - moon_positions["MOON"], axis=1) / 1e3
        ax2.plot(times_days, dist_moon, "gray", linewidth=1)
        ax2.set_ylabel("Distance to Moon (×10³ km)", fontsize=11)
    ax2.set_xlabel("Time (days from epoch)", fontsize=11)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_prefix + "_distance.png", dpi=300, bbox_inches="tight")
    plt.show()


# =============================================================================
# 5. 位置连续性验证图
# =============================================================================
def plot_position_continuity(data, eph_dynamics, save_prefix):
    if "position_errors_km" not in data:
        print("  [skip] JSON 中无 position_errors_km 字段")
        return

    pos_errors = np.array(data["position_errors_km"])
    n_seg = len(pos_errors)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.semilogy(range(n_seg), pos_errors, "ro-", markersize=8, linewidth=1.5)
    ax.axhline(y=1e-6, color="green", linestyle="--", linewidth=1, label="Tolerance 1e-6 km")
    ax.set_xlabel("Segment index", fontsize=11)
    ax.set_ylabel("Position continuity error (km)", fontsize=11)
    ax.set_title("Position Continuity Error per Segment", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, which="both")

    plt.tight_layout()
    plt.savefig(save_prefix + "_continuity.png", dpi=300, bbox_inches="tight")
    plt.show()


# =============================================================================
# 6. 残差收敛图
# =============================================================================
def plot_residual_history(data, save_prefix):
    if "residual_history" not in data:
        print("  [skip] JSON 中无 residual_history 字段")
        return

    residuals = data["residual_history"]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.semilogy(range(len(residuals)), residuals, "b-o", markersize=5, linewidth=1.5)
    ax.axhline(y=1e-6, color="green", linestyle="--", linewidth=1, label="Tolerance 1e-6 km")
    ax.set_xlabel("Iteration", fontsize=11)
    ax.set_ylabel("Max residual (km)", fontsize=11)
    ax.set_title(
        f"Differential Correction Convergence\n"
        f"{'Converged' if data.get('converged') else 'Not converged'} "
        f"in {data.get('iterations', '?')} iterations",
        fontsize=12,
    )
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, which="both")

    plt.tight_layout()
    plt.savefig(save_prefix + "_residual.png", dpi=300, bbox_inches="tight")
    plt.show()


# =============================================================================
# Main
# =============================================================================
json_path = OUTPUT_DIR / JSON_FILENAME
save_prefix = str(OUTPUT_DIR / Path(JSON_FILENAME).stem)

print(f"加载数据: {JSON_FILENAME}")
data = load_json(json_path)
print(f"  收敛: {data.get('converged')}")
print(f"  迭代: {data.get('iterations')}")
print(f"  最大残差: {data.get('max_residual', 'N/A')}")
print(f"  Patch points: {data.get('n_patch_points')}")
print(f"  展示模式: {DISPLAY_MODE}")

kernel_path = find_spice_kernel()
print(f"SPICE kernel: {kernel_path}")

spice = SPICEManager()
spice.load_kernel(kernel_path)

try:
    eph_system = EphemerisSystem(
        bodies=data["bodies"],
        spice=spice,
        origin="EARTH",
        frame="J2000",
    )
    eph_dynamics = EphemerisDynamics(system=eph_system)

    print("\n传播轨道段...")
    full_states, full_times = propagate_segments(data, eph_dynamics)
    print(f"  总状态点: {len(full_states)}")

    if DISPLAY_MODE in ("j2000", "both"):
        print("\n获取天体位置...")
        body_positions = get_body_positions(spice, full_times, data["bodies"])

        print("绘制 J2000 3D 轨道图...")
        plot_j2000_3d(full_states, body_positions, data, save_prefix)

        print("绘制 J2000 2D 投影图...")
        plot_j2000_2d_projections(full_states, body_positions, data, save_prefix)

    if DISPLAY_MODE in ("synodic", "both"):
        print("\n转换到 synodic 坐标系...")
        states_syn, t_syn, cr3bp_system = convert_to_synodic(
            full_states, full_times, data, spice
        )
        print("绘制 synodic 坐标系图...")
        plot_synodic_views(states_syn, t_syn, cr3bp_system, data, save_prefix)

    print("\n绘制距离时间曲线...")
    plot_distance_curve(full_states, full_times, spice, data, save_prefix)

    print("绘制位置连续性验证图...")
    plot_position_continuity(data, eph_dynamics, save_prefix)

    print("绘制残差收敛图...")
    plot_residual_history(data, save_prefix)

    print(f"\n所有图表已保存至 {OUTPUT_DIR}")

finally:
    spice.unload_kernel(kernel_path)
