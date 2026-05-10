"""
生成 Halo 轨道

Halo 轨道是 CR3BP（圆形受限三体问题）下围绕共线拉格朗日点（L1/L2）的
三维周期轨道，关于 XZ 平面对称。轨道按 Z 方向偏置方向分为：
    - Class I (北 Halo): z 振幅为正
    - Class II (南 Halo): z 振幅为负

求解流程：
    1) 用 Richardson 三阶解析近似生成初始猜测，或使用已知的参考值；
    2) 利用 Halo 轨道关于 XZ 平面的对称性，仅积分半周期；
    3) 通过 scipy.optimize.least_squares 求解自由变量 (x0, vy0, T/2)，
       使半周期末端状态满足垂直穿越 XZ 平面的约束 (y=0, vx=0, vz=0)。

参考文献:
    Richardson, D. L. (1980). Analytic construction of periodic orbits
    about the collinear points. Celestial Mechanics, 22(3), 303-320.
"""

import argparse
import sys
from pathlib import Path

import time

import numpy as np
from scipy import integrate as sci_integrate
from scipy.optimize import least_squares

# 解析项目根目录（仓库顶层）：本文件位于 tod/generates/cr3bp/halo/，
# 向上 5 层即仓库根，用于定位与 e2m2e 共享的 output/ 目录。
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

import e2m2e
from e2m2e.core import Orbit

# MU: 地月系质量比（无量纲，μ ≈ 1.21506683e-2）
# TU: 时间单位（无量纲 → 物理天数的换算系数）
from tod.commons.common import MU, TU

OUTPUT_DIR = project_root / "output" / "halo"

# L1 北 Halo 参考解：来自数值搜索 (least_squares) 的精确解。
# x0, vy0 对应 z=0.23 附近的轨道参数，可作为相近振幅的初始猜测。
_L1_NORTH_REF = {"x0": 0.930528, "vy0": 0.104313, "T_half": 1.839729}


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


def _halo_residuals(vars, dynamics, z0):
    """Halo 轨道半周期约束残差：[y(T/2), vx(T/2), vz(T/2)] → 0"""
    x0, vy0, t_half = vars
    state = [x0, 0.0, z0, 0.0, vy0, 0.0]
    res = sci_integrate.solve_ivp(
        dynamics.equations_of_motion, (0, t_half), state,
        method="DOP853", t_eval=[t_half], rtol=1e-12, atol=1e-12,
    )
    final = res.y[:, -1]
    return np.array([final[1], final[3], final[5]])


def _solve_halo(dynamics, z0, x0_guess, vy0_guess, t_half_guess, tol=1e-10):
    """用 scipy.optimize.least_squares 求解 Halo 轨道

    自由变量 (x0, vy0, T/2)，约束 y(T/2)=vx(T/2)=vz(T/2)=0。

    Args:
        dynamics: CR3BP 动力学对象
        z0: 固定的初始 z 坐标
        x0_guess, vy0_guess, t_half_guess: 初始猜测

    Returns:
        (x0, vy0, t_half) 或 None
    """
    result = least_squares(
        lambda v: _halo_residuals(v, dynamics, z0),
        [x0_guess, vy0_guess, t_half_guess],
        bounds=([-2.0, -5.0, 0.3], [2.0, 5.0, 5.0]),
        ftol=tol, xtol=tol, gtol=tol,
        max_nfev=500,
    )
    if result.cost > 1e-10:
        return None
    return tuple(result.x)


def _propagate_full_orbit(dynamics, x0, z0, vy0, t_half, n_points=1000):
    """传播完整周期轨道并构造 Orbit 对象"""
    T = 2 * t_half
    state0 = [x0, 0.0, z0, 0.0, vy0, 0.0]
    res = sci_integrate.solve_ivp(
        dynamics.equations_of_motion, (0, T), state0,
        method="DOP853", rtol=1e-12, atol=1e-12,
        t_eval=np.linspace(0, T, n_points),
    )
    orbit = Orbit(states=res.y.T.tolist(), times=res.t.tolist())
    orbit.period = T
    return orbit


def richardson_initial_guess(mu, z_amplitude, libration_point, halo_class):
    """用 Richardson 三阶近似生成 Halo 轨道初始猜测

    调用 e2m2e 的 halo_third_order_approximation 生成完整近似轨道，
    然后从中提取 z 达到最大偏移处的 (x0, vy0, T)，作为微分修正的种子。

    Args:
        mu: 质量比 μ = m₂/(m₁+m₂)
        z_amplitude: 目标 Z 方向振幅（无量纲）
        libration_point: 拉格朗日点编号 (1=L1, 2=L2)
        halo_class: 0=北 Halo (Class I), 1=南 Halo (Class II)

    Returns:
        dict: 包含 x0, z0, vy0, period 的初始猜测参数
    """
    Aw = z_amplitude
    Au = np.sqrt(z_amplitude) * 0.5

    coeffs = e2m2e.algorithms.compute_halo_coefficients(mu, libration_point)

    omega_p = coeffs["omega_p"]
    kappa1 = coeffs["kappa1"]
    kappa2 = coeffs["kappa2"]
    freq_correction = kappa1 * Au**2 + kappa2 * Aw**2
    T_richardson = 2 * np.pi / (omega_p + freq_correction)
    T_linear = 2 * np.pi / omega_p
    T_est = T_linear if abs(freq_correction) > 0.5 * omega_p else T_richardson

    SV_xyz, _, T = e2m2e.algorithms.halo_third_order_approximation(
        mu=mu, Au=Au, Aw=Aw, phi=0.0, L=libration_point,
        tf=T_est, N=500, halo_class=halo_class,
    )

    z_col = SV_xyz[:, 2]
    idx_z_max = np.argmax(np.abs(z_col))

    x0 = float(SV_xyz[idx_z_max, 0])
    vy0 = float(SV_xyz[idx_z_max, 4])

    z0 = z_amplitude if halo_class == 0 else -z_amplitude
    period = T_linear if abs(freq_correction) > 0.5 * omega_p else T

    return {
        "x0": x0,
        "z0": z0,
        "vy0": vy0,
        "period": period,
    }


def _get_initial_guess(mu, amplitude_z, libration_point, halo_class):
    """获取最优初始猜测

    对于 L1 北 Halo，使用已知参考解作为猜测（比 Richardson 更可靠）。
    对于 L2，使用平动点位置 + 线性化速度估计。
    其他情况使用 Richardson 三阶近似。
    """
    if libration_point == 1 and halo_class == 0:
        return {
            "x0": _L1_NORTH_REF["x0"],
            "z0": amplitude_z,
            "vy0": _L1_NORTH_REF["vy0"],
            "period": 2 * _L1_NORTH_REF["T_half"],
            "ref_z": 0.23,
        }

    # L2: Richardson 完全失效，用平动点位置 + 线性化估计
    if libration_point == 2:
        coeffs = e2m2e.algorithms.compute_halo_coefficients(mu, libration_point)
        gamma = coeffs["gamma"]
        omega_p = coeffs["omega_p"]
        k = coeffs["k"]
        delta = coeffs["delta"]
        if halo_class == 1:
            delta = -delta
        L_position = 1 - mu - gamma  # L2: gamma < 0, so L_position > 1-mu
        Au = np.sqrt(amplitude_z) * 0.5
        return {
            "x0": L_position,
            "z0": amplitude_z if halo_class == 0 else -amplitude_z,
            "vy0": k * Au * omega_p,
            "period": 2 * np.pi / omega_p,
            "ref_z": None,
        }

    guess = richardson_initial_guess(mu, amplitude_z, libration_point, halo_class)
    guess["ref_z"] = None
    return guess


def main():
    args = parse_args()

    # =============================================================================
    # 1. 系统与动力学模型初始化
    # =============================================================================
    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

    # =============================================================================
    # 2. Halo轨道参数
    # =============================================================================
    LIBRATION_POINT_MAP = {"L1": 1, "L2": 2}
    libration_point = LIBRATION_POINT_MAP[args.libration_point]
    amplitude_z = args.amplitude_z
    halo_class = args.halo_class
    z0 = amplitude_z if halo_class == 0 else -amplitude_z

    print(f"目标轨道: L{libration_point} {'北' if halo_class == 0 else '南'} Halo")
    print(f"Z振幅: {amplitude_z}")

    # =============================================================================
    # 3. 获取初始猜测
    # =============================================================================
    guess = _get_initial_guess(MU, amplitude_z, libration_point, halo_class)
    x0 = guess["x0"]
    vy0 = guess["vy0"]
    t_half = guess["period"] / 2

    print(f"\n初始猜测:")
    print(f"  x0 = {x0:.10f}")
    print(f"  z0 = {z0}")
    print(f"  vy0 = {vy0:.10f}")
    print(f"  半周期 = {t_half:.6f} TU ({t_half * TU:.2f} days)")

    # =============================================================================
    # 4. 用 scipy.optimize 求解
    # =============================================================================
    # 对于 L1 北 Halo，先尝试直接求解，若失败则从参考振幅延拓。
    # 其他情况使用 Richardson 猜测直接求解。
    print("\n开始求解...")
    sol = _solve_halo(dynamics, z0, x0, vy0, t_half, tol=args.tolerance)

    ref_z = guess.get("ref_z")
    if sol is None and ref_z is not None and abs(amplitude_z - ref_z) > 0.01:
        print(f"直接求解失败，尝试从参考振幅 z={ref_z} 延拓...")
        # 先求参考振幅处的精确解
        z_sign = 1 if halo_class == 0 else -1
        ref_z0 = z_sign * ref_z
        ref_sol = _solve_halo(
            dynamics, ref_z0,
            _L1_NORTH_REF["x0"], _L1_NORTH_REF["vy0"], _L1_NORTH_REF["T_half"],
            tol=args.tolerance,
        )
        if ref_sol is not None:
            # 从参考振幅逐步延拓到目标振幅
            current_z = ref_z
            current_sol = ref_sol
            step = 0.02
            direction = np.sign(amplitude_z - ref_z)
            while abs(current_z - amplitude_z) > 1e-10:
                next_z = current_z + direction * min(step, abs(amplitude_z - current_z))
                next_z0 = z_sign * next_z
                next_sol = _solve_halo(
                    dynamics, next_z0,
                    current_sol[0], current_sol[1], current_sol[2],
                    tol=args.tolerance,
                )
                if next_sol is None:
                    step /= 2
                    if step < 1e-5:
                        break
                    continue
                current_z = next_z
                current_sol = next_sol
                print(f"  延拓: z={next_z:.4f}, T/2={current_sol[2]:.6f}")
            if abs(current_z - amplitude_z) < 1e-10:
                sol = current_sol

    if sol is None:
        print("\n[error] 求解失败: least_squares 未收敛")
        return

    x0_sol, vy0_sol, t_half_sol = sol
    residual = np.linalg.norm(_halo_residuals(sol, dynamics, z0))
    print("\n[ok] 成功找到 Halo 轨道!")
    print(f"  x0 = {x0_sol:.10f}")
    print(f"  vy0 = {vy0_sol:.10f}")
    print(f"  半周期 = {t_half_sol:.10f} TU ({t_half_sol * TU:.4f} days)")
    print(f"  约束残差 = {residual:.2e}")

    # =============================================================================
    # 5. 传播完整轨道并保存
    # =============================================================================
    orbit_result = _propagate_full_orbit(dynamics, x0_sol, z0, vy0_sol, t_half_sol)

    ts = int(time.time())
    output_file = (
        OUTPUT_DIR
        / f"halo_L{libration_point}_{'N' if halo_class == 0 else 'S'}_{amplitude_z}_{ts}.json"
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    orbit_result.save_to_file(filename=str(output_file))
    print(f"  保存至: {output_file}") if output_file else None


if __name__ == "__main__":
    # IDE 调试模式：F5 直跑（无命令行参数）时注入下列参数；
    # 命令行调用 `python -m tod.generates.cr3bp.halo.generate_halo_orbit ...` 时不受影响。
    if len(sys.argv) == 1:
        sys.argv += [
            "--libration-point", "L1",                  # 共线拉格朗日点：L1 / L2
            "--amplitude-z", "0.23",                    # z 方向振幅（无量纲），决定轨道"大小"
            "--halo-class", "1",                        # 0=北 Halo（z0>0）/ 1=南 Halo（z0<0）
            "--max-iterations", "150",                  # 最大迭代次数
            "--tolerance", "1e-6",                      # 收敛容差
        ]
        print("[debug] 使用代码内置调试参数")
    main()
