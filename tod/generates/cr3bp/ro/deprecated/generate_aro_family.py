"""generate_aro_family 轨道生成脚本。

本模块在地月 CR3BP 中构造种子轨道，调用 e2m2e 的微分修正、自然延拓或伪弧长延拓算法生成目标轨道。输入为命令行给出的初始状态、周期猜测和延拓配置；输出为 output/ 下对应轨道类别的 JSON/CSV 文件。

运行示例:
    .. code-block:: bash

       uv run python -m tod.generates.cr3bp.ro.generate_aro_family --help
"""


import argparse
import logging
import sys
import time
from pathlib import Path

import e2m2e
from tod.commons.constants import MU, TU

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
OUTPUT_DIR = project_root / "output"
RO_32_FAMILY_FILE = OUTPUT_DIR / "ro" / "ro_32_family_-1.2--0.8-0.005_3856904629.json"


def parse_args():
    """解析命令行参数。
    
    Returns:
        解析后的命令行参数命名空间。
    """
    parser = argparse.ArgumentParser(description="生成 ARO 轴向共振轨道族（从 3:2 RO 分岔）", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--ro-file", type=str, default=None,
                        help="3:2 RO 轨道族 JSON 文件路径")
    parser.add_argument("--target-x0", type=float, default=-1.1318,
                        help="ARO 目标 x0（分岔点搜索）")
    parser.add_argument("--z0", type=float, default=0.1999, help="固定 z0 坐标（无量纲）")
    parser.add_argument("--vy0", type=float, default=0.4, help="初始 y 方向速度猜测（无量纲）")
    parser.add_argument("--period", type=float, default=60.0 / TU, help="初始周期猜测（无量纲）")
    parser.add_argument("--x-min", type=float, default=-1.2, help="延拓 x0 范围下限")
    parser.add_argument("--x-max", type=float, default=-0.9, help="延拓 x0 范围上限")
    parser.add_argument("--step-size", type=float, default=0.005, help="延拓步长")
    return parser.parse_args()


def main():
    """执行脚本主流程。
    
    Returns:
        None。
    """
    args = parse_args()
    family_aro = None

    ro_32_family_file = args.ro_file or str(RO_32_FAMILY_FILE)
    target_x0_aro = args.target_x0
    z0_aro = args.z0

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
    aro_bp = None
    if bifurcation_points:
        logger.info("搜索接近 x0=%.4f 的分岔点（ARO种子）...", target_x0_aro)

        aro_bp = e2m2e.algorithms.StabilityAnalysis.find_nearest_bifurcation(
            orbits=family_32.orbits,
            dynamics=dynamics,
            target_x0=target_x0_aro,
            tolerance=0.1,
        )

        if aro_bp:
            logger.info(
                "找到 ARO 分岔点: 索引=%d, x0=%.4f, z0=%.4f",
                aro_bp["orbit_index"],
                aro_bp["orbit"].states[0][0],
                aro_bp["orbit"].states[0][2],
            )
        else:
            logger.warning("未找到 ARO 分岔点，使用搜索到的第一个分岔点")
            aro_bp = bifurcation_points[0] if bifurcation_points else None

    # =============================================================================
    # 5. 从分岔点生成 ARO 族（固定 z0，改变 x0）
    # =============================================================================
    logger.info("从分岔点生成 ARO 族...")

    z0_aro = args.z0

    corrector_aro = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    corrector_aro.setup_3D_symmetric_xz_fixed_z0(z0=z0_aro)

    if aro_bp:
        x0_aro = aro_bp["orbit"].states[0][0]
    else:
        x0_aro = target_x0_aro

    y_dot0_aro = args.vy0
    seed_state_aro = [x0_aro, 0.0, z0_aro, 0.0, y_dot0_aro, 0.0]
    seed_orbit_aro = e2m2e.core.orbit.Orbit(states=[seed_state_aro], times=[0])
    seed_orbit_aro.period = args.period

    try:
        seed_orbit_aro = corrector_aro.iterate_correction(
            initial_guess=seed_orbit_aro,
            verbose=False,
        )
        logger.info(
            "ARO 种子轨道修正成功: x0=%.4f, z0=%.4f, 周期=%.2f天",
            seed_orbit_aro.states[0][0],
            seed_orbit_aro.states[0][2],
            seed_orbit_aro.period * TU,
        )
    except Exception as e:
        logger.warning("ARO 种子轨道修正失败: %s", e)
        logger.info("使用默认种子继续...")

    x_min = args.x_min
    x_max = args.x_max

    continuator_aro = e2m2e.algorithms.Continuation(corrector=corrector_aro)
    family_aro = continuator_aro.natural_continuation(
        seed_orbit=seed_orbit_aro,
        param_range=(x_min, x_max),
        step_size=args.step_size,
        verbose=False,
    )

    logger.info("ARO 族延拓完成，共 %d 条轨道", len(family_aro))

    aro_output_file = OUTPUT_DIR / "ro" / f"aro_32_family_{x_min}-{x_max}-{args.step_size}_{int(time.time())}.json"
    family_aro.save_to_file(filename=str(aro_output_file))
    logger.info("ARO 族已保存至: %s", aro_output_file)

    # =============================================================================
    # 6. 输出总结
    # =============================================================================
    logger.info("ARO 族生成完成！")
    if bifurcation_points:
        logger.info("检测到 %d 个分岔点", len(bifurcation_points))
    if family_aro is not None:
        logger.info("ARO 族: %d 条轨道", len(family_aro))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv += [
            "--target-x0", "-1.1318",
            "--z0", "0.1999",
            "--vy0", "0.4",
            "--period", "13.79908925442076",
            "--x-min", "-1.2",
            "--x-max", "-0.9",
            "--step-size", "0.005",
        ]
        logger.debug("使用代码内置调试参数")
    main()
