"""
Halo 轨道 CR3BP → 星历模型 (Ephemeris N-body) 修正

将 CR3BP 中的 Halo 轨道转换到高精度星历模型下，
使用 Two-Level Multiple Shooting 差分修正方法。

工作流:
  Step 1: 使用 Orbit.load_from_file 加载 Halo 轨道
  Step 2: 对 Halo 轨道均匀采样生成 patch points
  Step 3: synodic → J2000 坐标转换（含速度）
  Step 4: Two-Level Multiple Shooting 差分修正（星历模型）
  Step 5: 验证修正后位置连续性

依赖:
    e2m2e (Layer 1a/1b/1c/2): SPICEManager, EphemerisSystem, EphemerisDynamics,
                               SynodicJ2000Transformation, TwoLevelMultipleShooting
    SPICE kernels: de440.bsp, naif0012.tls
"""

import json
import logging
import multiprocessing
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import spiceypy
from e2m2e.algorithms import convert_to_j2000, sample_patch_points
from e2m2e.core import (
    CR3BP_System,
    EphemerisDynamics,
    EphemerisSystem,
    Orbit,
    SPICEManager,
    SynodicJ2000Transformation,
)

from tod.commons.common import DU, MU, TU
from tod.generates.ephemeris._corrector import correct_ephemeris_patch_points

logger = logging.getLogger(__name__)

# =============================================================================
# 输入输出路径设置
# =============================================================================
project_root = Path(__file__).resolve().parent.parent.parent.parent
OUTPUT_DIR = project_root / "output" / "ephemeris"
_HALO_OUTPUT_DIR = project_root / "output" / "halo"


def _resolve_halo_input_file() -> Path:
    """Resolve Halo orbit JSON input file.

    Priority:
      1. HALO_INPUT_FILE environment variable (absolute or relative path)
      2. Latest halo_*.json file in output/halo/
    """
    env_path = os.environ.get("HALO_INPUT_FILE")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = project_root / p
        return p

    candidates = sorted(_HALO_OUTPUT_DIR.glob("halo_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]

    return _HALO_OUTPUT_DIR / "halo_L1_north_default.json"


HALO_JSON_FILE = _resolve_halo_input_file()

# =============================================================================
# 多重打靶法所需要的各项参数
# =============================================================================
TU_SECONDS = TU * 86400
VU = DU / TU_SECONDS
N_PATCH_POINTS = 10
POSITION_CONTINUITY_TOL = 1e-3
VELOCITY_CONTINUITY_TOL = 1e-6
N_WORKERS = multiprocessing.cpu_count()
REFERENCE_EPOCH = "2025-06-21T11:00:06"
SPICE_KERNEL_DIR = os.environ.get(
    "SPICE_KERNEL_DIR",
    str(project_root.parent / "e2m2e" / "kernels"),
)
BODIES = ["EARTH", "MOON", "SUN"]
CORRECTION_METHOD = os.environ.get("EPHEMERIS_CORRECTION_METHOD", "two_level")
if CORRECTION_METHOD not in ("standard", "two_level"):
    raise ValueError(
        f"EPHEMERIS_CORRECTION_METHOD={CORRECTION_METHOD!r} not supported, "
        "choose 'standard' or 'two_level'"
    )


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("Halo CR3BP → 星历模型修正")
    logger.info(f"参考历元: {REFERENCE_EPOCH}")
    logger.info(f"天体: {BODIES}")
    logger.info(f"Patch points: {N_PATCH_POINTS}")
    logger.info(f"修正方法: {CORRECTION_METHOD}")

    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(SPICE_KERNEL_DIR)
    logger.info(f"SPICE kernel: {kernel_path}")

    leapseconds_path = os.path.join(SPICE_KERNEL_DIR, "naif0012.tls")
    spiceypy.furnsh(leapseconds_path)
    spice.load_kernel(kernel_path)

    try:
        reference_et = spice.utc_to_et(REFERENCE_EPOCH)

        cr3bp_system = CR3BP_System(mu=MU, primary="earth", secondary="moon")

        eph_system = EphemerisSystem(
            bodies=BODIES,
            spice=spice,
            origin="EARTH",
            frame="J2000",
        )
        eph_dynamics = EphemerisDynamics(system=eph_system)

        # Step 1: 从 JSON 文件加载 CR3BP 下的 Halo 轨道
        logger.info("Step 1: 加载 Halo 轨道 (JSON)")
        halo_orbit = Orbit.load_from_file(filename=HALO_JSON_FILE, system=cr3bp_system)
        if halo_orbit.period is None:
            raise ValueError("无法确定 Halo 轨道周期")
        logger.info(f"  文件: {HALO_JSON_FILE.name}")
        logger.info(f"  状态数: {len(halo_orbit.states)}")
        logger.info(f"  周期: {halo_orbit.period:.6f} TU ({halo_orbit.period * TU:.2f} days)")

        # Step 2: 沿轨道周期均匀采样 patch points（归一化 synodic 坐标系）
        logger.info(f"Step 2: 采样 {N_PATCH_POINTS} 个 patch points")

        t_patch_syn, states_syn = sample_patch_points(halo_orbit, N_PATCH_POINTS)

        logger.info(f"  时间范围: [0, {t_patch_syn[-1]:.4f}] TU")
        logger.info(f"  时间间隔: {t_patch_syn[1] - t_patch_syn[0]:.4f} TU")
        for i in range(N_PATCH_POINTS):
            r = np.linalg.norm(states_syn[i, :3]) * DU
            logger.info(f"  Patch {i}: t={t_patch_syn[i]:.4f}, r={r:.0f} km")

        # Step 3: Synodic → J2000 坐标转换
        logger.info("Step 3: Synodic → J2000 坐标转换")

        syn_j2000 = SynodicJ2000Transformation(
            cr3bp_system=cr3bp_system,
            spice=spice,
        )
        t_patch_j2000, states_j2000 = convert_to_j2000(
            t_patch_syn, states_syn, syn_j2000, reference_et, TU
        )

        logger.info(f"  参考历元: {REFERENCE_EPOCH} (ET={reference_et:.2f} s)")
        for i in range(len(t_patch_syn)):
            r = np.linalg.norm(states_j2000[i, :3])
            v = np.linalg.norm(states_j2000[i, 3:])
            logger.info(
                f"  Patch {i}: ET={t_patch_j2000[i]:.2f}, r={r:.0f} km, v={v:.4f} km/s"
            )

        # Step 4: 以 J2000 状态为初值，执行 Multiple Shooting 差分修正
        logger.info(f"\n{'=' * 60}")
        logger.info("Step 4: Multiple Shooting 差分修正")
        logger.info(f"{'=' * 60}")

        logger.info(f"  Patch points: {len(t_patch_j2000)}")
        logger.info(f"  最大迭代: 50")
        logger.info(f"  收敛容差: {POSITION_CONTINUITY_TOL:.1e} km")

        result = correct_ephemeris_patch_points(
            CORRECTION_METHOD,
            eph_dynamics,
            t_patch_j2000,
            states_j2000,
            tolerance=POSITION_CONTINUITY_TOL,
            max_iter=50,
            verbose=True,
            n_workers=N_WORKERS,
            kernel_dir=SPICE_KERNEL_DIR,
            velocity_tolerance=VELOCITY_CONTINUITY_TOL,
        )

        if result.converged:
            logger.info(f"\n修正收敛!")
            logger.info(f"  迭代次数: {result.iterations}")
            logger.info(f"  最大位置残差: {result.max_residual:.2e} km")
            if result.velocity_residual is not None:
                logger.info(f"  最大速度残差: {result.velocity_residual:.2e} km/s")
        else:
            logger.warning(f"\n修正未收敛")
            logger.info(f"  迭代次数: {result.iterations}")
            logger.info(f"  最大位置残差: {result.max_residual:.2e} km")

        # Step 5: 验证修正后轨迹连续性，并将结果保存为 JSON
        logger.info(f"\n{'=' * 60}")
        logger.info("Step 5: 验证与保存")
        logger.info(f"{'=' * 60}")

        corrected_states = result.state_patch
        corrected_times = result.t_patch
        n_seg = len(corrected_states) - 1

        pos_errors = []
        full_states_list = []
        full_times_list = []
        for i in range(n_seg):
            prop = eph_dynamics.propagate(
                corrected_states[i],
                (corrected_times[i], corrected_times[i + 1]),
            )
            propagated_final = prop["states"][-1]
            pos_error = np.linalg.norm(
                propagated_final[:3] - corrected_states[i + 1, :3]
            )
            pos_errors.append(pos_error)
            logger.info(f"    段 {i}→{i + 1}: 位置连续性误差 = {pos_error:.2e} km")

            seg_states = prop["states"]
            seg_times = prop["time"]
            if i > 0:
                seg_states = seg_states[1:]
                seg_times = seg_times[1:]
            full_states_list.append(seg_states)
            full_times_list.append(seg_times)

        full_states = np.vstack(full_states_list)
        full_times = np.concatenate(full_times_list)

        max_error = max(pos_errors) if pos_errors else 0.0
        logger.info(f"  最大位置连续性误差: {max_error:.2e} km")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_data = {
            "orbit_type": "halo",
            "method": CORRECTION_METHOD,
            "converged": result.converged,
            "iterations": result.iterations,
            "max_residual": float(result.max_residual),
            "velocity_residual": (
                None
                if result.velocity_residual is None
                else float(result.velocity_residual)
            ),
            "residual_history": [float(r) for r in result.residual_history],
            "velocity_residual_history": (
                None
                if result.velocity_residual_history is None
                else [float(r) for r in result.velocity_residual_history]
            ),
            "reference_epoch": REFERENCE_EPOCH,
            "n_patch_points": len(corrected_states),
            "bodies": BODIES,
            "cr3bp_halo": {
                "source_file": str(HALO_JSON_FILE),
                "x0": halo_orbit.states[0][0],
                "vy0": halo_orbit.states[0][4],
                "z0": halo_orbit.states[0][2],
                "period_tu": halo_orbit.period,
            },
            "position_errors_km": [float(e) for e in pos_errors],
            "corrected_states": corrected_states.tolist(),
            "corrected_times_et": corrected_times.tolist(),
            "full_trajectory_states": full_states.tolist(),
            "full_trajectory_times_et": full_times.tolist(),
        }

        output_file = (
            OUTPUT_DIR
            / f"halo_ephemeris_correction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        logger.info(f"\n  结果已保存: {output_file}")

    finally:
        spice.unload_kernel(kernel_path)


if __name__ == "__main__":
    main()
