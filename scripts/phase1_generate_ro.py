"""
阶段一：基线轨道生成 — 共振轨道族 (RO)

生成3:2和3:1平面共振轨道族 (Resonant Orbits)，计算Jacobi常数与稳定性指标。

共振轨道命名约定：
  p:q表示航天器绕地球p圈，月球绕地球q圈
  旋转坐标系周期: T = 2πq（轨道在q个月球轨道周期后闭合）
  惯性系周期（Kepler周期）: T_k = 2πq/p
  Kepler半长轴: a = ((1-μ)(q/p)^2)^(1/3)

目标RO：
  3:2 RO: T = 4π ≈ 12.566 (航天器3圈/月球2圈)
  3:1 RO: T = 2π ≈  6.283 (航天器3圈/月球1圈)

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import json

import e2m2e
from e2m2e import CR3BP_System, CR3BP_Dynamics, DifferentialCorrection, Continuation
from e2m2e.algorithms.continuation import ContinuationDirection

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
MU = 1.21506683e-2
DU = 3.84405e5  # km
TU = 4.34811305  # days
VU = 1023.23281  # m/s

T_MOON = 2 * np.pi  # 月球恒星周期(无量纲)

# 目标共振轨道周期
T_RO_32 = 2 * T_MOON  # 4π ≈ 12.566
T_RO_31 = 1 * T_MOON  # 2π ≈  6.283


# ============================================================
# 辅助函数
# ============================================================
def create_system():
    """创建地月CR3BP系统"""
    system = CR3BP_System(mu=MU, primary="Earth", secondary="Moon")
    system.set_characteristic_scales(distance=DU * 1e3, period=TU * 86400)
    system.compute_libration_points()
    return system


def keplerian_circular_estimate(p, q, mu):
    """p:q共振轨道的Kepler圆轨道估计

    返回旋转系中在x轴上(地球-月球连线，地球右侧)的初始状态。

    参数:
        p, q: 共振比 p:q
        mu: 质量比

    返回:
        x0, vy0, a: 初始x坐标、y方向速度、半长轴
    """
    # Kepler半长轴
    a = ((1 - mu) * (q / p) ** 2) ** (1.0 / 3)
    # 初始位置: 地球右侧 (x轴上)
    r = a  # 圆轨道，距离=半长轴
    x0 = -mu + r
    # 旋转系速度: v_inertial - ω×r
    # 在(x0, 0)处: v_inertial = sqrt((1-μ)/r) (向上), ω×r = (0, x0)
    vy0 = np.sqrt((1 - mu) / r) - x0
    return x0, vy0, a


def keplerian_eccentric_estimate(p, q, mu, e, at_periapsis=True):
    """p:q共振轨道在指定偏心率下的Kepler估计

    参数:
        p, q: 共振比
        mu: 质量比
        e: 偏心率
        at_periapsis: True=在近地点出发, False=在远地点出发

    返回:
        x0, vy0
    """
    a = ((1 - mu) * (q / p) ** 2) ** (1.0 / 3)

    if at_periapsis:
        r = a * (1 - e)
        v = np.sqrt((1 - mu) * (2 / r - 1 / a))
    else:
        r = a * (1 + e)
        v = np.sqrt((1 - mu) * (2 / r - 1 / a))

    x0 = -mu + r
    vy0 = v - x0  # 顺行，+y方向
    return x0, vy0


def find_y_crossings(dynamics, state, t_max, max_crossings=20):
    """找到所有y=0穿越（用于确定半周期）

    返回穿越点列表，每个包含时间、状态、|vx|。
    """
    from scipy.integrate import solve_ivp

    crossings = []

    def y_zero(t, s):
        return s[1]

    y_zero.terminal = False
    y_zero.direction = 0

    # 先走一小步避免初始y=0被检测
    res0 = solve_ivp(
        dynamics.equations_of_motion,
        (0, 0.005),
        state,
        method="DOP853",
        rtol=1e-12,
        atol=1e-12,
    )
    s0 = res0.y[:, -1]

    res = solve_ivp(
        dynamics.equations_of_motion,
        (0.005, t_max),
        s0,
        method="DOP853",
        rtol=1e-12,
        atol=1e-12,
        events=y_zero,
    )

    if res.t_events[0].size > 0:
        for t_c, s_c in zip(res.t_events[0], res.y_events[0]):
            crossings.append(
                {
                    "time": t_c,
                    "state": s_c,
                    "vx": abs(s_c[3]),
                    "x": s_c[0],
                }
            )
            if len(crossings) >= max_crossings:
                break

    return crossings


def correct_ro_fixed_t(dynamics, x0_guess, vy0_guess, t_half, verbose=True):
    """使用固定半周期的微分修正找到RO"""
    dc = DifferentialCorrection(dynamics)
    dc.setup_2D_symmetric_x_fixed_t(t_half=t_half)
    dc.tolerance = 1e-12
    dc.max_iterations = 60

    state = np.array([x0_guess, 0.0, 0.0, 0.0, vy0_guess, 0.0])
    orbit, result = dc.correct_orbit(state, t_half, verbose=verbose)
    return orbit, result


def correct_ro_fixed_x0(dynamics, x0, vy0_guess, t_half_guess, verbose=True):
    """使用固定x0的微分修正找到RO"""
    dc = DifferentialCorrection(dynamics)
    dc.setup_2D_symmetric_x_fixed_x0(x0=x0)
    dc.tolerance = 1e-12
    dc.max_iterations = 60

    state = np.array([x0, 0.0, 0.0, 0.0, vy0_guess, 0.0])
    orbit, result = dc.correct_orbit(state, t_half_guess, verbose=verbose)
    return orbit, result


def find_ro_seed(dynamics, p, q, verbose=True):
    """寻找p:q共振轨道的种子

    策略：
    1. 尝试Kepler圆轨道估计 + 固定周期修正
    2. 遍历不同偏心率的Kepler估计
    3. 使用事件检测 + 固定x0修正

    返回:
        orbit, result (或 None, None)
    """
    T_target = 2 * np.pi * q
    t_half_target = T_target / 2
    x0_circ, vy0_circ, a = keplerian_circular_estimate(p, q, MU)

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"{p}:{q} RO 种子搜索")
        print(f"{'=' * 60}")
        print(f"  Kepler半长轴: a = {a:.6f} DU ({a * DU:.0f} km)")
        print(f"  目标周期: T = {T_target:.6f} (T/2 = {t_half_target:.6f})")
        print(f"  圆轨道估计: x0 = {x0_circ:.6f}, vy0 = {vy0_circ:.6f}")

    # ---- 方法1: 圆轨道估计 + 固定T修正 ----
    if verbose:
        print(f"\n  方法1: 圆轨道估计 + 固定T修正")
    orbit, result = correct_ro_fixed_t(
        dynamics, x0_circ, vy0_circ, t_half_target, verbose=verbose
    )
    if orbit is not None:
        # 验证是地球轨道（x0不能太大）
        x0_result = result["state"][0]
        if x0_result < 1 - MU - 0.1:
            if verbose:
                print(
                    f"  ✓ 方法1成功: x0={x0_result:.8f}, vy0={result['state'][4]:.8f}"
                )
            return orbit, result
        elif verbose:
            print(f"  方法1找到的轨道可能是月球附近轨道 (x0={x0_result:.4f})，跳过")
    elif verbose:
        print(f"  方法1失败")

    # ---- 方法2: 不同偏心率 + 固定T修正 ----
    if verbose:
        print(f"\n  方法2: 变偏心率 + 固定T修正")

    for e in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        for at_peri in [True, False]:
            try:
                x0_ecc, vy0_ecc = keplerian_eccentric_estimate(p, q, MU, e, at_peri)
            except (ValueError, ZeroDivisionError):
                continue

            # 检查物理合理性
            if x0_ecc < -MU + 0.01 or x0_ecc > 1 - MU - 0.05:
                continue
            if vy0_ecc < 0:  # RO应该是顺行
                continue

            orbit, result = correct_ro_fixed_t(
                dynamics, x0_ecc, vy0_ecc, t_half_target, verbose=False
            )
            if orbit is not None:
                x0_result = result["state"][0]
                if x0_result < 1 - MU - 0.1:
                    if verbose:
                        pos = "近地点" if at_peri else "远地点"
                        print(
                            f"  ✓ 方法2成功 (e={e:.1f}, {pos}): "
                            f"x0={x0_result:.8f}, vy0={result['state'][4]:.8f}"
                        )
                    return orbit, result

    if verbose:
        print(f"  方法2失败")

    # ---- 方法3: 事件检测 + 固定x0修正 ----
    if verbose:
        print(f"\n  方法3: 事件检测 + 固定x0修正")

    # 尝试不同x0值，积分检测y=0穿越并挑选近垂直穿越
    for x0_try in np.arange(0.2, 0.9, 0.05):
        r_try = x0_try + MU
        vy_try = np.sqrt((1 - MU) / r_try)  # 不减去x0，给较大的vy

        state_try = np.array([x0_try, 0, 0, 0, vy_try, 0])
        crossings = find_y_crossings(dynamics, state_try, t_max=t_half_target * 3)

        for c in crossings:
            if c["vx"] < 0.3 and c["time"] > 0.5:
                # 用这个穿越时间作为半周期估计，固定x0修正
                orbit, result = correct_ro_fixed_x0(
                    dynamics, x0_try, vy_try, c["time"], verbose=False
                )
                if orbit is not None:
                    T_found = result["period"]
                    if abs(T_found - T_target) / T_target < 0.1:
                        if verbose:
                            print(
                                f"  ✓ 方法3成功 (x0={x0_try:.2f}): "
                                f"x0={result['state'][0]:.8f}, "
                                f"vy0={result['state'][4]:.8f}, T={T_found:.6f}"
                            )
                        return orbit, result

    if verbose:
        print(f"  方法3失败")

    # ---- 方法4: 直接扫描x0和vy0的网格 ----
    if verbose:
        print(f"\n  方法4: 网格扫描")

    for x0_try in np.arange(0.1, 0.85, 0.02):
        r_try = x0_try + MU
        v_circ = np.sqrt((1 - MU) / r_try)
        for vy_factor in [0.3, 0.5, 0.7, 0.9, 1.0, 1.1]:
            vy_try = v_circ * vy_factor
            orbit, result = correct_ro_fixed_t(
                dynamics, x0_try, vy_try, t_half_target, verbose=False
            )
            if orbit is not None:
                x0_r = result["state"][0]
                if 0 < x0_r < 1 - MU - 0.1:
                    if verbose:
                        print(
                            f"  ✓ 方法4成功 (x0_g={x0_try:.2f}, vy_f={vy_factor:.1f}): "
                            f"x0={x0_r:.8f}, vy0={result['state'][4]:.8f}"
                        )
                    return orbit, result

    print(f"  ✗ 所有方法均失败，未找到 {p}:{q} RO 种子")
    return None, None


def generate_ro_family(dynamics, seed_result, n_outward=30, n_inward=20, verbose=True):
    """使用自然参数延拓生成RO族

    从种子RO出发，沿x0方向双向延拓。
    使用setup_2D_symmetric_x_fixed_x0，延拓参数为x0。
    """
    x0_seed = seed_result["state"][0]
    vy0_seed = seed_result["state"][4]
    t_half_seed = seed_result["t_half"]

    all_states = [seed_result["state"].copy()]
    all_periods = [seed_result["period"]]

    # ---- 向外延拓 (x0增大) ----
    if verbose:
        print(f"\n--- 外向延拓 (x0增大) ---")

    dc_out = DifferentialCorrection(dynamics)
    dc_out.setup_2D_symmetric_x_fixed_x0(x0=x0_seed)
    dc_out.tolerance = 1e-12
    dc_out.max_iterations = 60

    cont_out = Continuation(dc_out, param="x0", step=0.005)
    cont_out.direction = ContinuationDirection.FORWARD
    cont_out.max_step_size = 0.03
    cont_out.min_step_size = 1e-5

    result_out = cont_out.natural_continuation(
        seed_result["state"],
        t_half_seed,
        n_orbits=n_outward,
        param_index=0,
        verbose=verbose,
    )

    orbits_out = []
    if result_out is not None:
        for i in range(1, len(result_out["states"])):
            all_states.append(result_out["states"][i])
            all_periods.append(result_out["periods"][i])
            orbits_out.append(result_out["orbits"][i])

    # ---- 向内延拓 (x0减小) ----
    if verbose:
        print(f"\n--- 内向延拓 (x0减小) ---")

    dc_in = DifferentialCorrection(dynamics)
    dc_in.setup_2D_symmetric_x_fixed_x0(x0=x0_seed)
    dc_in.tolerance = 1e-12
    dc_in.max_iterations = 60

    cont_in = Continuation(dc_in, param="x0", step=0.005)
    cont_in.direction = ContinuationDirection.BACKWARD
    cont_in.max_step_size = 0.02
    cont_in.min_step_size = 1e-5

    result_in = cont_in.natural_continuation(
        seed_result["state"],
        t_half_seed,
        n_orbits=n_inward,
        param_index=0,
        verbose=verbose,
    )

    orbits_in = []
    if result_in is not None:
        for i in range(len(result_in["states"]) - 1, 0, -1):
            all_states.insert(0, result_in["states"][i])
            all_periods.insert(0, result_in["periods"][i])
            orbits_in.insert(0, result_in["orbits"][i])

    all_states = np.array(all_states)
    all_periods = np.array(all_periods)

    if verbose:
        print(f"\n总计生成 {len(all_periods)} 条RO")
        print(f"x0 范围: [{all_states[:, 0].min():.4f}, {all_states[:, 0].max():.4f}]")
        print(f"周期范围: [{all_periods.min():.4f}, {all_periods.max():.4f}]")

    return {
        "states": all_states,
        "periods": all_periods,
    }


def compute_jacobi_and_stability(family_data, dynamics, verbose=True):
    """计算RO族的Jacobi常数和稳定性指标"""
    states = family_data["states"]
    periods = family_data["periods"]

    jacobi_constants = []
    stability_indices = []

    if verbose:
        print(f"\n{'=' * 60}")
        print("计算Jacobi常数和稳定性")
        print(f"{'=' * 60}")

    for i, (state, period) in enumerate(zip(states, periods)):
        C = dynamics.system.get_jacobi_constant(state)
        jacobi_constants.append(C)

        try:
            stm = dynamics.compute_state_transition_matrix(state, period)
            eigenvalues = np.linalg.eigvals(stm)
            mags = np.sort(np.abs(eigenvalues))
            stability_idx = np.max(mags)
            stability_indices.append(stability_idx)
        except Exception as e:
            stability_indices.append(1.0)
            if verbose:
                print(f"  轨道 {i}: 稳定性计算失败 ({e})")

        if verbose and (i + 1) % 10 == 0:
            print(
                f"  已处理 {i + 1}/{len(states)}, "
                f"C={C:.6f}, max|λ|={stability_indices[-1]:.4f}"
            )

    family_data["jacobi_constants"] = np.array(jacobi_constants)
    family_data["stability_indices"] = np.array(stability_indices)
    return family_data


def refine_target_ro(dynamics, target_period, guess_state, verbose=True):
    """使用固定周期修正精确找到目标共振RO"""
    t_half = target_period / 2
    x0 = guess_state[0]
    vy0 = guess_state[4]

    orbit, result = correct_ro_fixed_t(dynamics, x0, vy0, t_half, verbose=verbose)
    return orbit, result


def plot_ro_family(family_data, label, target_T, save_dir, system):
    """绘制RO族结果图"""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    states = family_data["states"]
    periods = family_data["periods"]
    jacobi_constants = family_data["jacobi_constants"]
    stability_indices = family_data["stability_indices"]

    mu = system.mu
    dynamics = CR3BP_Dynamics(system)

    # -------- 图1：RO族轨道 --------
    fig, ax = plt.subplots(figsize=(12, 10))

    n = len(states)
    colors = plt.cm.coolwarm(np.linspace(0, 1, n))

    for i, state in enumerate(states):
        period = periods[i]
        # 积分完整轨道用于绘图
        from scipy.integrate import solve_ivp

        res = solve_ivp(
            dynamics.equations_of_motion,
            (0, period),
            state,
            method="DOP853",
            t_eval=np.linspace(0, period, max(500, int(period * 200))),
            rtol=1e-12,
            atol=1e-12,
        )
        ax.plot(res.y[0], res.y[1], color=colors[i], linewidth=0.3, alpha=0.6)

    # 标记目标RO
    if "target" in family_data:
        tgt = family_data["target"]
        st = tgt["state"]
        T = tgt["period"]
        res = solve_ivp(
            dynamics.equations_of_motion,
            (0, T),
            st,
            method="DOP853",
            t_eval=np.linspace(0, T, 2000),
            rtol=1e-12,
            atol=1e-12,
        )
        ax.plot(
            res.y[0], res.y[1], "r-", linewidth=2.5, label=f"{label} target (T={T:.4f})"
        )

    # 天体
    ax.plot(-mu, 0, "ko", markersize=10, label="Earth")
    ax.plot(1 - mu, 0, "g^", markersize=8, label="Moon")

    ax.set_xlabel("x (nondim)")
    ax.set_ylabel("y (nondim)")
    ax.set_title(f"{label} Resonant Orbit Family")
    ax.set_aspect("equal")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    fig.savefig(
        save_dir / f"{label.replace(':', '_')}_family_orbits.png",
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)

    # -------- 图2：特征图 --------
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    x0s = states[:, 0]

    ax = axes[0]
    ax.plot(x0s, periods, "b.-", markersize=3)
    ax.axhline(
        y=target_T,
        color="r",
        linestyle="--",
        alpha=0.7,
        label=f"T_target={target_T:.4f}",
    )
    ax.set_xlabel("$x_0$")
    ax.set_ylabel("Period $T$")
    ax.set_title(f"{label}: Period vs $x_0$")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(x0s, jacobi_constants, "r.-", markersize=3)
    ax.set_xlabel("$x_0$")
    ax.set_ylabel("Jacobi Constant $C$")
    ax.set_title(f"{label}: Jacobi vs $x_0$")
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.semilogy(x0s, stability_indices, "g.-", markersize=3)
    ax.axhline(y=1.0, color="k", linestyle="--", alpha=0.5)
    ax.set_xlabel("$x_0$")
    ax.set_ylabel("max $|\\lambda|$")
    ax.set_title(f"{label}: Stability vs $x_0$")
    ax.grid(True, alpha=0.3)

    fig.suptitle(f"{label} RO Family Characteristics", fontsize=14)
    fig.tight_layout()
    fig.savefig(
        save_dir / f"{label.replace(':', '_')}_family_characteristics.png",
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)


def save_ro_data(family_data, label, save_dir):
    """保存RO族数据"""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    prefix = label.replace(":", "_")

    np.savez(
        save_dir / f"{prefix}_family.npz",
        states=family_data["states"],
        periods=family_data["periods"],
        jacobi_constants=family_data["jacobi_constants"],
        stability_indices=family_data["stability_indices"],
        mu=MU,
    )

    if "target" in family_data:
        tgt = family_data["target"]
        target_dict = {
            "state": tgt["state"].tolist(),
            "period": float(tgt["period"]),
            "jacobi": float(tgt["jacobi"]),
            "stability": float(tgt["stability"]),
        }
        with open(save_dir / f"{prefix}_target.json", "w") as f:
            json.dump(target_dict, f, indent=2)


# ============================================================
# 主程序
# ============================================================
def process_one_resonance(system, dynamics, p, q, n_out=30, n_in=20):
    """处理一个共振比的完整流程"""
    label = f"{p}:{q}"
    T_target = 2 * np.pi * q

    print(f"\n{'#' * 60}")
    print(f"# {label} RO 族生成")
    print(f"# 目标周期 T = {T_target:.6f}")
    print(f"{'#' * 60}")

    # 1. 找种子
    seed_orbit, seed_result = find_ro_seed(dynamics, p, q, verbose=True)

    if seed_orbit is None:
        print(f"\n{label} RO 种子搜索失败！")
        return None

    print(f"\n{label} 种子RO:")
    print(f"  x0 = {seed_result['state'][0]:.10f}")
    print(f"  vy0 = {seed_result['state'][4]:.10f}")
    print(f"  T = {seed_result['period']:.10f}")

    # 2. 生成族 (延拓)
    family = generate_ro_family(
        dynamics, seed_result, n_outward=n_out, n_inward=n_in, verbose=True
    )

    if family is None:
        print(f"\n{label} RO 族延拓失败！")
        return None

    # 3. Jacobi常数和稳定性
    family = compute_jacobi_and_stability(family, dynamics, verbose=True)

    # 4. 精确修正到目标周期
    print(f"\n{'=' * 60}")
    print(f"精确修正 {label} RO 到 T = {T_target:.10f}")
    print(f"{'=' * 60}")

    # 找到最接近目标周期的轨道作为初始猜测
    idx_best = np.argmin(np.abs(family["periods"] - T_target))
    best_state = family["states"][idx_best]
    best_T = family["periods"][idx_best]
    print(
        f"  最佳初始猜测: 索引={idx_best}, T={best_T:.6f}, ΔT={abs(best_T - T_target):.2e}"
    )

    orbit_refined, result_refined = refine_target_ro(
        dynamics, T_target, best_state, verbose=True
    )

    if orbit_refined is not None:
        C_target = dynamics.system.get_jacobi_constant(result_refined["state"])

        # 稳定性
        try:
            stm = dynamics.compute_state_transition_matrix(
                result_refined["state"], result_refined["period"]
            )
            eigs = np.linalg.eigvals(stm)
            stab = np.max(np.abs(eigs))
        except:
            stab = 1.0

        family["target"] = {
            "state": result_refined["state"].copy(),
            "period": result_refined["period"],
            "jacobi": C_target,
            "stability": stab,
        }

        print(f"\n  ✓ {label} RO 精确修正成功:")
        print(f"    T = {result_refined['period']:.12f} (目标: {T_target:.12f})")
        print(f"    x0 = {result_refined['state'][0]:.12f}")
        print(f"    vy0 = {result_refined['state'][4]:.12f}")
        print(f"    Jacobi = {C_target:.8f}")
        print(f"    max|λ| = {stab:.6f}")
        print(f"    误差 = {result_refined['error']:.2e}")
    else:
        print(f"\n  ✗ {label} RO 精确修正失败")

    return family


def main():
    print("=" * 60)
    print("Phase 1: 共振轨道(RO)族生成")
    print(f"e2m2e v{e2m2e.__version__}")
    print("=" * 60)

    # 创建系统
    system = create_system()
    dynamics = CR3BP_Dynamics(system)
    dynamics.integrator = "DOP853"

    print(f"系统: μ = {system.mu}")
    print(f"L1: x = {system.L1[0]:.6f}")
    print(f"L2: x = {system.L2[0]:.6f}")

    output_dir = Path(__file__).parent.parent / "output" / "phase1_ro"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # ---- 3:2 RO ----
    family_32 = process_one_resonance(system, dynamics, 3, 2, n_out=25, n_in=15)
    if family_32 is not None:
        results["3:2"] = family_32
        save_ro_data(family_32, "3:2", output_dir)
        plot_ro_family(family_32, "3:2", T_RO_32, output_dir, system)
        print(f"\n3:2 RO 数据和图像已保存到 {output_dir.resolve()}")

    # ---- 3:1 RO ----
    family_31 = process_one_resonance(system, dynamics, 3, 1, n_out=25, n_in=15)
    if family_31 is not None:
        results["3:1"] = family_31
        save_ro_data(family_31, "3:1", output_dir)
        plot_ro_family(family_31, "3:1", T_RO_31, output_dir, system)
        print(f"\n3:1 RO 数据和图像已保存到 {output_dir.resolve()}")

    # ---- 总结 ----
    print(f"\n{'=' * 60}")
    print("Phase 1 RO族生成总结")
    print(f"{'=' * 60}")

    for key, fam in results.items():
        print(f"\n{key} RO:")
        print(f"  族大小: {len(fam['periods'])} 条轨道")
        print(
            f"  x0范围: [{fam['states'][:, 0].min():.4f}, {fam['states'][:, 0].max():.4f}]"
        )
        print(f"  周期范围: [{fam['periods'].min():.4f}, {fam['periods'].max():.4f}]")
        if "target" in fam:
            t = fam["target"]
            print(
                f"  目标轨道: x0={t['state'][0]:.8f}, vy0={t['state'][4]:.8f}, T={t['period']:.8f}"
            )

    print(f"\n{'=' * 60}")
    print("Phase 1 RO族生成完成！")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
