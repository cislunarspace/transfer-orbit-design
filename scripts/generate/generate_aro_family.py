"""
生成 3:2 ARO（轴向共振轨道）族

本脚本实现：
1. 加载已有的 3:2 RO 族数据
2. 检测单值矩阵特征值分岔点（λ ≈ 1）
3. 从分岔点出发，生成 ARO（轴向共振轨道）族（固定 z0，改变 x0）

技术背景：
- 论文 Section II.D: "当单值矩阵的一对特征值在实轴 +1 处碰撞时，发生切分岔，
  伴随 3D 轨道的生成"
- ARO 特征：关于 x 轴对称，类似于 LPO 中的轴向轨道

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

import sys
from pathlib import Path

# 将项目根目录添加到 sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import e2m2e
from fontTools.misc.timeTools import timestampNow
from scripts.utils.common import MU, TU

OUTPUT_DIR = project_root / "output"
RO_32_FAMILY_FILE = OUTPUT_DIR / "ro" / "ro_32_family_-1.2--0.8-0.005_3856904629.json"

# ARO 目标 x0（来自论文 Table 2）
TARGET_X0_ARO = -1.1318
Z0_ARO = 0.1999  # 固定 z0

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
family_32 = e2m2e.core.orbit.OrbitFamily.load_from_file(str(RO_32_FAMILY_FILE))
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

            for lam in analysis.eigenvalues:
                diff = abs(lam - 1.0)
                if diff < min_diff:
                    min_diff = diff
                    best_orbit_idx = i
                    best_eigenvalues = analysis.eigenvalues
        except Exception:
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
if bifurcation_points:
    print("\n" + "=" * 60)
    print(f"搜索接近 x0={TARGET_X0_ARO} 的分岔点（ARO种子）...")

    aro_bp = e2m2e.algorithms.StabilityAnalysis.find_nearest_bifurcation(
        orbits=family_32.orbits,
        dynamics=dynamics,
        target_x0=TARGET_X0_ARO,
        tolerance=0.1,
    )

    if aro_bp:
        print(
            f"找到 ARO 分岔点: 索引={aro_bp['orbit_index']}, "
            f"x0={aro_bp['orbit'].states[0][0]:.4f}, "
            f"z0={aro_bp['orbit'].states[0][2]:.4f}"
        )
    else:
        print("未找到 ARO 分岔点，使用搜索到的第一个分岔点")
        aro_bp = bifurcation_points[0] if bifurcation_points else None

# =============================================================================
# 5. 从分岔点生成 ARO 族（固定 z0，改变 x0）
# =============================================================================
print("\n" + "=" * 60)
print("从分岔点生成 ARO 族...")

# ARO 的种子来自论文 Table 2: x=-1.1318, z=0.1999
z0_aro = Z0_ARO  # 固定 z0

# 配置 3D XZ 对称修正器（固定 z0）
corrector_aro = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
corrector_aro.setup_3D_symmetric_xz_fixed_z0(z0=z0_aro)

# ARO 种子状态
if aro_bp:
    x0_aro = aro_bp["orbit"].states[0][0]
else:
    x0_aro = TARGET_X0_ARO

y_dot0_aro = 0.4  # 初始猜测
seed_state_aro = [x0_aro, 0.0, z0_aro, 0.0, y_dot0_aro, 0.0]
seed_orbit_aro = e2m2e.core.orbit.Orbit(states=[seed_state_aro], times=[0])
seed_orbit_aro.period = 60.0 / TU  # 初始周期猜测

# 先修正种子轨道
try:
    seed_orbit_aro = corrector_aro.iterate_correction(
        initial_guess=seed_orbit_aro,
        verbose=False,
    )
    print(
        f"ARO 种子轨道修正成功: x0={seed_orbit_aro.states[0][0]:.4f}, "
        f"z0={seed_orbit_aro.states[0][2]:.4f}, "
        f"周期={seed_orbit_aro.period * TU:.2f}天"
    )
except Exception as e:
    print(f"ARO 种子轨道修正失败: {e}")
    print("使用默认种子继续...")

# 延拓参数：x0 范围
x_min = -1.2
x_max = -0.9

# 自然延拓生成 ARO 族
continuator_aro = e2m2e.algorithms.Continuation(corrector=corrector_aro)
family_aro = continuator_aro.natural_continuation(
    seed_orbit=seed_orbit_aro,
    param_range=(x_min, x_max),
    step_size=0.005,
    verbose=False,
)

print(f"ARO 族延拓完成，共 {len(family_aro)} 条轨道")

# 保存 ARO 族
aro_output_file = OUTPUT_DIR / "ro" / f"aro_32_family_{timestampNow()}.json"
family_aro.save_to_file(filename=str(aro_output_file))
print(f"ARO 族已保存至: {aro_output_file}")

# =============================================================================
# 6. 输出总结
# =============================================================================
print("\n" + "=" * 60)
print("ARO 族生成完成！")
print("=" * 60)
if bifurcation_points:
    print(f"检测到 {len(bifurcation_points)} 个分岔点")
if "family_aro" in dir():
    print(f"ARO 族: {len(family_aro)} 条轨道")
