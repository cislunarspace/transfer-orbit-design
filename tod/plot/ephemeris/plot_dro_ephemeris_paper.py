# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""plot_dro_ephemeris_paper 可视化脚本。

本模块读取 DRO 星历修正 JSON 结果，生成论文版三子图纵向布局：
J2000 惯性系 XY、会合坐标系 XY、地心距随时间变化。中文标签，DPI ≥ 300。

运行示例:
    .. code-block:: bash

       uv run python -m tod.plot.ephemeris.plot_dro_ephemeris_paper --help
"""


from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from e2m2e.core import Orbit, CR3BP_System, SynodicJ2000Transformation
from e2m2e.core.spice import SPICEManager
from e2m2e.core.ephemeris_system import EphemerisSystem
from e2m2e.core.ephemeris_dynamics import EphemerisDynamics
from e2m2e.mbse.data.enums import ReferenceFrame

from tod.commons.constants import DU, MU, TU
from tod.commons.common import find_project_root
from tod.plot.config import apply_standard_plot_config

logger = logging.getLogger(__name__)

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

DRO_JSON_DEFAULT = project_root / "output" / "dro" / "dro_31_1780135710.json"
EPHEMERIS_JSON_DEFAULT = (
    project_root
    / "output"
    / "ephemeris"
    / "dro_single_ephemeris_conversion_20260609_105936.json"
)


def parse_args(argv=None):
    """解析命令行参数。

    Args:
        argv: 命令行参数列表，None 时使用 sys.argv（argparse 默认行为）。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(
        description="绘制 DRO 星历修正结果论文版图（中文标签，纵向三子图）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径")
    parser.add_argument("--ephemeris-file", type=str, default=None, help="星历修正 JSON 文件路径")
    parser.add_argument("--out-file", type=str, default=None, help="输出图片路径")
    parser.add_argument("--dpi", type=int, default=300, help="输出图片 DPI")
    return parser.parse_args(argv)


def load_ephemeris_result(json_file: Path) -> dict:
    """加载星历修正 JSON 结果。

    Args:
        json_file: 星历修正 JSON 文件路径。

    Returns:
        dict，包含 metadata 和 result 字段。
    """
    with open(json_file, encoding="utf-8") as f:
        return json.load(f)


def propagate_corrected_segments(
    corrected_states: np.ndarray,
    corrected_times: np.ndarray,
    dynamics: EphemerisDynamics,
) -> tuple[np.ndarray, np.ndarray]:
    """从修正后的拼接点逐段传播完整闭合轨道。

    Args:
        corrected_states: 修正后的状态数组 (n, 6)。
        corrected_times: 修正后的时间数组 (n,)，ET 秒。
        dynamics: 星历动力学对象。

    Returns:
        (full_states, full_times)：完整轨道状态和时间。
    """
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
    """执行脚本主流程。

    Args:
        argv: 命令行参数列表，None 时使用 sys.argv。

    Returns:
        None。

    Raises:
        FileNotFoundError: 当输入文件不存在时。
        Exception: 当输入数据、文件或数值流程不满足脚本要求时抛出。
    """
    args = parse_args(argv)

    dro_file = Path(args.dro_file) if args.dro_file else DRO_JSON_DEFAULT
    ephemeris_file = Path(args.ephemeris_file) if args.ephemeris_file else EPHEMERIS_JSON_DEFAULT
    out_file = Path(args.out_file) if args.out_file else (
        project_root / "figures" / "结果" / "星历修正DRO论文版.png"
    )

    if not ephemeris_file.is_file():
        raise FileNotFoundError(f"星历修正文件不存在: {ephemeris_file}")
    if not dro_file.is_file():
        raise FileNotFoundError(f"DRO 文件不存在: {dro_file}")

    # ---------- 加载结果 ----------
    eph_data = load_ephemeris_result(ephemeris_file)
    result = eph_data["result"]
    reference_epoch = eph_data["metadata"]["reference_epoch"]

    logger.info(f"参考历元: {reference_epoch}")
    logger.info(f"收敛: {result['converged']}")
    logger.info(f"迭代次数: {result['iterations']}")
    logger.info(f"最大残差: {result['max_residual']:.2e} km")
    logger.info(f"拼接点数: {len(result['corrected_states'])}")

    # ---------- 加载 DRO ----------
    cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dro_orbit = Orbit.load_from_file(filename=dro_file, system=cr3bp_system)
    period_tu = dro_orbit.period
    logger.info(f"DRO 周期: {period_tu * TU:.3f} days")

    # ---------- SPICE ----------
    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    spice.load_kernel(kernel_path)
    ref_et = spice.utc_to_et(reference_epoch)

    try:
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
            frame=ReferenceFrame.J2000,
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
        logger.info(f"修正后平均地心距: {mean_dist:.2e} km")

        # 平均月距
        r_moon_syn = np.linalg.norm(
            eph_full_syn[:, :3] - np.array([1 - MU, 0, 0]), axis=1
        ) * DU
        mean_moon_dist = np.mean(r_moon_syn)
        logger.info(f"修正后平均月距: {mean_moon_dist:.2e} km")

        # ---------- 绘图 ----------
        # 单栏纵向三子图：J2000 惯性系 XY、会合坐标系 XY、地心距随时间变化
        fig = plt.figure(figsize=(8.5 / 2.54, 17 / 2.54))
        gs = fig.add_gridspec(3, 1, height_ratios=[1.1, 1.1, 0.7], hspace=0.5)

        # --- 上: J2000 惯性系 XY ---
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(
            dro_j2000[:, 0] / 1e3, dro_j2000[:, 1] / 1e3,
            "-", color=COLOR_CR3BP, lw=1.0, alpha=0.6, label="CR3BP DRO",
        )
        ax1.plot(
            eph_full_j2000[:, 0] / 1e3, eph_full_j2000[:, 1] / 1e3,
            "-", color=COLOR_EPH, lw=1.5, label="星历修正",
        )
        ax1.scatter(
            corrected_states[:, 0] / 1e3, corrected_states[:, 1] / 1e3,
            c=COLOR_PATCH, s=18, zorder=5, marker="o",
            edgecolors="white", linewidths=0.5,
        )
        ax1.scatter(0, 0, color="green", s=40, zorder=5, marker="*", label="地球")
        ax1.set_xlabel(r"$X$（$\times 10^3$ km）", fontsize=PLOT_CONFIG.label)
        ax1.set_ylabel(r"$Y$（$\times 10^3$ km）", fontsize=PLOT_CONFIG.label)
        ax1.set_title("J2000 惯性系", fontsize=PLOT_CONFIG.title)
        ax1.tick_params(labelsize=PLOT_CONFIG.tick)
        ax1.legend(fontsize=PLOT_CONFIG.legend, loc="best")
        ax1.set_aspect("equal")
        ax1.grid(True, alpha=0.3)

        # --- 中: 会合坐标系 XY ---
        ax2 = fig.add_subplot(gs[1])
        ax2.plot(
            dro_syn[:, 0], dro_syn[:, 1],
            "-", color=COLOR_CR3BP, lw=1.0, alpha=0.6, label="CR3BP DRO",
        )
        ax2.plot(
            eph_full_syn[:, 0], eph_full_syn[:, 1],
            "-", color=COLOR_EPH, lw=1.5, label="星历修正",
        )
        ax2.scatter(
            syn_patch[:, 0], syn_patch[:, 1],
            c=COLOR_PATCH, s=18, zorder=5, marker="o",
            edgecolors="white", linewidths=0.5,
        )
        ax2.scatter(1 - MU, 0, color=COLOR_MOON, s=30, zorder=5, label="月球")
        ax2.scatter(-MU, 0, color=COLOR_EARTH, s=60, zorder=5, label="地球")
        ax2.set_xlabel(r"$X$（DU）", fontsize=PLOT_CONFIG.label)
        ax2.set_ylabel(r"$Y$（DU）", fontsize=PLOT_CONFIG.label)
        ax2.set_title("会合坐标系", fontsize=PLOT_CONFIG.title)
        ax2.tick_params(labelsize=PLOT_CONFIG.tick)
        ax2.legend(fontsize=PLOT_CONFIG.legend, loc="best")
        ax2.set_aspect("equal")
        ax2.grid(True, alpha=0.3)

        # --- 下: 地心距随时间变化 ---
        ax3 = fig.add_subplot(gs[2])
        t_days = (eph_full_times - ref_et) / 86400
        ax3.plot(
            t_days, r_earth_j2000 / 1e3,
            "-", color=COLOR_EPH, lw=1.5, label="地心距",
        )
        ax3.axhline(
            y=mean_dist / 1e3, color="gray", ls="--", alpha=0.5,
            label=f"平均 {mean_dist/1e3:.0f} km",
        )
        ax3.set_xlabel("时间（天）", fontsize=PLOT_CONFIG.label)
        ax3.set_ylabel(r"地心距（$\times 10^3$ km）", fontsize=PLOT_CONFIG.label)
        ax3.set_title("地心距随时间变化", fontsize=PLOT_CONFIG.title)
        ax3.tick_params(labelsize=PLOT_CONFIG.tick)
        ax3.legend(fontsize=PLOT_CONFIG.legend, loc="best")
        ax3.grid(True, alpha=0.3)

        out_file.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_file, dpi=args.dpi, bbox_inches="tight")
        logger.info(f"已保存: {out_file}")
        plt.close(fig)

    finally:
        spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        logger.debug("无命令行参数，使用默认值运行")
    main()


# ------------------------------------------------------------------
# GUI 注册
# ------------------------------------------------------------------

from tod.scripting import CliParam, ScriptEntry

SCRIPT_ENTRY = ScriptEntry(
    module='ephemeris',
    name='plot_dro_ephemeris_paper',
    description='绘制 DRO 星历修正结果论文版图',
    script_path='tod/plot/ephemeris/plot_dro_ephemeris_paper.py',
    output_dir='figures/结果',
    needs_spice=True,
    group_label='绘图',
    cli_params=[
        CliParam('--dro-file', 'DRO 文件', 'str', '', help='DRO 轨道 JSON 文件路径。', file_category='dro'),
        CliParam('--ephemeris-file', '星历修正文件', 'str', '', help='星历修正 JSON 文件路径。', file_category='ephemeris'),
        CliParam('--out-file', '输出路径', 'str', '', help='输出图片路径，默认 figures/结果/星历修正DRO论文版.png。'),
        CliParam('--dpi', 'DPI', 'int', '300', help='输出图片 DPI。'),
    ],
)
