"""
生成 Halo 轨道

Halo 轨道是 CR3BP（圆形受限三体问题）下围绕共线拉格朗日点（L1/L2）的
三维周期轨道，关于 XZ 平面对称。轨道按 Z 方向偏置方向分为：
    - Class I (北 Halo): z 振幅为正
    - Class II (南 Halo): z 振幅为负

求解流程：
    1) 用 Richardson 三阶解析近似 (halo_third_order_approximation) 生成
       完整近似轨道，从中提取 z=z_max 处的 (x0, vy0, T) 作为初始猜测；
    2) 利用 Halo 轨道关于 XZ 平面的对称性，仅积分半周期；
    3) 通过微分修正在自由变量 (x0, vy0) 上迭代收敛，使半周期末端
       状态满足垂直穿越 XZ 平面的约束 (y=0, vx=0, vz=0)。

参考文献:
    Richardson, D. L. (1980). Analytic construction of periodic orbits
    about the collinear points. Celestial Mechanics, 22(3), 303-320.
"""

import argparse
import sys
from pathlib import Path

import time

import numpy as np

# 解析项目根目录（仓库顶层）：本文件位于 tod/pipelines/halo/generate/，
# 向上 5 层即仓库根，用于定位与 e2m2e 共享的 output/ 目录。
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

import e2m2e
from e2m2e.core import Orbit

# MU: 地月系质量比（无量纲，μ ≈ 1.21506683e-2）
# TU: 时间单位（无量纲 → 物理天数的换算系数）
from tod.commons.common import MU, TU

OUTPUT_DIR = project_root / "output" / "halo"


def parse_args():
    parser = argparse.ArgumentParser(description="生成 Halo 轨道（Richardson 三阶近似 + 微分修正）")
    parser.add_argument("--libration-point", type=str, default="L1", choices=["L1", "L2"],
                        help="平动点：L1, L2")
    parser.add_argument("--amplitude-z", type=float, default=0.23,
                        help="Z 方向振幅（无量纲）")
    parser.add_argument("--halo-class", type=int, default=0,
                        help="0=北 Halo (Class I), 1=南 Halo (Class II)")
    parser.add_argument("--max-iterations", type=int, default=150, help="最大迭代次数")
    parser.add_argument("--tolerance", type=float, default=1e-6, help="修正容差")
    return parser.parse_args()


def richardson_initial_guess(mu, z_amplitude, libration_point, halo_class):
    """用 Richardson 三阶近似生成 Halo 轨道初始猜测

    调用 e2m2e 的 halo_third_order_approximation 生成完整近似轨道，
    然后从中提取 z 达到最大偏移处的 (x0, vy0, T)，作为微分修正的种子。

    Richardson 三阶近似将 CR3BP 运动方程在共线平动点附近展开为三阶
    非线性扰动级数。位移分解为面内 (u-v) 和面外 (w) 分量，
    用包含基频 ω_p 各阶谐波的 Fourier 级数表示：

        u(τ) = a₂₁·Au² + a₂₂·Aw² − Au·cos(τ) + (a₂₃·Au²−a₂₄·Aw²)·cos(2τ)
               + a₃₁·Au³·cos(3τ)

        v(τ) = k·Au·sin(τ) + (b₂₁·Au²−b₂₂·Aw²)·sin(2τ) + b₃₁·Au³·sin(3τ)

        w(τ) = δ·[Aw·sin(τ) + d₂₁·Au·Aw·sin(2τ) + (d₃₂·Aw·Au²−d₃₁·Aw³)·sin(3τ)]

    其中 τ = (ω_p + κ₁·Au² + κ₂·Aw²)·t 为频率修正后的相位角，
    Au 为面内振幅参数，Aw 为面外振幅参数。
    各系数 a_ij, b_ij, d_ij 由拉格朗日点位置和质量比 μ 唯一确定。

    该解析解虽不精确（误差随振幅增大而增长），但作为微分修正器的
    初始猜测已足够好——修正器通常在 5-15 次迭代内即可收敛。

    Args:
        mu: 质量比 μ = m₂/(m₁+m₂)
        z_amplitude: 目标 Z 方向振幅（无量纲）
        libration_point: 拉格朗日点编号 (1=L1, 2=L2)
        halo_class: 0=北 Halo (Class I), 1=南 Halo (Class II)

    Returns:
        dict: 包含 x0, z0, vy0, period 的初始猜测参数
    """
    # ── 振幅参数 ──────────────────────────────────────────────────────────
    # Richardson 公式需要面内振幅 Au 和面外振幅 Aw 两个独立参数。
    # Aw ≈ z_amplitude：面外分量直接对应 z 方向的最大偏移。
    # Au 由非线性耦合关系近似为 √z_amplitude × 0.5，这是 Richardson
    # 理论中面内/面外振幅耦合关系的零阶估计。
    # 这些值不需要精确——微分修正器会在后续步骤中精化 x0 和 vy0。
    Aw = z_amplitude
    Au = np.sqrt(z_amplitude) * 0.5

    # ── 计算 Richardson 系数 ──────────────────────────────────────────────
    # 通过 compute_halo_coefficients 求解平动点附近势函数展开的全部系数：
    #   γ    — 次天体到平动点的距离（L1: γ>0, L2: γ<0）
    #   ω_p  — 面内振荡基频
    #   c₁,c₂,c₃ — Legendre 展开系数（有效势前三阶）
    #   a₂₁~a₃₁, b₂₁~b₃₁, d₂₁~d₃₂ — 各方向谐波振幅修正系数
    #   k, δ — 符号因子（决定轨道方向和南北类别）
    #   κ₁, κ₂ — 频率修正系数（三阶非线性导致的频率偏移）
    coeffs = e2m2e.algorithms.compute_halo_coefficients(mu, libration_point)

    # ── 估计周期 ──────────────────────────────────────────────────────────
    # Richardson 三阶近似的修正频率：ω = ω_p + κ₁·Au² + κ₂·Aw²
    # κ₁·Au² + κ₂·Aw² 项反映非线性耦合对线性频率的修正。
    # 周期 T = 2π/ω，此估计值将作为积分时间跨度和修正器的周期初值。
    omega_p = coeffs["omega_p"]
    kappa1 = coeffs["kappa1"]
    kappa2 = coeffs["kappa2"]
    T_est = 2 * np.pi / (omega_p + kappa1 * Au**2 + kappa2 * Aw**2)

    # ── 生成完整近似轨道 ─────────────────────────────────────────────────
    # phi=0 为标准初始相位，N=500 提供足够的时间分辨率以精确定位 z 极值点。
    # 返回的 SV_uvw 实际已从 (u,v,w) 坐标转换为旋转系 (x,y,z) 坐标
    # （平动点位置已加回：x = L_position + u）。
    SV_xyz, t, T = e2m2e.algorithms.halo_third_order_approximation(
        mu=mu,
        Au=Au,
        Aw=Aw,
        phi=0.0,
        L=libration_point,
        tf=T_est,
        N=500,
        halo_class=halo_class,
    )

    # ── 提取 z=z_max 处的初始状态 ────────────────────────────────────────
    # 近似轨道中 |z| 达到最大值的点对应 Halo 轨道的"极点"（最大 z 偏移处），
    # 北 Halo 此处 z>0，南 Halo 此处 z<0。
    # 该点的 x 和 vy 即为微分修正器所需的自由变量初始值。
    z_col = SV_xyz[:, 2]
    idx_z_max = np.argmax(np.abs(z_col))

    x0 = float(SV_xyz[idx_z_max, 0])
    vy0 = float(SV_xyz[idx_z_max, 4])

    # z0 取用户指定的目标振幅（而非 Richardson 近似值），因为
    # corrector.setup_halo_orbit_fixed_z0 将固定 z0 作为约束条件。
    z0 = z_amplitude if halo_class == 0 else -z_amplitude

    return {
        "x0": x0,
        "z0": z0,
        "vy0": vy0,
        "period": T,
    }


def main():
    args = parse_args()

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    # CR3BP（圆形受限三体问题）：在地月质心同步旋转坐标系下建模，状态量
    # 已用 DU/TU 无量纲化，方程仅依赖单一参数 μ = m_moon / (m_earth + m_moon)。
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. Halo轨道参数
    # =============================================================================
    # Halo轨道特征：关于XZ平面对称，在拉格朗日点(L1/L2)附近振荡
    # 状态向量格式：[x, y, z, vx, vy, vz]，均为无量纲量
    LIBRATION_POINT_MAP = {"L1": 1, "L2": 2}
    libration_point = LIBRATION_POINT_MAP[args.libration_point]
    amplitude_z = args.amplitude_z
    halo_class = args.halo_class

    print(f"目标轨道: L{libration_point} {'北' if halo_class == 0 else '南'} Halo")
    print(f"Z振幅: {amplitude_z}")

    # =============================================================================
    # 3. Richardson 三阶近似生成初始猜测
    # =============================================================================
    # Richardson (1980) 在共线平动点附近将 CR3BP 运动方程展开至三阶，
    # 得到封闭形式的解析周期解。该解将轨道位移分解为面内 (x-y) 和
    # 面外 (z) 两个耦合振荡，用 Fourier 谐波级数表示，系数由平动点位置
    # 和质量比唯一确定。
    #
    # 三阶近似比线性化 (Lindstedt-Poincaré 一阶) 显著更精确：
    # 它捕捉了面内/面外的非线性耦合、频率的振幅依赖性 (κ₁, κ₂ 修正)、
    # 以及二次和三次谐波对轨道形状的影响。
    #
    # 但它仍不精确——特别是对较大振幅（Az > 0.3）误差明显。
    # 因此这里仅用它生成初始猜测，后续交由微分修正器迭代精化。
    guess = richardson_initial_guess(
        mu=MU,
        z_amplitude=amplitude_z,
        libration_point=libration_point,
        halo_class=halo_class,
    )

    x0 = guess["x0"]
    z0 = guess["z0"]
    vy0 = guess["vy0"]
    target_period = guess["period"]
    t_half = target_period / 2

    print(f"\nRichardson 三阶近似初始猜测:")
    print(f"  x0 = {x0:.10f}")
    print(f"  z0 = {z0}")
    print(f"  vy0 = {vy0:.10f}")
    print(f"  预估周期 T = {target_period:.6f} TU ({target_period * TU:.2f} days)")
    print(f"  半周期 = {t_half:.6f} TU")

    # =============================================================================
    # 4. 配置微分校正器
    # =============================================================================
    # setup_halo_orbit_fixed_z0：固定 z0，自由变量为 (x0, vy0)。
    # 选择固定 z0 是因为它直接刻画了轨道的"大小"（z 振幅），
    # 留 (x0, vy0) 作为自由量更利于沿族延拓时单调推进。
    # 北 Halo 取 z0>0，南 Halo 取 z0<0。
    corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
    corrector.setup_halo_orbit_fixed_z0(z0=z0, libration_point=libration_point)

    print(f"\n微分校正器配置:")
    print(f"  模式: setup_halo_orbit_fixed_z0")
    print(f"  固定参数: z0 = {z0}")
    print(f"  自由变量: {corrector.free_variables}")
    print(f"  约束条件: {list(corrector.target_conditions.keys())}")

    # =============================================================================
    # 5. 构造初始轨道对象并执行修正
    # =============================================================================
    # 初始状态形如 [x0, 0, z0, 0, vy0, 0]：垂直穿越 XZ 平面的对称约束要求
    # y = vx = vz = 0；只剩 x0、z0、vy0 三个自由量参与求解。
    initial_state = [x0, 0.0, z0, 0.0, vy0, 0.0]

    orbit_init = Orbit(states=[initial_state], times=[0])
    orbit_init.period = target_period

    corrector.max_iterations = args.max_iterations
    corrector.tolerance = args.tolerance

    # 迭代收敛后返回的 Orbit 对象已含完整周期内的状态序列；若发散则返回 None。
    print(f"\n开始迭代修正...")
    orbit_result = corrector.iterate_correction(initial_guess=orbit_init, verbose=True)

    # =============================================================================
    # 6. 保存结果
    # =============================================================================
    if orbit_result is not None:
        print(f"\n[ok] 成功找到 Halo 轨道!")
        print(f"  修正后周期: {orbit_result.period:.6f} TU")
        print(f"  初始状态: {orbit_result.states[0].tolist()}")

        # 文件名编码：拉格朗日点 + N/S(北/南) + Z 振幅 + Unix 时间戳，
        # 便于在 family 生成与可视化阶段按文件名筛选轨道。
        ts = int(time.time())
        output_file = (
            OUTPUT_DIR
            / f"halo_L{libration_point}_{'N' if halo_class == 0 else 'S'}_{amplitude_z}_{ts}.json"
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        orbit_result.save_to_file(filename=str(output_file))
        print(f"  保存至: {output_file}")
    else:
        print(f"\n[error] 修正失败: {corrector.termination_reason}")


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用 `python -m tod.pipelines.halo.generate.generate_halo_orbit ...` 时不受影响。
    # Richardson 公式会自动计算 x0、vy0、period，调试时只需指定振幅和平动点。
    if len(sys.argv) == 1:
        sys.argv += [
            "--libration-point", "L1",                  # 共线拉格朗日点：L1 / L2
            "--amplitude-z", "0.23",                    # z 方向振幅（无量纲），决定轨道"大小"
            "--halo-class", "0",                        # 0=北 Halo（z0>0）/ 1=南 Halo（z0<0）
            "--max-iterations", "150",                  # 微分修正最大迭代次数（发散保护）
            "--tolerance", "1e-6",                      # 微分修正收敛容差（约束残差范数阈值）
        ]
        print("[debug] 使用代码内置调试参数")
    main()
