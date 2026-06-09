#!/usr/bin/env python3
"""绘制 DRO 星历修正结果图 —— 用于 beamer 演示。

3:1 DRO，8 个拼接点，日-地-月星历模型，
参考历元 2025-06-21T11:00:06。
"""

import argparse
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from e2m2e.core import Orbit, CR3BP_System, SynodicJ2000Transformation
from e2m2e.core.spice import SPICEManager
from e2m2e.core.ephemeris_system import EphemerisSystem
from e2m2e.core.ephemeris_dynamics import EphemerisDynamics

from tod.commons.constants import DU, MU, TU
from tod.commons.common import find_project_root
from tod.plot.config import apply_standard_plot_config

project_root = find_project_root(Path(__file__))
PLOT_CONFIG = apply_standard_plot_config()

SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
TU_SECONDS = TU * 86400

# beamer 配色
COLOR_CR3BP = "#4A6FA5"
COLOR_EPH = "#C0392B"
COLOR_PATCH = "#E74C3C"
COLOR_EARTH = "#2E86C1"
COLOR_MOON = "#95A5A6"


def load_ephemeris_result(json_file: Path) -> dict:
    with open(json_file, encoding="utf-8") as f:
        return json.load(f)


def propagate_corrected_segments(
    corrected_states: np.ndarray,
    corrected_times: np.ndarray,
    dynamics: EphemerisDynamics,
) -> tuple[np.ndarray, np.ndarray]:
    """从修正后的拼接点逐段传播完整闭合轨道。"""
    n = len(corrected_states)
    dt = corrected_times[1] - corrected_times[0]

    full_states = []
    full_times = []
    for i in range(n):
        state0 = corrected_states[i]
        t0 = corrected_times[i]
        if i < n - 1:
            t1 = corrected_times[i + 1]
        else:
            t1 = t0 + dt  # 闭合：最后一段传播到下一个周期起点
        prop = dynamics.propagate(state0, (t0, t1))
        states = np.array(prop["states"])
        times = np.array(prop["time"])
        if i > 0:
            states = states[1:]
            times = times[1:]
        full_states.append(states)
        full_times.append(times)

    return np.vstack(full_states), np.concatenate(full_times)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dro-file",
        default=str(project_root / "output" / "dro" / "dro_31_1780135710.json"),
    )
    parser.add_argument(
        "--ephemeris-file",
        default=str(
            project_root
            / "output"
            / "ephemeris"
            / "dro_single_ephemeris_conversion_20260609_105936.json"
        ),
    )
    parser.add_argument(
        "--out-file",
        default=str(
            project_root
            / "output"
            / "ephemeris"
            / "dro_ephemeris_corrected_result.png"
        ),
    )
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args(argv)

    # ---------- 加载结果 ----------
    eph_data = load_ephemeris_result(Path(args.ephemeris_file))
    result = eph_data["result"]
    reference_epoch = eph_data["metadata"]["reference_epoch"]

    print(f"参考历元: {reference_epoch}")
    print(f"收敛: {result['converged']}")
    print(f"迭代次数: {result['iterations']}")
    print(f"最大残差: {result['max_residual']:.2e} km")
    print(f"拼接点数: {len(result['corrected_states'])}")

    # ---------- 加载 DRO ----------
    cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dro_orbit = Orbit.load_from_file(filename=args.dro_file, system=cr3bp_system)
    period_tu = dro_orbit.period
    print(f"DRO 周期: {period_tu * TU:.3f} days")

    # ---------- SPICE ----------
    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    spice.load_kernel(kernel_path)
    ref_et = spice.utc_to_et(reference_epoch)

    # ---------- 坐标转换 ----------
    syn_j2000 = SynodicJ2000Transformation(
        cr3bp_system=cr3bp_system, spice=spice
    )

    # CR3BP DRO: synodic -> J2000 (1 period)
    dro_syn = np.array(dro_orbit.states)
    t_cr3bp = np.linspace(0, period_tu, len(dro_syn))
    dro_j2000 = syn_j2000.batch_synodic_to_j2000(
        states_syn=dro_syn, t_syn_arr=t_cr3bp, et0=ref_et
    )

    # ---------- 星历动力学 ----------
    eph_system = EphemerisSystem(
        bodies=["EARTH", "MOON", "SUN"],
        spice=spice,
        origin="EARTH",
        frame="J2000",
    )
    eph_dynamics = EphemerisDynamics(system=eph_system)

    corrected_states = np.array(result["corrected_states"])
    corrected_times = np.array(result["corrected_times_et"])

    # 逐段传播完整轨道
    eph_full_j2000, eph_full_times = propagate_corrected_segments(
        corrected_states, corrected_times, eph_dynamics
    )

    # J2000 -> Synodic
    eph_t_syn = (eph_full_times - ref_et) / TU_SECONDS
    eph_full_syn = syn_j2000.batch_j2000_to_synodic(
        states_j2000=eph_full_j2000,
        t_syn_arr=eph_t_syn,
        et0=ref_et,
    )

    # 拼接点的 synodic 坐标
    syn_patch = syn_j2000.batch_j2000_to_synodic(
        states_j2000=corrected_states,
        t_syn_arr=(corrected_times - ref_et) / TU_SECONDS,
        et0=ref_et,
    )

    # 平均地心距
    r_earth_j2000 = np.linalg.norm(eph_full_j2000[:, :3], axis=1)
    mean_dist = np.mean(r_earth_j2000)
    print(f"修正后平均地心距: {mean_dist:.2e} km")

    # 地月距
    r_moon_j2000 = np.linalg.norm(eph_full_j2000[:, :3], axis=1)  # 地球为原点
    # 从地心距（这里earth是原点，所以r_earth就是到原点的距离）
    # 但要计算地月距，需要减去月球位置
    # 更简单：直接算 synodic 系中的月距
    r_moon_syn = np.linalg.norm(
        eph_full_syn[:, :3] - np.array([1 - MU, 0, 0]), axis=1
    ) * DU
    mean_moon_dist = np.mean(r_moon_syn)
    print(f"修正后平均月距: {mean_moon_dist:.2e} km")

    # ---------- 绘图 ----------
    fig = plt.figure(figsize=(16, 6))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1])

    # --- 左: J2000 XY ---
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(
        dro_j2000[:, 0] / 1e3, dro_j2000[:, 1] / 1e3,
        "-", color=COLOR_CR3BP, lw=1.0, alpha=0.6, label="CR3BP DRO",
    )
    ax1.plot(
        eph_full_j2000[:, 0] / 1e3, eph_full_j2000[:, 1] / 1e3,
        "-", color=COLOR_EPH, lw=1.5, label="Ephemeris corrected",
    )
    ax1.scatter(
        corrected_states[:, 0] / 1e3, corrected_states[:, 1] / 1e3,
        c=COLOR_PATCH, s=25, zorder=5, marker="o",
        edgecolors="white", linewidths=0.5,
    )
    ax1.scatter(0, 0, color="green", s=60, zorder=5, marker="*", label="Earth")
    ax1.set_xlabel(r"$X$ ($\times 10^3$ km)", fontsize=12)
    ax1.set_ylabel(r"$Y$ ($\times 10^3$ km)", fontsize=12)
    ax1.set_title("J2000 Inertial Frame", fontsize=PLOT_CONFIG.title)
    ax1.legend(fontsize=8, loc="best")
    ax1.set_aspect("equal")
    ax1.grid(True, alpha=0.3)

    # --- 中: Synodic XY ---
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(
        dro_syn[:, 0], dro_syn[:, 1],
        "-", color=COLOR_CR3BP, lw=1.0, alpha=0.6, label="CR3BP DRO",
    )
    ax2.plot(
        eph_full_syn[:, 0], eph_full_syn[:, 1],
        "-", color=COLOR_EPH, lw=1.5, label="Ephemeris corrected",
    )
    ax2.scatter(
        syn_patch[:, 0], syn_patch[:, 1],
        c=COLOR_PATCH, s=25, zorder=5, marker="o",
        edgecolors="white", linewidths=0.5,
    )
    ax2.scatter(1 - MU, 0, color=COLOR_MOON, s=40, zorder=5, label="Moon")
    ax2.scatter(-MU, 0, color=COLOR_EARTH, s=80, zorder=5, label="Earth")
    ax2.set_xlabel("$X$ (n.d.)", fontsize=12)
    ax2.set_ylabel("$Y$ (n.d.)", fontsize=12)
    ax2.set_title("Synodic Rotating Frame", fontsize=PLOT_CONFIG.title)
    ax2.legend(fontsize=8, loc="best")
    ax2.set_aspect("equal")
    ax2.grid(True, alpha=0.3)

    # --- 右: 距离 vs 时间 ---
    ax3 = fig.add_subplot(gs[0, 2])
    t_days = (eph_full_times - ref_et) / 86400
    ax3.plot(
        t_days, r_earth_j2000 / 1e3,
        "-", color=COLOR_EPH, lw=1.5, label="Geocentric dist.",
    )
    ax3.axhline(
        y=mean_dist / 1e3, color="gray", ls="--", alpha=0.5,
        label=f"Mean: {mean_dist/1e3:.0f} km",
    )
    ax3.set_xlabel("Time (days)", fontsize=12)
    ax3.set_ylabel("Distance ($\times 10^3$ km)", fontsize=12)
    ax3.set_title("Geocentric Distance Variation", fontsize=PLOT_CONFIG.title)
    ax3.legend(fontsize=8, loc="best")
    ax3.grid(True, alpha=0.3)

    fig.suptitle(
        f"3:1 DRO  |  8 Patch Points  |  Earth–Moon–Sun Ephemeris  |  "
        f"Converged in {result['iterations']} iterations  |  "
        f"Max residual: ${result['max_residual']:.2e}$ km",
        fontsize=PLOT_CONFIG.suptitle,
    )

    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=args.dpi, bbox_inches="tight")
    print(f"\nSaved: {out_path}")

    spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    main()
