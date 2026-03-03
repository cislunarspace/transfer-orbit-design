"""
阶段一：基线轨道生成 — DRO族

生成完整的Distant Retrograde Orbit (DRO)族，计算Jacobi常数与稳定性指标。
识别论文中使用的2:1 DRO和3:1 DRO。

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6

DRO是月球远距离逆行轨道（Broucke Family F），具有以下对称性：
  - 关于x轴对称
  - 初始状态 [x0, 0, 0, 0, vy0, 0]，其中vy0 < 0（逆行）
  - 半周期条件：y(T/2) = 0, vx(T/2) = 0

论文参数：
  μ = 1.21506683 × 10⁻² (地月系统质量比)
  DU = 3.84405 × 10⁵ km, TU = 4.34811305 天
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
from pathlib import Path
import json

import e2m2e
from e2m2e import CR3BP_System, CR3BP_Dynamics, DifferentialCorrection, Continuation

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
MU = 1.21506683e-2   # 地月系统质量比
DU = 3.84405e5       # 距离单位 km
TU = 4.34811305      # 时间单位 天
VU = 1023.23281      # 速度单位 m/s

# 月球恒星周期 = 2π (无量纲)
T_MOON = 2 * np.pi

# 目标DRO
# 2:1 DRO: 2次绕月/1次月球公转 → T = T_MOON / 2 = π
# 3:1 DRO: 3次绕月/1次月球公转 → T = T_MOON / 3 = 2π/3
T_DRO_21 = T_MOON / 2    # ≈ 3.14159
T_DRO_31 = T_MOON / 3    # ≈ 2.09440


def find_half_period(dynamics, state, t_max=10.0):
    """通过积分找到DRO的半周期（首次y=0穿越时间）
    
    从(x0, 0, 0, 0, vy0, 0)出发，找到第一次y再次等于0的时间
    """
    from scipy.integrate import solve_ivp
    
    def y_crossing(t, s):
        return s[1]  # y = 0
    y_crossing.terminal = True
    y_crossing.direction = -1 if state[4] < 0 else 1  # DRO逆行时y先减后增
    
    # 先积分一小步避免初始y=0被检测
    result_init = solve_ivp(
        dynamics.equations_of_motion,
        (0, 0.01), state,
        method="DOP853", rtol=1e-12, atol=1e-12,
    )
    state_shifted = result_init.y[:, -1]
    
    # 从偏移点积分，检测y=0穿越
    # 对于逆行DRO (vy<0), 半周期时y从负返回0
    y_crossing.direction = 0  # 双向检测
    
    result = solve_ivp(
        dynamics.equations_of_motion,
        (0.01, t_max), state_shifted,
        method="DOP853", rtol=1e-12, atol=1e-12,
        events=y_crossing, dense_output=True,
    )
    
    if result.t_events[0].size > 0:
        t_half = result.t_events[0][0]
        return t_half
    return None


def create_system():
    """创建地月CR3BP系统"""
    system = CR3BP_System(mu=MU, primary="Earth", secondary="Moon")
    system.set_characteristic_scales(distance=DU * 1e3, period=TU * 86400)
    system.compute_libration_points()
    return system


def correct_single_dro(dynamics, x0, vy0_guess, verbose=False):
    """修正单个DRO
    
    从初始猜测(x0, vy0_guess)出发，找到精确DRO。
    先数值搜索半周期，再微分修正。
    """
    state_guess = np.array([x0, 0, 0, 0, vy0_guess, 0])
    
    # 找半周期
    t_half = find_half_period(dynamics, state_guess, t_max=10.0)
    if t_half is None:
        return None, None
    
    # 微分修正
    dc = DifferentialCorrection(dynamics)
    dc.setup_2D_symmetric_x_fixed_x0(x0=x0)
    dc.tolerance = 1e-12
    dc.max_iterations = 30
    
    orbit, result = dc.correct_orbit(state_guess, t_half, verbose=verbose)
    return orbit, result


def generate_dro_family(system, n_orbits=100, verbose=True):
    """使用延拓生成DRO族
    
    策略：
    1. 从一个已知收敛的DRO种子开始（先用数值搜索找到半周期）
    2. 使用自然参数延拓，沿x0方向双向扩展
    3. 生成覆盖大范围x0的完整DRO族
    """
    dynamics = CR3BP_Dynamics(system)
    dynamics.integrator = "DOP853"
    mu = system.mu
    
    # ---- Step 1: 找种子轨道 ----
    # 使用一个中等大小的DRO: x0 = 1.15 (约0.16远离月球)
    x0_seed = 1.15
    # Keplerian估计逆行速度（旋转系中）
    r_moon = x0_seed - (1 - mu)
    vy_kep = -(np.sqrt(mu / r_moon) + r_moon)
    
    if verbose:
        print("=" * 60)
        print("DRO族生成")
        print("=" * 60)
        print(f"种子: x0={x0_seed}, vy0_guess={vy_kep:.6f}")
    
    seed_orbit, seed_result = correct_single_dro(
        dynamics, x0_seed, vy_kep, verbose=verbose
    )
    
    if seed_orbit is None:
        # 尝试扫描vy寻找
        if verbose:
            print("种子修正失败，尝试vy扫描...")
        for vy_try in np.linspace(-0.2, -1.5, 20):
            seed_orbit, seed_result = correct_single_dro(
                dynamics, x0_seed, vy_try, verbose=False
            )
            if seed_orbit is not None:
                if verbose:
                    print(f"  vy={vy_try:.4f} 成功!")
                break
    
    if seed_orbit is None:
        print("无法找到种子DRO！")
        return None
    
    if verbose:
        print(f"\n种子DRO: T={seed_result['period']:.6f}, "
              f"x0={seed_result['state'][0]:.8f}, vy0={seed_result['state'][4]:.8f}")
    
    # ---- Step 2: 向外延拓 (x0增大) ----
    all_states = [seed_result['state'].copy()]
    all_periods = [seed_result['period']]
    all_orbits = [seed_orbit]
    
    if verbose:
        print(f"\n--- 向外延拓 ---")
    
    dc_out = DifferentialCorrection(dynamics)
    dc_out.setup_2D_symmetric_x_fixed_x0(x0=x0_seed)
    dc_out.tolerance = 1e-12
    
    cont_out = Continuation(dc_out, param="x0", step=0.01)
    cont_out.direction = e2m2e.algorithms.continuation.ContinuationDirection.FORWARD
    cont_out.max_step_size = 0.05
    cont_out.min_step_size = 1e-5
    
    n_outward = n_orbits * 2 // 3
    result_out = cont_out.natural_continuation(
        seed_result['state'], seed_result['t_half'],
        n_orbits=n_outward, param_index=0, verbose=verbose
    )
    
    if result_out is not None:
        for i in range(1, len(result_out['states'])):
            all_states.append(result_out['states'][i])
            all_periods.append(result_out['periods'][i])
            all_orbits.append(result_out['orbits'][i])
    
    # ---- Step 3: 向内延拓 (x0减小) ----
    if verbose:
        print(f"\n--- 向内延拓 ---")
    
    dc_in = DifferentialCorrection(dynamics)
    dc_in.setup_2D_symmetric_x_fixed_x0(x0=x0_seed)
    dc_in.tolerance = 1e-12
    
    cont_in = Continuation(dc_in, param="x0", step=0.005)
    cont_in.direction = e2m2e.algorithms.continuation.ContinuationDirection.BACKWARD
    cont_in.max_step_size = 0.02
    cont_in.min_step_size = 1e-5
    
    n_inward = n_orbits // 3
    result_in = cont_in.natural_continuation(
        seed_result['state'], seed_result['t_half'],
        n_orbits=n_inward, param_index=0, verbose=verbose
    )
    
    if result_in is not None:
        for i in range(len(result_in['states']) - 1, 0, -1):
            all_states.insert(0, result_in['states'][i])
            all_periods.insert(0, result_in['periods'][i])
            all_orbits.insert(0, result_in['orbits'][i])
    
    all_states = np.array(all_states)
    all_periods = np.array(all_periods)
    
    if verbose:
        print(f"\n总计生成 {len(all_periods)} 条DRO")
        print(f"x0 范围: [{all_states[:, 0].min():.4f}, {all_states[:, 0].max():.4f}]")
        print(f"周期范围: [{all_periods.min():.4f}, {all_periods.max():.4f}]")
    
    return {
        'states': all_states,
        'periods': all_periods,
        'orbits': all_orbits,
        'system': system,
    }


def compute_jacobi_and_stability(family_data, verbose=True):
    """计算DRO族的Jacobi常数和稳定性指标"""
    system = family_data['system']
    dynamics = CR3BP_Dynamics(system)
    dynamics.integrator = "DOP853"
    
    states = family_data['states']
    periods = family_data['periods']
    
    jacobi_constants = []
    stability_indices = []
    eigenvalue_magnitudes = []
    
    if verbose:
        print(f"\n{'='*60}")
        print("计算Jacobi常数和稳定性")
        print(f"{'='*60}")
    
    for i, (state, period) in enumerate(zip(states, periods)):
        # Jacobi常数
        C = system.get_jacobi_constant(state)
        jacobi_constants.append(C)
        
        # 单值矩阵和稳定性
        try:
            stm = dynamics.compute_state_transition_matrix(state, period)
            eigenvalues = np.linalg.eigvals(stm)
            mags = np.sort(np.abs(eigenvalues))
            eigenvalue_magnitudes.append(mags)
            
            # 稳定性指标：max(|λ|)
            stability_idx = np.max(mags)
            stability_indices.append(stability_idx)
        except Exception as e:
            eigenvalue_magnitudes.append(np.ones(6))
            stability_indices.append(1.0)
            if verbose:
                print(f"  轨道 {i}: 稳定性计算失败 ({e})")
        
        if verbose and (i + 1) % 20 == 0:
            print(f"  已处理 {i+1}/{len(states)}, "
                  f"C={C:.6f}, max|λ|={stability_indices[-1]:.4f}")
    
    family_data['jacobi_constants'] = np.array(jacobi_constants)
    family_data['stability_indices'] = np.array(stability_indices)
    family_data['eigenvalue_magnitudes'] = eigenvalue_magnitudes
    
    return family_data


def identify_target_dros(family_data, verbose=True):
    """识别2:1 DRO和3:1 DRO
    
    通过周期匹配找到目标DRO：
    - 2:1 DRO: T ≈ π
    - 3:1 DRO: T ≈ 2π/3
    """
    periods = family_data['periods']
    states = family_data['states']
    
    # 找最接近目标周期的DRO
    idx_21 = np.argmin(np.abs(periods - T_DRO_21))
    idx_31 = np.argmin(np.abs(periods - T_DRO_31))
    
    dro_21 = {
        'state': states[idx_21],
        'period': periods[idx_21],
        'index': int(idx_21),
        'jacobi': family_data['jacobi_constants'][idx_21],
        'stability': family_data['stability_indices'][idx_21],
    }
    
    dro_31 = {
        'state': states[idx_31],
        'period': periods[idx_31],
        'index': int(idx_31),
        'jacobi': family_data['jacobi_constants'][idx_31],
        'stability': family_data['stability_indices'][idx_31],
    }
    
    if verbose:
        print(f"\n{'='*60}")
        print("目标DRO识别")
        print(f"{'='*60}")
        
        print(f"\n2:1 DRO (目标T={T_DRO_21:.6f}):")
        print(f"  索引={idx_21}, T={dro_21['period']:.6f}, "
              f"ΔT={abs(dro_21['period']-T_DRO_21):.2e}")
        print(f"  x0={dro_21['state'][0]:.8f}, vy0={dro_21['state'][4]:.8f}")
        print(f"  Jacobi={dro_21['jacobi']:.6f}, max|λ|={dro_21['stability']:.4f}")
        
        print(f"\n3:1 DRO (目标T={T_DRO_31:.6f}):")
        print(f"  索引={idx_31}, T={dro_31['period']:.6f}, "
              f"ΔT={abs(dro_31['period']-T_DRO_31):.2e}")
        print(f"  x0={dro_31['state'][0]:.8f}, vy0={dro_31['state'][4]:.8f}")
        print(f"  Jacobi={dro_31['jacobi']:.6f}, max|λ|={dro_31['stability']:.4f}")
    
    family_data['dro_21'] = dro_21
    family_data['dro_31'] = dro_31
    
    return family_data


def refine_target_dro(system, target_period, initial_guess_state, initial_t_half):
    """使用固定周期的微分修正精确找到目标DRO
    
    固定T/2，调整x0和vy0使轨道精确闭合
    """
    dynamics = CR3BP_Dynamics(system)
    dynamics.integrator = "DOP853"
    
    dc = DifferentialCorrection(dynamics)
    dc.setup_2D_symmetric_x_fixed_t(t_half=target_period / 2)
    dc.tolerance = 1e-14  # 更高精度
    
    orbit, result = dc.correct_orbit(initial_guess_state, target_period / 2, verbose=False)
    return orbit, result


def plot_dro_family(family_data, save_dir):
    """绘制DRO族结果图"""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    
    states = family_data['states']
    periods = family_data['periods']
    jacobi_constants = family_data['jacobi_constants']
    stability_indices = family_data['stability_indices']
    orbits = family_data['orbits']
    
    mu = family_data['system'].mu
    
    # -------- 图1：DRO族轨道 --------
    fig, ax = plt.subplots(figsize=(12, 8))
    
    n = len(orbits)
    colors = plt.cm.viridis(np.linspace(0, 1, n))
    
    for i, orbit in enumerate(orbits):
        ax.plot(orbit.states[:, 0], orbit.states[:, 1], 
                color=colors[i], linewidth=0.5, alpha=0.7)
    
    # 标记2:1和3:1 DRO
    if 'dro_21' in family_data:
        idx = family_data['dro_21']['index']
        ax.plot(orbits[idx].states[:, 0], orbits[idx].states[:, 1],
                'r-', linewidth=2.0, label=f"2:1 DRO (T={periods[idx]:.4f})")
    if 'dro_31' in family_data:
        idx = family_data['dro_31']['index']
        ax.plot(orbits[idx].states[:, 0], orbits[idx].states[:, 1],
                'b-', linewidth=2.0, label=f"3:1 DRO (T={periods[idx]:.4f})")
    
    # 主天体
    ax.plot(-mu, 0, 'ko', markersize=10, label='Earth')
    ax.plot(1-mu, 0, 'g^', markersize=8, label='Moon')
    
    ax.set_xlabel('x (无量纲)')
    ax.set_ylabel('y (无量纲)')
    ax.set_title('DRO轨道族 (Broucke Family F)')
    ax.set_aspect('equal')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    fig.savefig(save_dir / 'dro_family_orbits.png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    
    # -------- 图2：特征图 (x0 vs 周期, x0 vs Jacobi, x0 vs 稳定性) --------
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    x0s = states[:, 0]
    
    # x0 vs 周期
    ax = axes[0]
    ax.plot(x0s, periods, 'b.-', markersize=2)
    ax.axhline(y=T_DRO_21, color='r', linestyle='--', alpha=0.7, label=f'T(2:1)={T_DRO_21:.4f}')
    ax.axhline(y=T_DRO_31, color='g', linestyle='--', alpha=0.7, label=f'T(3:1)={T_DRO_31:.4f}')
    ax.set_xlabel('$x_0$')
    ax.set_ylabel('Period $T$')
    ax.set_title('周期 vs 初始x坐标')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # x0 vs Jacobi
    ax = axes[1]
    ax.plot(x0s, jacobi_constants, 'r.-', markersize=2)
    ax.set_xlabel('$x_0$')
    ax.set_ylabel('Jacobi Constant $C$')
    ax.set_title('Jacobi常数 vs 初始x坐标')
    ax.grid(True, alpha=0.3)
    
    # x0 vs 稳定性
    ax = axes[2]
    ax.semilogy(x0s, stability_indices, 'g.-', markersize=2)
    ax.axhline(y=1.0, color='k', linestyle='--', alpha=0.5)
    ax.set_xlabel('$x_0$')
    ax.set_ylabel('max $|\\lambda|$')
    ax.set_title('稳定性指标 vs 初始x坐标')
    ax.grid(True, alpha=0.3)
    
    fig.suptitle('DRO族特征', fontsize=14)
    fig.tight_layout()
    fig.savefig(save_dir / 'dro_family_characteristics.png', dpi=200, bbox_inches='tight')
    plt.close(fig)
    
    print(f"\n图像已保存到 {save_dir.resolve()}")


def save_family_data(family_data, save_dir):
    """保存DRO族数据到文件"""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存核心数据为npz
    np.savez(
        save_dir / 'dro_family.npz',
        states=family_data['states'],
        periods=family_data['periods'],
        jacobi_constants=family_data['jacobi_constants'],
        stability_indices=family_data['stability_indices'],
        mu=family_data['system'].mu,
    )
    
    # 保存目标DRO为json
    targets = {}
    for key in ['dro_21', 'dro_31']:
        if key in family_data:
            d = family_data[key]
            targets[key] = {
                'state': d['state'].tolist(),
                'period': float(d['period']),
                'index': d['index'],
                'jacobi': float(d['jacobi']),
                'stability': float(d['stability']),
            }
    
    with open(save_dir / 'dro_targets.json', 'w') as f:
        json.dump(targets, f, indent=2)
    
    print(f"数据已保存到 {save_dir.resolve()}")


# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 60)
    print("Phase 1: DRO族生成")
    print(f"e2m2e v{e2m2e.__version__}")
    print("=" * 60)
    
    # 1. 创建系统
    system = create_system()
    print(f"系统: μ={system.mu}")
    print(f"L1: x={system.L1[0]:.6f}")
    print(f"L2: x={system.L2[0]:.6f}")
    
    # 2. 生成DRO族
    family_data = generate_dro_family(system, n_orbits=120, verbose=True)
    if family_data is None:
        print("DRO族生成失败！")
        return
    
    # 3. 计算Jacobi常数和稳定性
    family_data = compute_jacobi_and_stability(family_data, verbose=True)
    
    # 4. 识别目标DRO
    family_data = identify_target_dros(family_data, verbose=True)
    
    # 5. 精确修正目标DRO到精确共振周期
    print(f"\n{'='*60}")
    print("精确修正目标DRO")
    print(f"{'='*60}")
    
    for name, target_T in [("2:1 DRO", T_DRO_21), ("3:1 DRO", T_DRO_31)]:
        key = 'dro_21' if '2:1' in name else 'dro_31'
        guess_state = family_data[key]['state']
        
        orbit, result = refine_target_dro(system, target_T, guess_state, target_T / 2)
        if orbit is not None:
            print(f"\n{name} 精确修正成功:")
            print(f"  T = {result['period']:.12f} (目标: {target_T:.12f})")
            print(f"  x0 = {result['state'][0]:.12f}")
            print(f"  vy0 = {result['state'][4]:.12f}")
            print(f"  误差 = {result['error']:.2e}")
            family_data[key]['refined_state'] = result['state'].copy()
            family_data[key]['refined_period'] = result['period']
            family_data[key]['refined_orbit'] = orbit
        else:
            print(f"\n{name} 精确修正失败: {result['termination_reason']}")
    
    # 6. 保存和绘图
    output_dir = Path(__file__).parent.parent / "output" / "phase1_dro"
    save_family_data(family_data, output_dir)
    plot_dro_family(family_data, output_dir)
    
    print(f"\n{'='*60}")
    print("Phase 1 DRO族生成完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
