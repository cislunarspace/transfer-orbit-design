"""
生成 3:2 RRO（反射共振轨道）族

本脚本实现：
1. 加载已有的 3:2 RO 族数据
2. 检测单值矩阵特征值分岔点（λ ≈ 1）
3. 从分岔点出发，生成 RRO（反射共振轨道）族（固定 x0，改变 z0）

技术背景：
- 论文 Section II.D: "当单值矩阵的一对特征值在实轴 +1 处碰撞时，发生切分岔，
  伴随 3D 轨道的生成"
- RRO 特征：关于 x-z 平面对称（Mirror Theorem），类似于 LPO 中的 Halo 轨道

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import e2m2e
from tod.commons.common import MU

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
OUTPUT_DIR = project_root / "output"
RO_32_FAMILY_FILE = OUTPUT_DIR / "ro" / "ro_32_family_-1.2--0.8-0.005_3856904629.json"


def parse_args():
    parser = argparse.ArgumentParser(description="生成 RRO 反射共振轨道族（从 3:2 RO 分岔）")
    parser.add_argument("--ro-file", type=str, default=None,
                        help="3:2 RO 轨道族 JSON 文件路径")
    parser.add_argument("--target-x0", type=float, default=-1.0878,
                        help="RRO 目标 x0（分岔点搜索）")
    parser.add_argument("--z-max", type=float, default=0.5, help="最大 z 幅值")
    parser.add_argument("--step-size", type=float, default=0.01, help="延拓步长")
    return parser.parse_args()


def main():
    args = parse_args()
    family_rro = None

    ro_32_family_file = args.ro_file or str(RO_32_FAMILY_FILE)
    target_x0_rro = args.target_x0

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. 加载已有的 3:2 RO 族
    # =============================================================================
    logger.info("加载 3:2 RO 族数据...")
    family_32 = e2m2e.core.orbit.OrbitFamily.load_from_file(ro_32_family_file)
    logger.info("已加载 %d 条 3:2 RO 轨道", len(family_32))

    # =============================================================================
    # 3. 检测分岔点
    # =============================================================================
    logger.info("检测分岔点...")

    bifurcation_points = e2m2e.algorithms.StabilityAnalysis.detect_bifurcation_in_family(
        orbits=family_32.orbits,
        dynamics=dynamics,
        tolerance=1e-8,
    )

    logger.info("严格容差(1e-8)下找到 %d 个分岔点", len(bifurcation_points))

    if not bifurcation_points:
        logger.info("严格容差未找到分岔点，使用宽松容差搜索最近的点...")

        min_diff = float("inf")
        best_orbit_idx = None
        best_eigenvalues = None

        for i, orbit in enumerate(family_32.orbits):
            try:
                analysis = e2m2e.algorithms.StabilityAnalysis(
                    orbit=orbit, dynamics=dynamics
                )
                analysis.compute_floquet_multipliers()

                if analysis.eigenvalues is None:
                    continue
                for lam in analysis.eigenvalues:
                    diff = abs(lam - 1.0)
                    if diff < min_diff:
                        min_diff = diff
                        best_orbit_idx = i
                        best_eigenvalues = analysis.eigenvalues
            except Exception:
                continue

        if best_orbit_idx is not None:
            logger.info(
                "找到最近的点: 索引=%d, x0=%.4f, |λ-1|=%.2e",
                best_orbit_idx,
                family_32.orbits[best_orbit_idx].states[0][0],
                min_diff,
            )

            bifurcation_points = [
                {
                    "orbit_index": best_orbit_idx,
                    "orbit": family_32.orbits[best_orbit_idx],
                    "eigenvalues": best_eigenvalues,
                    "eigenvalue_diff": min_diff,
                    "bifurcation_type": e2m2e.algorithms.stability.BifurcationType.SADDLE_NODE,
                }
            ]
    else:
        unique_bps = {}
        for bp in bifurcation_points:
            idx = bp["orbit_index"]
            if (
                idx not in unique_bps
                or bp["eigenvalue_diff"] < unique_bps[idx]["eigenvalue_diff"]
            ):
                unique_bps[idx] = bp
        bifurcation_points = list(unique_bps.values())

        logger.info("去重后有 %d 个分岔点:", len(bifurcation_points))
        for bp in bifurcation_points[:5]:
            orbit = bp["orbit"]
            x0 = orbit.states[0][0]
            z0 = orbit.states[0][2]
            logger.debug(
                "  索引: %d, x0=%.4f, z0=%.4f, |λ-1|=%.2e",
                bp["orbit_index"], x0, z0, bp["eigenvalue_diff"],
            )

    # =============================================================================
    # 4. 找到最接近论文 Table 2 值的分岔点
    # =============================================================================
    rro_bp = None
    if bifurcation_points:
        logger.info("搜索接近 x0=%.4f 的分岔点（RRO种子）...", target_x0_rro)

        rro_bp = e2m2e.algorithms.StabilityAnalysis.find_nearest_bifurcation(
            orbits=family_32.orbits,
            dynamics=dynamics,
            target_x0=target_x0_rro,
            tolerance=0.1,
        )

        if rro_bp:
            logger.info(
                "找到 RRO 分岔点: 索引=%d, x0=%.4f, z0=%.4f",
                rro_bp["orbit_index"],
                rro_bp["orbit"].states[0][0],
                rro_bp["orbit"].states[0][2],
            )
        else:
            logger.warning("未找到 RRO 分岔点，使用搜索到的第一个分岔点")
            rro_bp = bifurcation_points[0] if bifurcation_points else None

    # =============================================================================
    # 5. 从分岔点生成 RRO 族（固定 x0，改变 z0）
    # =============================================================================
    if bifurcation_points:
        logger.info("从分岔点生成 RRO 族...")

        bp_orbit = rro_bp["orbit"] if rro_bp else bifurcation_points[0]["orbit"]
        x0_rro = bp_orbit.states[0][0]
        z0_seed = bp_orbit.states[0][2]
        y_dot0 = bp_orbit.states[0][4]

        logger.info("RRO 种子状态: x0=%.4f, z0=%.4f, y_dot0=%.4f", x0_rro, z0_seed, y_dot0)

        corrector_rro = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
        corrector_rro.setup_3D_symmetric_x_fixed_x0(x0=x0_rro)

        seed_state_rro = bp_orbit.states[0].copy()
        seed_orbit_rro = e2m2e.core.orbit.Orbit(states=[seed_state_rro], times=[0])
        seed_orbit_rro.period = bp_orbit.period

        z_min = z0_seed
        z_max = args.z_max
        step_size = args.step_size

        continuator_rro = e2m2e.algorithms.Continuation(corrector=corrector_rro)
        family_rro = continuator_rro.natural_continuation(
            seed_orbit=seed_orbit_rro,
            param_range=(z_min, z_max),
            step_size=step_size,
            verbose=False,
        )

        logger.info("RRO 族延拓完成，共 %d 条轨道", len(family_rro))

        rro_output_file = OUTPUT_DIR / "ro" / f"rro_32_family_{z_min}-{z_max}-{args.step_size}_{int(time.time())}.json"
        family_rro.save_to_file(filename=str(rro_output_file))
        logger.info("RRO 族已保存至: %s", rro_output_file)

    # =============================================================================
    # 6. 输出总结
    # =============================================================================
    logger.info("RRO 族生成完成！")
    if bifurcation_points:
        logger.info("检测到 %d 个分岔点", len(bifurcation_points))
    if family_rro is not None:
        logger.info("RRO 族: %d 条轨道", len(family_rro))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += [
            "--target-x0", "-1.0878",
            "--z-max", "0.5",
            "--step-size", "0.01",
        ]
        logger.debug("使用代码内置调试参数")
    main()
