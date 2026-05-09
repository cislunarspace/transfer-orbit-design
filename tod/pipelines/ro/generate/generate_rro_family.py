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
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent

import e2m2e
import time
from tod.commons.common import MU, TU

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
    print("=" * 60)
    print("加载 3:2 RO 族数据...")
    family_32 = e2m2e.core.orbit.OrbitFamily.load_from_file(ro_32_family_file)
    print(f"已加载 {len(family_32)} 条 3:2 RO 轨道")

    # =============================================================================
    # 3. 检测分岔点
    # =============================================================================
    print("\n" + "=" * 60)
    print("检测分岔点...")

    # 使用较严格的容差检测分岔点
    bifurcation_points = e2m2e.algorithms.StabilityAnalysis.detect_bifurcation_in_family(
        orbits=family_32.orbits,
        dynamics=dynamics,
        tolerance=1e-8,
        # tolerance=1e-4,  # 宽松容差用于调试
    )

    print(f"严格容差(1e-8)下找到 {len(bifurcation_points)} 个分岔点")

    if not bifurcation_points:
        print("严格容差未找到分岔点，使用宽松容差搜索最近的点...")

        # 找每条轨道最小的 |λ-1| 值
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
                # Intentionally broad: Floquet multiplier computation may fail for individual orbits
                continue

        if best_orbit_idx is not None:
            print(
                f"找到最近的点: 索引={best_orbit_idx}, x0={family_32.orbits[best_orbit_idx].states[0][0]:.4f}, "
                f"|λ-1|={min_diff:.2e}"
            )

            # 创建单一分岔点
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
        # 对分岔点按 |λ-1| 排序并去重（每条轨道只取一个）
        unique_bps = {}
        for bp in bifurcation_points:
            idx = bp["orbit_index"]
            if (
                idx not in unique_bps
                or bp["eigenvalue_diff"] < unique_bps[idx]["eigenvalue_diff"]
            ):
                unique_bps[idx] = bp
        bifurcation_points = list(unique_bps.values())

        print(f"\n去重后有 {len(bifurcation_points)} 个分岔点:")
        for bp in bifurcation_points[:5]:  # 只显示前5个
            orbit = bp["orbit"]
            x0 = orbit.states[0][0]
            z0 = orbit.states[0][2]
            print(
                f"  索引: {bp['orbit_index']}, x0={x0:.4f}, z0={z0:.4f}, "
                f"|λ-1|={bp['eigenvalue_diff']:.2e}"
            )

    # =============================================================================
    # 4. 找到最接近论文 Table 2 值的分岔点
    # =============================================================================
    rro_bp = None
    if bifurcation_points:
        print("\n" + "=" * 60)
        print(f"搜索接近 x0={target_x0_rro} 的分岔点（RRO种子）...")

        rro_bp = e2m2e.algorithms.StabilityAnalysis.find_nearest_bifurcation(
            orbits=family_32.orbits,
            dynamics=dynamics,
            target_x0=target_x0_rro,
            tolerance=0.1,
        )

        if rro_bp:
            print(
                f"找到 RRO 分岔点: 索引={rro_bp['orbit_index']}, "
                f"x0={rro_bp['orbit'].states[0][0]:.4f}, "
                f"z0={rro_bp['orbit'].states[0][2]:.4f}"
            )
        else:
            print("未找到 RRO 分岔点，使用搜索到的第一个分岔点")
            rro_bp = bifurcation_points[0] if bifurcation_points else None

    # =============================================================================
    # 5. 从分岔点生成 RRO 族（固定 x0，改变 z0）
    # =============================================================================
    if bifurcation_points:
        print("\n" + "=" * 60)
        print("从分岔点生成 RRO 族...")

        # 获取分岔点的初始状态
        bp_orbit = rro_bp["orbit"] if rro_bp else bifurcation_points[0]["orbit"]
        x0_rro = bp_orbit.states[0][0]
        z0_seed = bp_orbit.states[0][2]  # 初始 z0
        y_dot0 = bp_orbit.states[0][4]

        print(f"RRO 种子状态: x0={x0_rro:.4f}, z0={z0_seed:.4f}, y_dot0={y_dot0:.4f}")

        # 配置 3D 对称修正器（固定 x0）
        corrector_rro = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
        corrector_rro.setup_3D_symmetric_x_fixed_x0(x0=x0_rro)

        # 创建种子 Orbit
        seed_state_rro = bp_orbit.states[0].copy()
        seed_orbit_rro = e2m2e.core.orbit.Orbit(states=[seed_state_rro], times=[0])
        seed_orbit_rro.period = bp_orbit.period

        # 延拓参数：z0 从种子值开始
        z_min = z0_seed
        z_max = args.z_max  # 最大 z 幅值
        step_size = args.step_size

        # 自然延拓生成 RRO 族
        continuator_rro = e2m2e.algorithms.Continuation(corrector=corrector_rro)
        family_rro = continuator_rro.natural_continuation(
            seed_orbit=seed_orbit_rro,
            param_range=(z_min, z_max),
            step_size=step_size,
            verbose=False,
        )

        print(f"RRO 族延拓完成，共 {len(family_rro)} 条轨道")

        # 保存 RRO 族
        rro_output_file = OUTPUT_DIR / "ro" / f"rro_32_family_{z_min}-{z_max}-{args.step_size}_{int(time.time())}.json"
        family_rro.save_to_file(filename=str(rro_output_file))
        print(f"RRO 族已保存至: {rro_output_file}")

    # =============================================================================
    # 6. 输出总结
    # =============================================================================
    print("\n" + "=" * 60)
    print("RRO 族生成完成！")
    print("=" * 60)
    if bifurcation_points:
        print(f"检测到 {len(bifurcation_points)} 个分岔点")
    if family_rro is not None:
        print(f"RRO 族: {len(family_rro)} 条轨道")


if __name__ == "__main__":
    main()
