# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportInvalidTypeForm=false, reportCallIssue=false, reportPrivateImportUsage=false
"""plot_ephemeris_correction 可视化脚本。

本模块读取轨道、转移或星历修正 JSON 结果，并生成用于检查几何形态、
稳定性或优化质量的图形。输入文件通常来自 output/ 下的生成、搜索或优化结果；
输出为 Matplotlib 窗口或保存图片。

运行示例:
    .. code-block:: bash

       uv run python -m plot.ephemeris.plot_ephemeris_correction --help
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from e2m2e.algorithm.coordinate.synodic_j2000 import SynodicJ2000System
from e2m2e.algorithm.dynamics import CR3BP_System
from e2m2e.data.types.orbit import Orbit

try:
    from e2m2e.algorithm.dynamics import EphemerisDynamics, EphemerisSystem
    from e2m2e.data.kernels.manager import SPICEManager
except ImportError:

    class _MissingEphemerisApi:
        """延迟报告当前 e2m2e 版本缺少星历绘图所需 API。"""

        def __init__(self, *args, **kwargs):
            raise RuntimeError("当前 e2m2e 安装缺少星历绘图所需的 SPICE/Ephemeris API。")

    SPICEManager = EphemerisSystem = EphemerisDynamics = _MissingEphemerisApi
from plot.config import apply_standard_plot_config
from src.commons.constants import DU, MU, TU
from src.commons.paths import find_project_root

logger = logging.getLogger(__name__)
project_root = find_project_root(Path(__file__))

output_dir = project_root / "output" / "ephemeris"
PLOT_CONFIG = apply_standard_plot_config()

DRO_JSON_DEFAULT = project_root / "output" / "dro" / "dro_31_3857864736.json"
EPHEMERIS_JSON_DEFAULT = output_dir / "dro_ephemeris_correction_20260406_120419.json"


def parse_args():
    """解析命令行参数。

    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(
        description="绘制 DRO 星历修正前后对比图",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--dro-file", type=str, default=None, help="DRO 轨道 JSON 文件路径")
    parser.add_argument("--ephemeris-file", type=str, default=None, help="星历修正 JSON 文件路径")
    parser.add_argument(
        "--reference-epoch",
        type=str,
        default=None,
        help=(
            "参考历元；可选，未填时使用星历修正 JSON 中的 reference_epoch，填写时必须与 JSON 一致。"
        ),
    )
    return parser.parse_args()


REFERENCE_EPOCH = "2025-06-21T11:00:06"
SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
BODIES = ["EARTH", "MOON", "SUN"]
TU_SECONDS = TU * 86400
N_PERIODS = 3
J2000_AXIS_LABELS = ("X (DU)", "Y (DU)", "Z (DU)")


def resolve_reference_epoch(
    eph_data: dict,
    requested_reference_epoch: str | None,
) -> str:
    """从星历修正 JSON 和用户请求中解析参考历元。

    未传入时返回 JSON 顶层 ``reference_epoch``；传入时必须严格字符串
    相等，否则抛出 ValueError。

    Args:
        eph_data: 已加载的星历修正 JSON 字典。
        requested_reference_epoch: 用户通过 ``--reference-epoch`` 传入的值。

    Returns:
        经过校验的参考历元字符串。

    Raises:
        ValueError: 当显式值与 JSON 值不一致时。
        KeyError: 当 JSON 中缺少 ``reference_epoch`` 字段时。
    """
    if "reference_epoch" not in eph_data:
        raise ValueError("星历修正 JSON 缺少 reference_epoch，无法确定 synodic/J2000 转换参考历元")
    json_reference_epoch = eph_data["reference_epoch"]
    if requested_reference_epoch is None:
        return json_reference_epoch
    if requested_reference_epoch != json_reference_epoch:
        raise ValueError(
            f"显式传入的 --reference-epoch（{requested_reference_epoch!r}）"
            f"与 JSON 中的 reference_epoch（{json_reference_epoch!r}）不一致"
        )
    return json_reference_epoch


def set_axes_equal(ax):
    """将三维坐标轴设置为等比例显示。

    Args:
        ax: 调用方传入的参数值。

    Returns:
        None。
    """
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
    """执行 tile_orbit_n_periods 对应的处理逻辑。

    Args:
        orbit: 调用方传入的参数值。
        n: 调用方传入的参数值。

    Returns:
        函数执行结果。
    """
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
    ephemeris_json_file = (
        Path(args.ephemeris_file) if args.ephemeris_file else EPHEMERIS_JSON_DEFAULT
    )

    if not ephemeris_json_file.is_file():
        raise FileNotFoundError(f"星历修正数据文件不存在: {ephemeris_json_file}")

    with open(ephemeris_json_file, encoding="utf-8") as f:
        eph_data = json.load(f)
    reference_epoch = resolve_reference_epoch(eph_data, args.reference_epoch)

    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    import spiceypy

    # 闰秒 kernel 版本随发行变化（naif0011/naif0012/...），按 glob 取最新
    leapseconds_candidates = sorted(Path(SPICE_KERNEL_DIR).glob("naif*.tls"))
    if not leapseconds_candidates:
        raise FileNotFoundError(
            f"SPICE kernel 目录中找不到闰秒文件 (naif*.tls): {SPICE_KERNEL_DIR}"
        )
    spiceypy.furnsh(str(leapseconds_candidates[-1]))
    spice.load_kernel(kernel_path)

    try:
        reference_et = spice.utc_to_et(reference_epoch)
        cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
        syn_j2000 = SynodicJ2000System(
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

        logger.info(f"CR3BP DRO (synodic, 1 period): {len(dro_syn_1p)} 个状态点")
        logger.info(f"CR3BP DRO (J2000, 3 periods): {len(dro_j2000)} 个状态点")
        logger.info(f"星历轨迹 (3 periods): {len(eph_j2000)} 个状态点")
        logger.info(f"修正结果: {ephemeris_json_file.name}")

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

        ax2.set_xlabel(J2000_AXIS_LABELS[0])
        ax2.set_ylabel(J2000_AXIS_LABELS[1])
        ax2.set_zlabel(J2000_AXIS_LABELS[2])
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
        logger.info(f"已保存: {out_path}")
        plt.show()

    finally:
        spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用时不影响。
    # 想调哪个值就改下方对应字面量即可。
    if len(sys.argv) == 1:
        logger.debug("使用代码内置调试参数")
    main()
