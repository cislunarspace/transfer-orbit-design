"""
绘制 DRO 星历修正前后对比图

左图: 会合坐标系 (Synodic, 无量纲) — CR3BP DRO vs 星历修正轨迹反转换回 synodic
右图: J2000 惯性系 (km) — CR3BP DRO 转换后 vs 星历修正轨迹

DRO 为 3:1 共振轨道，需 3 个周期才在 J2000 中闭合。
"""

import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from e2m2e.core import (
    Orbit,
    CR3BP_System,
    SPICEManager,
    EphemerisSystem,
    EphemerisDynamics,
    SynodicJ2000Transformation,
)

from tod.commons.common import find_project_root
project_root = find_project_root(Path(__file__))

from tod.commons.common import DU, MU, TU
from tod.commons.plot_helpers import apply_standard_plot_config

output_dir = project_root / "output" / "ephemeris"
PLOT_CONFIG = apply_standard_plot_config()

DRO_JSON_DEFAULT = project_root / "output" / "dro" / "dro_31_3857864736.json"
EPHEMERIS_JSON_DEFAULT = output_dir / "dro_ephemeris_correction_20260406_120419.json"


def parse_args():
    parser = argparse.ArgumentParser(description="绘制 DRO 星历修正前后对比图")
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径")
    parser.add_argument("--ephemeris-file", type=str, default=None, help="星历修正 JSON 文件路径")
    return parser.parse_args()

REFERENCE_EPOCH = "2025-06-21T11:00:06"
SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
BODIES = ["EARTH", "MOON", "SUN"]
TU_SECONDS = TU * 86400
N_PERIODS = 3


def set_axes_equal(ax):
    x_range = ax.get_xlim()[1] - ax.get_xlim()[0]
    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    z_range = ax.get_zlim()[1] - ax.get_zlim()[0]
    max_range = max(x_range, y_range, z_range) / 2
    mid_x = np.mean(ax.get_xlim())
    mid_y = np.mean(ax.get_ylim())
    mid_z = np.mean(ax.get_zlim())
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)


def tile_orbit_n_periods(orbit, n):
    period = orbit.period
    states_1 = np.array(orbit.states)
    times_1 = np.array(orbit.times)

    states_list = []
    times_list = []
    for k in range(n):
        offset = k * period
        if k == 0:
            states_list.append(states_1)
            times_list.append(times_1 + offset)
        else:
            states_list.append(states_1[1:])
            times_list.append(times_1[1:] + offset)

    return np.vstack(states_list), np.concatenate(times_list)


def main():
    args = parse_args()

    dro_json_file = Path(args.dro_file) if args.dro_file else DRO_JSON_DEFAULT
    ephemeris_json_file = Path(args.ephemeris_file) if args.ephemeris_file else EPHEMERIS_JSON_DEFAULT

    if not ephemeris_json_file.is_file():
        raise FileNotFoundError(f"星历修正数据文件不存在: {ephemeris_json_file}")

    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    import spiceypy

    leapseconds_path = os.path.join(SPICE_KERNEL_DIR, "naif0012.tls")
    spiceypy.furnsh(leapseconds_path)
    spice.load_kernel(kernel_path)

    try:
        reference_et = spice.utc_to_et(REFERENCE_EPOCH)
        cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
        syn_j2000 = SynodicJ2000Transformation(
            cr3bp_system=cr3bp_system,
            spice=spice,
        )

        dro_orbit = Orbit.load_from_file(filename=dro_json_file, system=cr3bp_system)
        dro_syn_1p = np.array(dro_orbit.states)
        dro_syn_3t, dro_times_3t = tile_orbit_n_periods(dro_orbit, N_PERIODS)

        dro_j2000 = syn_j2000.batch_synodic_to_j2000(
            states_syn=dro_syn_3t,
            t_syn_arr=dro_times_3t,
            et0=reference_et,
        )

        with open(ephemeris_json_file, encoding="utf-8") as f:
            eph_data = json.load(f)

        converged = eph_data["converged"]
        period_tu = eph_data["cr3bp_dro"]["period_tu"]
        corrected_states = np.array(eph_data["corrected_states"])
        corrected_times = np.array(eph_data["corrected_times_et"])
        state0 = corrected_states[0]
        t0 = corrected_times[0]
        t_end_3p = t0 + N_PERIODS * period_tu * TU_SECONDS

        eph_system = EphemerisSystem(
            bodies=BODIES,
            spice=spice,
            origin="EARTH",
            frame="J2000",
        )
        eph_dynamics = EphemerisDynamics(system=eph_system)
        prop_3p = eph_dynamics.propagate(state0, (t0, t_end_3p))
        eph_j2000 = prop_3p["states"]
        eph_times_et = prop_3p["time"]
        eph_t_syn = (eph_times_et - reference_et) / TU_SECONDS

        eph_syn = syn_j2000.batch_j2000_to_synodic(
            states_j2000=eph_j2000,
            t_syn_arr=eph_t_syn,
            et0=reference_et,
        )

        print(f"CR3BP DRO (synodic, 1 period): {len(dro_syn_1p)} 个状态点")
        print(f"CR3BP DRO (J2000, 3 periods): {len(dro_j2000)} 个状态点")
        print(f"星历轨迹 (3 periods): {len(eph_j2000)} 个状态点")
        print(f"修正结果: {ephemeris_json_file.name}")

        fig = plt.figure(figsize=(20, 9))

        # --- 左图: Synodic 坐标系 ---
        ax1 = fig.add_subplot(121, projection="3d")

        ax1.plot(
            dro_syn_1p[:, 0],
            dro_syn_1p[:, 1],
            dro_syn_1p[:, 2],
            color="royalblue",
            linewidth=1.5,
            alpha=0.7,
            label="CR3BP DRO",
        )

        n_per_period = len(eph_syn) // N_PERIODS
        eph_syn_1p = eph_syn[: n_per_period + 1]
        ax1.plot(
            eph_syn_1p[:, 0],
            eph_syn_1p[:, 1],
            eph_syn_1p[:, 2],
            color="crimson",
            linewidth=1.5,
            alpha=0.9,
            label="Ephemeris corrected",
        )

        ax1.scatter(1 - MU, 0, 0, color="silver", s=80, label="Moon")
        ax1.scatter(-MU, 0, 0, color="blue", s=200, label="Earth")

        ax1.set_xlabel("X (n.d.)")
        ax1.set_ylabel("Y (n.d.)")
        ax1.set_zlabel("Z (n.d.)")
        ax1.set_title("Synodic Frame (Rotating)", fontsize=PLOT_CONFIG.title)
        ax1.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")
        ax1.view_init(elev=25, azim=-60)
        set_axes_equal(ax1)

        # --- 右图: J2000 惯性系 ---
        ax2 = fig.add_subplot(122, projection="3d")

        ax2.plot(
            dro_j2000[:, 0] / DU,
            dro_j2000[:, 1] / DU,
            dro_j2000[:, 2] / DU,
            color="royalblue",
            linewidth=1.2,
            alpha=0.7,
            label=f"CR3BP DRO ({N_PERIODS}T)",
        )

        ax2.plot(
            eph_j2000[:, 0] / DU,
            eph_j2000[:, 1] / DU,
            eph_j2000[:, 2] / DU,
            color="crimson",
            linewidth=1.5,
            alpha=0.9,
            label=f"Ephemeris corrected ({N_PERIODS}T)",
        )

        ax2.scatter(0, 0, 0, color="green", s=100, zorder=5, label="Earth")

        ax2.set_xlabel("X (×10⁵ km)")
        ax2.set_ylabel("Y (×10⁵ km)")
        ax2.set_zlabel("Z (×10⁵ km)")
        status = "Converged" if converged else "Not converged"
        ax2.set_title(f"J2000 Inertial Frame ({status})", fontsize=PLOT_CONFIG.title)
        ax2.legend(fontsize=PLOT_CONFIG.legend, loc="upper left")
        ax2.view_init(elev=25, azim=-60)
        set_axes_equal(ax2)

        fig.suptitle(
            f"DRO CR3BP vs Ephemeris Correction\n"
            f"ref: {eph_data['reference_epoch']}, "
            f"bodies: {', '.join(eph_data['bodies'])}",
            fontsize=PLOT_CONFIG.suptitle,
            y=1.02,
        )
        plt.tight_layout()

        out_name = ephemeris_json_file.name.replace(".json", "_compare_3d.png")
        out_path = output_dir / out_name
        fig.savefig(out_path, dpi=300, bbox_inches="tight")
        print(f"已保存: {out_path}")
        plt.show()

    finally:
        spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        print("[debug] 使用代码内置调试参数")
    main()
