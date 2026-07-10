#!/usr/bin/env python3
"""绘制 DRO 星历修正结果图 —— 专用于 beamer 左侧 column。

3:1 DRO，8 个拼接点，日-地-月星历模型。
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

from e2m2e.core import Orbit, CR3BP_System, SynodicJ2000System
from e2m2e.core.spice import SPICEManager
from e2m2e.core.ephemeris_system import EphemerisSystem
from e2m2e.core.ephemeris_dynamics import EphemerisDynamics

from tod.commons.constants import DU, MU, TU
from tod.commons.common import find_project_root

project_root = find_project_root(Path(__file__))

SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
TU_SECONDS = TU * 86400

COLOR_CR3BP = "#7B8FA8"
COLOR_EPH = "#C0392B"
COLOR_PATCH = "#E74C3C"
COLOR_EARTH = "#2E86C1"
COLOR_MOON = "#95A5A6"


def load_ephemeris_result(json_file: Path) -> dict:
    with open(json_file, encoding="utf-8") as f:
        return json.load(f)


def propagate_segments(corrected_states, corrected_times, dynamics):
    n = len(corrected_states)
    dt = corrected_times[1] - corrected_times[0]
    full_states, full_times = [], []
    for i in range(n):
        state0, t0 = corrected_states[i], corrected_times[i]
        t1 = corrected_times[i + 1] if i < n - 1 else t0 + dt
        prop = dynamics.propagate(state0, (t0, t1))
        states, times = np.array(prop["states"]), np.array(prop["time"])
        if i > 0:
            states, times = states[1:], times[1:]
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
            / "dro_ephemeris_beamer.png"
        ),
    )
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args(argv)

    # 加载
    eph_data = load_ephemeris_result(Path(args.ephemeris_file))
    result = eph_data["result"]
    reference_epoch = eph_data["metadata"]["reference_epoch"]

    cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dro_orbit = Orbit.load_from_file(filename=args.dro_file, system=cr3bp_system)
    period_tu = dro_orbit.period

    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    spice.load_kernel(kernel_path)
    ref_et = spice.utc_to_et(reference_epoch)

    syn_j2000 = SynodicJ2000System(cr3bp_system=cr3bp_system, spice=spice)

    dro_syn = np.array(dro_orbit.states)
    t_cr3bp = np.linspace(0, period_tu, len(dro_syn))
    dro_j2000 = syn_j2000.batch_synodic_to_j2000(
        states_syn=dro_syn, t_syn_arr=t_cr3bp, et0=ref_et
    )

    eph_system = EphemerisSystem(
        bodies=["EARTH", "MOON", "SUN"], spice=spice,
        origin="EARTH", frame="J2000",
    )
    eph_dynamics = EphemerisDynamics(system=eph_system)

    corrected_states = np.array(result["corrected_states"])
    corrected_times = np.array(result["corrected_times_et"])

    eph_full_j2000, eph_full_times = propagate_segments(
        corrected_states, corrected_times, eph_dynamics
    )
    eph_t_syn = (eph_full_times - ref_et) / TU_SECONDS
    eph_full_syn = syn_j2000.batch_j2000_to_synodic(
        states_j2000=eph_full_j2000, t_syn_arr=eph_t_syn, et0=ref_et,
    )
    syn_patch = syn_j2000.batch_j2000_to_synodic(
        states_j2000=corrected_states,
        t_syn_arr=(corrected_times - ref_et) / TU_SECONDS,
        et0=ref_et,
    )

    # ---- 绘图：Synodic 系单图 ----
    fig, ax = plt.subplots(figsize=(6, 5.5))

    ax.plot(
        dro_syn[:, 0], dro_syn[:, 1],
        "-", color=COLOR_CR3BP, lw=1.0, alpha=0.55, label="CR3BP DRO",
    )
    ax.plot(
        eph_full_syn[:, 0], eph_full_syn[:, 1],
        "-", color=COLOR_EPH, lw=1.5, label="Ephemeris corrected",
    )
    ax.scatter(
        syn_patch[:, 0], syn_patch[:, 1],
        c=COLOR_PATCH, s=22, zorder=5, marker="o",
        edgecolors="white", linewidths=0.4,
    )
    ax.scatter(1 - MU, 0, color=COLOR_MOON, s=45, zorder=5, marker="o", label="Moon")
    ax.scatter(-MU, 0, color=COLOR_EARTH, s=80, zorder=5, marker="o", label="Earth")

    ax.set_xlabel("$X$ (n.d.)", fontsize=12)
    ax.set_ylabel("$Y$ (n.d.)", fontsize=12)
    ax.set_title("Synodic Rotating Frame", fontsize=13, pad=8)
    ax.legend(fontsize=8, loc="best")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.25)
    ax.set_xlim(-0.15, 1.2)
    ax.set_ylim(-0.25, 0.25)

    fig.tight_layout()
    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=args.dpi, bbox_inches="tight")
    print(f"Saved: {out_path}")

    spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    main()
