"""
阶段一：基线轨道生成 — 3D共振轨道 (RRO/ARO)

从平面共振轨道(RO)出发，生成3D周期轨道。

方法：
  1. 使用固定半周期(T/2)的3D修正 (setup_3D_symmetric_xz_fixed_t)
     - 固定T使得轨道保持目标共振比
     - 自由变量: x0, z0, vy0
     - 约束: y(T/2)=0, vx(T/2)=0, vz(T/2)=0
  2. 初始猜测: 平面RO + z0扰动
  3. 逐步增大z0至目标Az=0.2

理论背景：
  对于Kepler p:q共振轨道，面外频率≈面内频率,
  所以在精确共振周期附近，面外跟踪矩阵tr(M_z)≈2,
  此处发生切分岔,可产生3D周期轨道族(RRO/ARO)。

参考论文：Cui et al. (2025) JGCD, Vol.48, No.6
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
import json
from scipy.integrate import solve_ivp

import e2m2e
from e2m2e import CR3BP_System, CR3BP_Dynamics, DifferentialCorrection, Continuation
from e2m2e.algorithms.continuation import ContinuationDirection

# ============================================================
# 系统参数
# ============================================================
MU = 1.21506683e-2
DU = 3.84405e5
TU = 4.34811305
VU = 1023.23281
T_MOON = 2 * np.pi
AZ_TARGET = 0.2


def create_system():
    system = CR3BP_System(mu=MU, primary="Earth", secondary="Moon")
    system.set_characteristic_scales(distance=DU * 1e3, period=TU * 86400)
    system.compute_libration_points()
    return system


def load_ro_target(label, data_dir):
    """从Phase 1 RO结果中加载目标轨道"""
    prefix = label.replace(":", "_")
    data_dir = Path(data_dir)
    target_file = data_dir / f'{prefix}_target.json'
    with open(target_file) as f:
        target = json.load(f)
    return np.array(target['state']), target['period']


def validate_3d_orbit(state, period, dynamics, min_period=1.0):
    """验证3D轨道是否物理合理"""
    if period < min_period:
        return False, "T too short"
    if abs(state[0]) > 3.0:
        return False, f"x0={state[0]:.4f} out of range"
    if abs(state[2]) < 1e-6:
        return False, "z0~0 (planar)"
    C = dynamics.system.get_jacobi_constant(state)
    if C < -5 or C > 10:
        return False, f"Jacobi={C:.4f} unreasonable"
    # Closure check
    res = solve_ivp(
        dynamics.equations_of_motion,
        (0, period), state,
        method="DOP853", rtol=1e-12, atol=1e-12,
    )
    closure = np.linalg.norm(res.y[:, -1] - state)
    if closure > 0.01:
        return False, f"closure={closure:.2e}"
    return True, "OK"


def classify_3d_orbit(dynamics, state, period):
    """分类3D轨道为RRO或ARO"""
    res = solve_ivp(
        dynamics.equations_of_motion,
        (0, period), state,
        method="DOP853",
        t_eval=np.linspace(0, period, 5000),
        rtol=1e-12, atol=1e-12,
    )
    z_traj = res.y[2]
    y_traj = res.y[1]
    z_max = np.max(np.abs(z_traj))
    if z_max < 1e-10:
        return "Planar", 0.0, 0.0
    z_abs, y_abs = np.abs(z_traj), np.abs(y_traj)
    if np.std(z_abs) < 1e-10 or np.std(y_abs) < 1e-10:
        return "Unknown", 0.0, z_max
    corr = np.corrcoef(z_abs, y_abs)[0, 1]
    if corr < -0.2:
        return "RRO", corr, z_max
    elif corr > 0.2:
        return "ARO", corr, z_max
    else:
        return "3D-RO", corr, z_max


def gradual_z_search(dynamics, planar_state, t_half, z_target, n_steps=40, verbose=True):
    """逐步增大z0，使用固定T修正寻找3D轨道"""
    z_values = np.linspace(0.001, z_target, n_steps)
    
    results = []
    prev_state = planar_state.copy()
    
    for i, z0 in enumerate(z_values):
        state_guess = prev_state.copy()
        state_guess[2] = z0
        
        dc = DifferentialCorrection(dynamics)
        dc.setup_3D_symmetric_xz_fixed_t(t_half=t_half)
        dc.tolerance = 1e-12
        dc.max_iterations = 80
        
        result = dc.iterate_correction(state_guess, t_half, verbose=False)
        
        if result['success']:
            valid, msg = validate_3d_orbit(result['state'], result['period'], dynamics)
            if valid and abs(result['state'][2]) > 1e-6:
                results.append({
                    'state': result['state'].copy(),
                    'period': result['period'],
                })
                prev_state = result['state'].copy()
                
                if verbose and (i + 1) % 5 == 0:
                    s = result['state']
                    print(f"    z0={z0:.4f}: x0={s[0]:.6f}, z0_act={s[2]:.6f}, T={result['period']:.6f}")
    
    return results


def fixed_x0_continuation(dynamics, x0, vy0, t_half, z_target, verbose=True):
    """使用固定x0修正 + z0延拓"""
    # 找到小z0的3D轨道
    for z0_start in [0.001, 0.005, 0.01, 0.02, 0.05]:
        dc = DifferentialCorrection(dynamics)
        dc.setup_3D_symmetric_xz_fixed_x0(x0=x0)
        dc.tolerance = 1e-12
        dc.max_iterations = 80
        
        state = np.array([x0, 0.0, z0_start, 0.0, vy0, 0.0])
        result = dc.iterate_correction(state, t_half, verbose=False)
        
        if result['success']:
            z0_actual = result['state'][2]
            if abs(z0_actual) > 1e-6:
                valid, msg = validate_3d_orbit(result['state'], result['period'], dynamics)
                if valid:
                    if verbose:
                        print(f"    起始3D轨道: z0={z0_actual:.6f}, T={result['period']:.6f}")
                    
                    # 延拓到z_target
                    dc2 = DifferentialCorrection(dynamics)
                    dc2.setup_3D_symmetric_xz_fixed_x0(x0=x0)
                    dc2.tolerance = 1e-12
                    dc2.max_iterations = 80
                    
                    step = (z_target - z0_actual) / 30
                    cont = Continuation(dc2, param="z0", step=abs(step))
                    cont.direction = ContinuationDirection.FORWARD if step > 0 else ContinuationDirection.BACKWARD
                    cont.max_step_size = 0.05
                    cont.min_step_size = 1e-5
                    
                    fam = cont.natural_continuation(
                        result['state'], result['t_half'],
                        n_orbits=35, param_index=2, verbose=verbose
                    )
                    
                    if fam is not None:
                        results = []
                        for j in range(len(fam['states'])):
                            s, p = fam['states'][j], fam['periods'][j]
                            v, m = validate_3d_orbit(s, p, dynamics)
                            if v and abs(s[2]) > 1e-6:
                                results.append({'state': s.copy(), 'period': p})
                        return results
    
    return []


def plot_3d_results(orbits_info, save_dir, dynamics, system):
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    mu = system.mu
    
    if not orbits_info:
        return
    
    fig = plt.figure(figsize=(16, 12))
    ax1 = fig.add_subplot(221, projection='3d')
    ax2 = fig.add_subplot(222)
    ax3 = fig.add_subplot(223)
    ax4 = fig.add_subplot(224)
    
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'cyan']
    
    for i, info in enumerate(orbits_info):
        state, period = info['state'], info['period']
        label = info['label']
        color = colors[i % len(colors)]
        
        res = solve_ivp(
            dynamics.equations_of_motion, (0, period), state,
            method="DOP853", t_eval=np.linspace(0, period, 5000),
            rtol=1e-12, atol=1e-12,
        )
        x, y, z = res.y[0], res.y[1], res.y[2]
        
        ax1.plot(x, y, z, color=color, linewidth=0.8, label=label)
        ax2.plot(x, y, color=color, linewidth=0.8, label=label)
        ax3.plot(x, z, color=color, linewidth=0.8, label=label)
        ax4.plot(y, z, color=color, linewidth=0.8, label=label)
    
    for ax in [ax2, ax3]:
        ax.plot(-mu, 0, 'ko', markersize=6)
        ax.plot(1 - mu, 0, 'g^', markersize=5)
    
    ax1.set_xlabel('x'); ax1.set_ylabel('y'); ax1.set_zlabel('z')
    ax1.set_title('3D View'); ax1.legend(fontsize=7)
    ax2.set_xlabel('x'); ax2.set_ylabel('y')
    ax2.set_title('XY Projection'); ax2.set_aspect('equal')
    ax2.grid(True, alpha=0.3); ax2.legend(fontsize=7)
    ax3.set_xlabel('x'); ax3.set_ylabel('z')
    ax3.set_title('XZ Projection'); ax3.grid(True, alpha=0.3); ax3.legend(fontsize=7)
    ax4.set_xlabel('y'); ax4.set_ylabel('z')
    ax4.set_title('YZ Projection'); ax4.grid(True, alpha=0.3); ax4.legend(fontsize=7)
    
    fig.suptitle('3D Resonant Orbits', fontsize=14)
    fig.tight_layout()
    fig.savefig(save_dir / '3d_ro_orbits.png', dpi=200, bbox_inches='tight')
    plt.close(fig)


def save_3d_data(orbits_info, save_dir):
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    data = {}
    for info in orbits_info:
        key = info['label'].replace(' ', '_').replace(':', '_')
        data[key] = {
            'state': info['state'].tolist(),
            'period': float(info['period']),
            'z_max': float(info['z_max']),
            'orbit_type': info['orbit_type'],
            'base_resonance': info['base_resonance'],
            'jacobi': float(info['jacobi']),
        }
    with open(save_dir / '3d_ro_targets.json', 'w') as f:
        json.dump(data, f, indent=2)


# ============================================================
def main():
    print("=" * 60)
    print("Phase 1: 3D RO (RRO/ARO)")
    print(f"e2m2e v{e2m2e.__version__}")
    print(f"目标z振幅: Az = {AZ_TARGET}")
    print("=" * 60)
    
    system = create_system()
    dynamics = CR3BP_Dynamics(system)
    dynamics.integrator = "DOP853"
    
    ro_dir = Path(__file__).parent.parent / "output" / "phase1_ro"
    output_dir = Path(__file__).parent.parent / "output" / "phase1_3d_ro"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_3d = []
    
    for label, p, q in [("3:2", 3, 2), ("3:1", 3, 1)]:
        T_target = 2 * np.pi * q
        t_half = T_target / 2
        
        print(f"\n{'#'*60}")
        print(f"# {label} -> 3D RO (T={T_target:.4f}, Az={AZ_TARGET})")
        print(f"{'#'*60}")
        
        try:
            planar_state, planar_T = load_ro_target(label, ro_dir)
        except FileNotFoundError:
            print(f"  平面RO数据未找到")
            continue
        
        print(f"  平面RO: x0={planar_state[0]:.8f}, vy0={planar_state[4]:.8f}, T={planar_T:.8f}")
        found_for_resonance = []
        
        # ---- M1: 固定T, 直接z0=target ----
        print(f"\n  M1: 固定T + z0={AZ_TARGET}")
        dc = DifferentialCorrection(dynamics)
        dc.setup_3D_symmetric_xz_fixed_t(t_half=t_half)
        dc.tolerance = 1e-12
        dc.max_iterations = 80
        
        state_g = planar_state.copy()
        state_g[2] = AZ_TARGET
        result = dc.iterate_correction(state_g, t_half, verbose=True)
        
        if result['success']:
            valid, msg = validate_3d_orbit(result['state'], result['period'], dynamics)
            if valid:
                otype, corr, zmax = classify_3d_orbit(dynamics, result['state'], result['period'])
                C = dynamics.system.get_jacobi_constant(result['state'])
                found_for_resonance.append({
                    'state': result['state'].copy(), 'period': result['period'],
                    'z_max': zmax, 'orbit_type': otype, 'base_resonance': label,
                    'jacobi': C, 'label': f'{label} {otype}',
                })
                print(f"  OK: {otype} z_max={zmax:.4f} T={result['period']:.6f} C={C:.6f}")
            else:
                print(f"  Invalid: {msg}")
        else:
            print(f"  Failed")
        
        # ---- M2: 逐步z0, 固定T ----
        print(f"\n  M2: gradual z0 (fixed T)")
        res_grad = gradual_z_search(dynamics, planar_state, t_half, AZ_TARGET, n_steps=40, verbose=True)
        if res_grad:
            z0s = [r['state'][2] for r in res_grad]
            idx = np.argmin([abs(z - AZ_TARGET) for z in z0s])
            best = res_grad[idx]
            is_dup = any(np.linalg.norm(e['state'] - best['state']) < 0.01 for e in found_for_resonance)
            if not is_dup:
                otype, corr, zmax = classify_3d_orbit(dynamics, best['state'], best['period'])
                C = dynamics.system.get_jacobi_constant(best['state'])
                found_for_resonance.append({
                    'state': best['state'].copy(), 'period': best['period'],
                    'z_max': zmax, 'orbit_type': otype, 'base_resonance': label,
                    'jacobi': C, 'label': f'{label} {otype} (grad)',
                })
                print(f"  OK: {otype} z0={best['state'][2]:.4f} T={best['period']:.6f}")
        else:
            print(f"  No results")
        
        # ---- M3: 固定x0 + z延拓 ----
        print(f"\n  M3: fixed x0 + z continuation")
        res_cont = fixed_x0_continuation(
            dynamics, planar_state[0], planar_state[4], t_half, AZ_TARGET, verbose=True
        )
        if res_cont:
            z0s = [r['state'][2] for r in res_cont]
            idx = np.argmin([abs(z - AZ_TARGET) for z in z0s])
            best = res_cont[idx]
            is_dup = any(np.linalg.norm(e['state'] - best['state']) < 0.01 for e in found_for_resonance)
            if not is_dup:
                otype, corr, zmax = classify_3d_orbit(dynamics, best['state'], best['period'])
                C = dynamics.system.get_jacobi_constant(best['state'])
                found_for_resonance.append({
                    'state': best['state'].copy(), 'period': best['period'],
                    'z_max': zmax, 'orbit_type': otype, 'base_resonance': label,
                    'jacobi': C, 'label': f'{label} {otype} (cont)',
                })
                print(f"  OK: {otype} z0={best['state'][2]:.4f} T={best['period']:.6f}")
        else:
            print(f"  No results")
        
        # ---- M4: vy0 offset search ----
        print(f"\n  M4: vy0 offset search")
        for dvy in [-0.2, -0.1, 0.1, 0.2, -0.3, 0.3, -0.5, 0.5]:
            sg = planar_state.copy()
            sg[2] = AZ_TARGET
            sg[4] += dvy
            
            dc2 = DifferentialCorrection(dynamics)
            dc2.setup_3D_symmetric_xz_fixed_t(t_half=t_half)
            dc2.tolerance = 1e-12
            dc2.max_iterations = 80
            
            r2 = dc2.iterate_correction(sg, t_half, verbose=False)
            if r2['success']:
                v, m = validate_3d_orbit(r2['state'], r2['period'], dynamics)
                if v:
                    is_dup = any(np.linalg.norm(e['state'] - r2['state']) < 0.01 for e in found_for_resonance)
                    if not is_dup:
                        otype, corr, zmax = classify_3d_orbit(dynamics, r2['state'], r2['period'])
                        C = dynamics.system.get_jacobi_constant(r2['state'])
                        found_for_resonance.append({
                            'state': r2['state'].copy(), 'period': r2['period'],
                            'z_max': zmax, 'orbit_type': otype, 'base_resonance': label,
                            'jacobi': C, 'label': f'{label} {otype} (dvy={dvy:+.1f})',
                        })
                        print(f"  OK (dvy={dvy:+.1f}): {otype} z={r2['state'][2]:.4f} T={r2['period']:.6f}")
        
        all_3d.extend(found_for_resonance)
        
        print(f"\n  {label}: found {len(found_for_resonance)} distinct 3D orbits")
    
    # Final refinement to exact Az
    print(f"\n{'='*60}")
    print(f"Final refinement to Az={AZ_TARGET}")
    print(f"{'='*60}")
    
    final = []
    for info in all_3d:
        state = info['state']
        t_h = info['period'] / 2
        
        dc = DifferentialCorrection(dynamics)
        dc.setup_3D_symmetric_xz_fixed_z0(z0=AZ_TARGET)
        dc.tolerance = 1e-14
        dc.max_iterations = 80
        
        r = dc.iterate_correction(state, t_h, verbose=False)
        if r['success']:
            v, m = validate_3d_orbit(r['state'], r['period'], dynamics)
            if v:
                otype, corr, zmax = classify_3d_orbit(dynamics, r['state'], r['period'])
                C = dynamics.system.get_jacobi_constant(r['state'])
                
                is_dup = any(np.linalg.norm(e['state'] - r['state']) < 0.01 for e in final)
                if not is_dup:
                    final.append({
                        'state': r['state'].copy(), 'period': r['period'],
                        'z_max': zmax, 'orbit_type': otype, 'base_resonance': info['base_resonance'],
                        'jacobi': C, 'label': info['label'],
                    })
                    print(f"  {info['label']}: x0={r['state'][0]:.6f} z0={r['state'][2]:.6f} "
                          f"vy0={r['state'][4]:.6f} T={r['period']:.6f} C={C:.6f} [{otype}]")
    
    if final:
        save_3d_data(final, output_dir)
        plot_3d_results(final, output_dir, dynamics, system)
        print(f"\nSaved to {output_dir.resolve()}")
    
    print(f"\n{'='*60}")
    print(f"Summary: {len(final)} 3D RO found")
    print(f"{'='*60}")
    for o in final:
        print(f"  {o['label']}: T={o['period']:.4f}, z_max={o['z_max']:.4f}, C={o['jacobi']:.4f}")
    if not final:
        print("  No valid 3D RO found. This is expected if no bifurcation exists at these resonances.")
    print("Done!")


if __name__ == "__main__":
    main()
