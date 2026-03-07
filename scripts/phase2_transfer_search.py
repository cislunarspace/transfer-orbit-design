"""
阶段二：CR3BP中的两脉冲转移设计（搜索+优化）
==================================================

实现从DRO到RO的两脉冲转移轨道设计。

四种平面转移路径：
  1. 2:1 DRO -> 3:2 RO
  2. 2:1 DRO -> 3:1 RO
  3. 3:1 DRO -> 3:2 RO
  4. 3:1 DRO -> 3:1 RO

方法论（Cui et al. 2025）：
  1. 搜索阶段：网格化出发点×脉冲方向，前向积分，筛选与RO接近的轨迹
  2. 优化阶段：以搜索结果为初始猜测，SQP求解NLP问题
     - 优化变量: [α, Δv_mag, T, t_ins]
     - 目标函数: J = Δv1 + Δv2
     - 约束条件: 位置连续性

三种典型转移类型：
  - 直接转移 (Direct): T < 20天, 近似椭圆轨道
  - 月球借力转移 (LGA): 经过月球近旁，60-80天
  - 外部转移 (External): 远地点超过3DU，60-100天
"""

import sys
import numpy as np
from scipy.integrate import solve_ivp
from scipy.spatial import cKDTree
from scipy.optimize import minimize
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
import json
import re
import time as time_mod


def _safe_filename(name):
    """Sanitise pair_name for use as filename (remove special chars)."""
    name = name.replace('->', 'to').replace(':', '')
    return re.sub(r'[^\w\-.]', '_', name)

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
MU = 1.21506683e-2
DU = 3.84405e5       # km
TU = 4.34811305      # days
VU = 1023.23281      # m/s

R_EARTH_ND = 6378.0 / (DU * 1e3 / 1e3)   # Earth radius in ND  ~0.0166
R_MOON_ND  = 1737.0 / (DU * 1e3 / 1e3)   # Moon radius in ND   ~0.00452

# ============================================================
# CR3BP Equations of Motion (standalone for speed)
# ============================================================
def cr3bp_eom(t, state):
    """CR3BP equations of motion (6-dim)."""
    x, y, z, vx, vy, vz = state
    r1_3 = ((x + MU)**2 + y**2 + z**2)**1.5
    r2_3 = ((x - 1 + MU)**2 + y**2 + z**2)**1.5
    ax = 2*vy + x - (1-MU)*(x+MU)/r1_3 - MU*(x-1+MU)/r2_3
    ay = -2*vx + y - (1-MU)*y/r1_3 - MU*y/r2_3
    az = -(1-MU)*z/r1_3 - MU*z/r2_3
    return [vx, vy, vz, ax, ay, az]


def jacobi_constant(state):
    """Compute Jacobi constant."""
    x, y, z, vx, vy, vz = state
    r1 = np.sqrt((x + MU)**2 + y**2 + z**2)
    r2 = np.sqrt((x - 1 + MU)**2 + y**2 + z**2)
    U = 0.5*(x**2 + y**2) + (1-MU)/r1 + MU/r2
    return 2*U - (vx**2 + vy**2 + vz**2)


# ============================================================
# Collision events
# ============================================================
def _make_earth_collision():
    def event(t, state):
        return np.sqrt((state[0]+MU)**2 + state[1]**2 + state[2]**2) - R_EARTH_ND*1.5
    event.terminal = True
    event.direction = -1
    return event

def _make_moon_collision():
    def event(t, state):
        return np.sqrt((state[0]-1+MU)**2 + state[1]**2 + state[2]**2) - R_MOON_ND*1.5
    event.terminal = True
    event.direction = -1
    return event

COLLISION_EVENTS = [_make_earth_collision(), _make_moon_collision()]


# ============================================================
# Orbit sampling
# ============================================================
def sample_orbit(state0, period, n_points=2000):
    """Propagate a periodic orbit and return dense-output solution."""
    t_eval = np.linspace(0, period, n_points, endpoint=False)
    sol = solve_ivp(cr3bp_eom, [0, period], state0,
                    method='DOP853', rtol=1e-13, atol=1e-13,
                    t_eval=t_eval, max_step=0.01, dense_output=True)
    return sol.t, sol.y.T, sol   # times, states(N,6), OdeSolution


# ============================================================
# Helper: tangent/normal frame at a point on an orbit
# ============================================================
def _tn_frame(v):
    """Return (e_t, e_n) in xy-plane from velocity vector v."""
    vxy = v[:2]
    vmag = np.linalg.norm(vxy)
    if vmag < 1e-15:
        return np.array([1.0, 0.0]), np.array([0.0, 1.0])
    e_t = vxy / vmag
    e_n = np.array([-e_t[1], e_t[0]])   # 90° CCW
    return e_t, e_n


# ============================================================
# SEARCH PHASE
# ============================================================
def search_transfers(dro_state, dro_period, ro_state, ro_period,
                     pair_name="",
                     n_dep=24, n_alpha=48,
                     dv_mags=(0.1, 0.2, 0.4),
                     t_max=25.0,
                     dist_threshold=0.03,
                     verbose=True):
    """
    Grid search for two-impulse transfer candidates.

    Uses a coarse-then-fine strategy: integrate with large max_step, check
    distances to RO at integration output points (no extra dense sampling).
    """
    if verbose:
        total = n_dep * n_alpha * len(dv_mags)
        print(f"\n{'='*60}", flush=True)
        print(f"SEARCH  {pair_name}", flush=True)
        print(f"  DRO  x0={dro_state[0]:.6f}  T={dro_period:.6f} "
              f"({dro_period*TU:.2f} d)")
        print(f"  RO   x0={ro_state[0]:.6f}  T={ro_period:.6f} "
              f"({ro_period*TU:.2f} d)")
        print(f"  Grid {n_dep}×{n_alpha}×{len(dv_mags)} = {total}")

    # 1. sample DRO — departure points
    dro_t, dro_pts, _ = sample_orbit(dro_state, dro_period, n_dep)
    # 2. sample RO (dense) and build KD-tree
    n_ro = 2000
    ro_t, ro_pts, ro_sol = sample_orbit(ro_state, ro_period, n_ro)
    ro_tree = cKDTree(ro_pts[:, :2])

    alphas = np.linspace(-np.pi, np.pi, n_alpha, endpoint=False)
    candidates = []
    t0 = time_mod.time()
    cnt = 0

    # time grid for trajectory sampling (fixed, reused for every case)
    t_eval_fixed = np.linspace(0, t_max, 400)

    for i_dep in range(n_dep):
        dep = dro_pts[i_dep]
        r_dep = dep[:3]
        v_dro = dep[3:]
        e_t, e_n = _tn_frame(v_dro)

        for dv_mag in dv_mags:
            # vectorise alpha loop: pre-compute all impulse vectors
            cos_a = np.cos(alphas)
            sin_a = np.sin(alphas)
            for ia, alpha in enumerate(alphas):
                cnt += 1
                dv_xy = dv_mag * (cos_a[ia]*e_t + sin_a[ia]*e_n)
                dv_vec = np.array([dv_xy[0], dv_xy[1], 0.0])
                v_dep = v_dro + dv_vec
                s0 = np.concatenate([r_dep, v_dep])

                try:
                    sol = solve_ivp(cr3bp_eom, [0, t_max], s0,
                                    method='DOP853', rtol=1e-10, atol=1e-10,
                                    t_eval=t_eval_fixed,
                                    events=COLLISION_EVENTS)
                except Exception:
                    continue
                if sol.status == -1 or len(sol.t) < 5:
                    continue

                # positions at integration output points
                xy = sol.y[:2, :].T          # (N,2)
                dists, idxs = ro_tree.query(xy)

                # local minima below threshold  (also cap total ΔV)
                ns = len(dists)
                for k in range(1, ns-1):
                    if (dists[k] < dist_threshold
                            and dists[k] <= dists[k-1]
                            and dists[k] <= dists[k+1]):
                        ri = idxs[k]
                        v_arr = sol.y[3:, k]
                        dv2 = float(np.linalg.norm(ro_pts[ri, 3:] - v_arr))
                        tot = float(dv_mag) + dv2
                        if tot > 1.5:      # skip obviously bad
                            continue
                        candidates.append({
                            'dep_idx': i_dep,
                            't_dep':   float(dro_t[i_dep]),
                            'alpha':   float(alpha),
                            'dv_mag':  float(dv_mag),
                            'T':       float(sol.t[k]),
                            't_ins':   float(ro_t[ri]),
                            'dv1':     float(dv_mag),
                            'dv2':     dv2,
                            'total_dv': tot,
                            'min_dist': float(dists[k]),
                            'dep_state': dep.tolist(),
                        })

        if verbose and (i_dep+1) % max(1, n_dep//6) == 0:
            el = time_mod.time()-t0
            pct = cnt / total * 100
            rate = cnt / max(el, 1e-9)
            eta = (total-cnt) / max(rate, 1e-9)
            print(f"  {pct:5.1f}%  {len(candidates):5d} cands  "
                  f"{el:.0f}s elapsed  ETA {eta:.0f}s", flush=True)

    elapsed = time_mod.time() - t0
    if verbose:
        print(f"  DONE  {len(candidates)} candidates in {elapsed:.1f}s", flush=True)
    return candidates, ro_sol


# ============================================================
# Candidate filtering / clustering
# ============================================================
def cluster_candidates(candidates, max_total_dv=1.5, n_max=30):
    """Keep diverse, low-ΔV candidates."""
    filt = [c for c in candidates if c['total_dv'] < max_total_dv]
    filt.sort(key=lambda c: c['total_dv'])
    if not filt:
        return []

    selected = [filt[0]]
    for c in filt[1:]:
        close = False
        for s in selected:
            if (abs(c['T'] - s['T']) < 0.5
                    and abs(c['alpha'] - s['alpha']) < 0.2
                    and abs(c['t_dep'] - s['t_dep']) < 0.15 * max(1, abs(s['t_dep']))):
                close = True
                break
        if not close:
            selected.append(c)
        if len(selected) >= n_max:
            break
    return selected


# ============================================================
# OPTIMIZATION PHASE  — fast root-finding approach
# ============================================================
def _propagate_transfer(r_dep, v_dro, e_t, e_n, alpha, dv_mag, T):
    """Propagate a transfer arc; return final state or None on failure."""
    dv_xy = dv_mag * (np.cos(alpha)*e_t + np.sin(alpha)*e_n)
    v_dep = v_dro + np.array([dv_xy[0], dv_xy[1], 0.0])
    s0 = np.concatenate([r_dep, v_dep])
    try:
        sol = solve_ivp(cr3bp_eom, [0, T], s0,
                        method='DOP853', rtol=1e-12, atol=1e-12,
                        max_step=max(0.02, T/500))
        return sol.y[:, -1]
    except Exception:
        return None


def _refine_root(r_dep, v_dro, e_t, e_n, alpha0, dvm0, T, tins, ro_sol, ro_period):
    """Solve for (alpha, dv_mag) satisfying position-matching via fsolve."""
    from scipy.optimize import fsolve
    ro = ro_sol.sol(tins % ro_period)

    def resid(y):
        a, dm = y
        if dm < 1e-6:
            return [1e6, 1e6]
        sf = _propagate_transfer(r_dep, v_dro, e_t, e_n, a, dm, T)
        if sf is None:
            return [1e6, 1e6]
        return [sf[0] - ro[0], sf[1] - ro[1]]

    try:
        sol, info, ier, msg = fsolve(resid, [alpha0, dvm0], full_output=True)
        if ier == 1 and sol[1] > 0:
            # verify
            sf = _propagate_transfer(r_dep, v_dro, e_t, e_n, sol[0], sol[1], T)
            if sf is not None:
                pe = np.linalg.norm(sf[:2] - ro[:2])
                if pe < 1e-6:
                    dv2 = np.linalg.norm(ro[3:] - sf[3:])
                    return sol[0], sol[1], pe, dv2
    except Exception:
        pass
    return None


def optimize_candidate(cand, ro_sol, ro_period, verbose=False):
    """
    Fast optimisation via root-finding grid:
      1. At search (T, t_ins), solve exact (alpha, dv_mag) via fsolve
      2. Scan a small grid around (T, t_ins) to find lower-ΔV solution
    """
    dep = np.array(cand['dep_state'])
    r_dep, v_dro = dep[:3], dep[3:]
    e_t, e_n = _tn_frame(v_dro)

    T0 = cand['T']
    tins0 = cand['t_ins']
    alpha0 = cand['alpha']
    dvm0 = cand['dv_mag']
    n_eval = [0]

    best = None

    # grid of (T, t_ins) perturbations around the search value
    dT_vals = T0 * np.array([0.0, -0.02, 0.02, -0.05, 0.05, -0.1, 0.1])
    dt_vals = np.array([0.0, -0.05, 0.05, -0.15, 0.15])
    T_grid = T0 + dT_vals
    tins_grid = tins0 + dt_vals

    for T in T_grid:
        if T < 0.05:
            continue
        for tins in tins_grid:
            n_eval[0] += 1
            result = _refine_root(r_dep, v_dro, e_t, e_n,
                                  alpha0, dvm0, T, tins, ro_sol, ro_period)
            if result is not None:
                a, dm, pe, dv2 = result
                total = abs(dm) + dv2
                if best is None or total < best['total_dv']:
                    best = {
                        'alpha': float(a),
                        'dv_mag': float(dm),
                        'T': float(T),
                        't_ins': float(tins % ro_period),
                        'dv1': float(abs(dm)),
                        'dv2': float(dv2),
                        'total_dv': float(total),
                        'pos_error': float(pe),
                    }

    if best is None:
        if verbose:
            print(f"    [FAIL] no root found  ({n_eval[0]} grid pts)")
        return None

    best['success'] = best['pos_error'] < 1e-5
    best['t_dep'] = cand['t_dep']
    best['dep_state'] = cand['dep_state']
    best['n_eval'] = n_eval[0]

    if verbose:
        tag = 'OK' if best['success'] else 'FAIL'
        print(f"    [{tag}] ΔV={best['total_dv']:.6f} "
              f"(Δv1={best['dv1']:.4f}  Δv2={best['dv2']:.4f})  "
              f"T={best['T']*TU:.1f}d  pos_err={best['pos_error']:.1e}  "
              f"({n_eval[0]} pts)", flush=True)
    return best


# ============================================================
# Trajectory classification
# ============================================================
def classify_and_get_trajectory(opt, ro_sol, ro_period):
    """
    Propagate the optimised transfer arc, classify type, return trajectory data.
    """
    dep = np.array(opt['dep_state'])
    r_dep, v_dro = dep[:3], dep[3:]
    e_t, e_n = _tn_frame(v_dro)
    alpha, dv_mag, T = opt['alpha'], opt['dv_mag'], opt['T']

    dv_xy = dv_mag * (np.cos(alpha)*e_t + np.sin(alpha)*e_n)
    v_dep = v_dro + np.array([dv_xy[0], dv_xy[1], 0.0])
    s0 = np.concatenate([r_dep, v_dep])

    sol = solve_ivp(cr3bp_eom, [0, T], s0,
                    method='DOP853', rtol=1e-12, atol=1e-12,
                    max_step=0.005, dense_output=True)
    nt = 3000
    ts = np.linspace(0, T, nt)
    traj = sol.sol(ts).T

    r_moon_dist = np.sqrt((traj[:, 0]-1+MU)**2 + traj[:, 1]**2)
    r_bary_dist = np.sqrt(traj[:, 0]**2 + traj[:, 1]**2)

    max_r = float(np.max(r_bary_dist))
    min_r_moon = float(np.min(r_moon_dist))
    T_days = T * TU

    if T_days < 25:
        ttype = 'direct'
    elif max_r > 2.5:
        ttype = 'external'
    elif min_r_moon < 0.08:
        ttype = 'LGA'
    elif T_days > 40:
        ttype = 'external'
    else:
        ttype = 'intermediate'

    # Arrival state on RO
    ro_state_arr = ro_sol.sol(opt['t_ins'] % ro_period)

    return {
        'type': ttype,
        'T_days': T_days,
        'max_r': max_r,
        'min_r_moon': min_r_moon,
        'trajectory': traj,     # (nt,6)
        't_traj': ts,
        'dv1_vec': np.array([dv_xy[0], dv_xy[1], 0.0]),
        'dep_pos': r_dep.copy(),
        'arr_pos': ro_state_arr[:3].copy(),
    }


# ============================================================
# Plotting
# ============================================================
def plot_solution_plane(results, pair_name, outdir):
    """Plot transfer-time vs total-ΔV (solution plane)."""
    if not results:
        return
    Tdays = [r['T']*TU for r in results]
    dvtot = [r['total_dv']*VU for r in results]

    colors = {'direct': 'tab:blue', 'LGA': 'tab:green',
              'external': 'tab:red', 'intermediate': 'tab:orange'}
    labels_placed = set()

    fig, ax = plt.subplots(figsize=(10, 6))
    for r, td, dv in zip(results, Tdays, dvtot):
        c = colors.get(r.get('class', 'intermediate'), 'gray')
        lbl = r.get('class', 'intermediate')
        ax.scatter(td, dv, c=c, s=30, zorder=3,
                   label=lbl if lbl not in labels_placed else '')
        labels_placed.add(lbl)
    ax.set_xlabel('Transfer time (days)')
    ax.set_ylabel('Total Δv (m/s)')
    ax.set_title(f'Solution plane — {pair_name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(str(Path(outdir) / f'solution_plane_{_safe_filename(pair_name)}.png'),
                dpi=150)
    plt.close(fig)


def plot_sample_transfers(classified, dro_state, dro_period,
                          ro_state, ro_period, pair_name, outdir):
    """Plot a few representative transfer trajectories in the rotating frame."""
    # Group by type, pick the best (lowest ΔV) per type
    by_type = {}
    for c in classified:
        tt = c['type']
        if tt not in by_type or c['opt']['total_dv'] < by_type[tt]['opt']['total_dv']:
            by_type[tt] = c

    if not by_type:
        return

    # Propagate DRO and RO for background
    _, dro_orbit, _ = sample_orbit(dro_state, dro_period, 500)
    _, ro_orbit,  _ = sample_orbit(ro_state,  ro_period,  1000)

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.plot(dro_orbit[:, 0], dro_orbit[:, 1], 'b-', lw=0.8, label='DRO')
    ax.plot(ro_orbit[:, 0], ro_orbit[:, 1], 'r-', lw=0.8, label='RO')

    # Earth and Moon
    ax.plot(-MU, 0, 'bo', ms=8, label='Earth')
    ax.plot(1-MU, 0, 'ko', ms=5, label='Moon')

    colors_t = {'direct': 'tab:blue', 'LGA': 'tab:green',
                'external': 'tab:red', 'intermediate': 'tab:orange'}
    for tt, c in by_type.items():
        traj = c['trajectory']
        col = colors_t.get(tt, 'gray')
        ax.plot(traj[:, 0], traj[:, 1], '-', color=col, lw=1.5,
                label=f"{tt} (ΔV={c['opt']['total_dv']*VU:.0f} m/s, "
                      f"T={c['opt']['T']*TU:.1f}d)")
        ax.plot(traj[0, 0], traj[0, 1], 'o', color=col, ms=6)
        ax.plot(traj[-1, 0], traj[-1, 1], 's', color=col, ms=6)

    ax.set_xlabel('x (ND)')
    ax.set_ylabel('y (ND)')
    ax.set_title(f'Transfer trajectories — {pair_name}')
    ax.set_aspect('equal')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(str(Path(outdir) / f'transfers_{_safe_filename(pair_name)}.png'),
                dpi=150)
    plt.close(fig)


# ============================================================
# Load Phase 1 data
# ============================================================
def load_phase1_data():
    """Load DRO and RO target orbits from Phase 1 output."""
    base = Path(__file__).resolve().parent.parent / 'output'

    with open(base / 'phase1_dro' / 'dro_targets.json') as f:
        dro_data = json.load(f)

    dro_21 = dro_data['dro_21']
    dro_31 = dro_data['dro_31']

    with open(base / 'phase1_ro' / '3_2_target.json') as f:
        ro_32 = json.load(f)
    with open(base / 'phase1_ro' / '3_1_target.json') as f:
        ro_31 = json.load(f)

    return {
        '2:1 DRO': {'state': np.array(dro_21['state']),
                     'period': dro_21['period']},
        '3:1 DRO': {'state': np.array(dro_31['state']),
                     'period': dro_31['period']},
        '3:2 RO':  {'state': np.array(ro_32['state']),
                     'period': ro_32['period']},
        '3:1 RO':  {'state': np.array(ro_31['state']),
                     'period': ro_31['period']},
    }


# ============================================================
# Main
# ============================================================
TRANSFER_PAIRS = [
    ('2:1 DRO', '3:2 RO'),
    ('2:1 DRO', '3:1 RO'),
    ('3:1 DRO', '3:2 RO'),
    ('3:1 DRO', '3:1 RO'),
]


def process_one_pair(dro_name, ro_name, orbits, outdir,
                     n_dep=36, n_alpha=72,
                     dv_mags=(0.05, 0.1, 0.2, 0.3, 0.5),
                     t_max=25.0, dist_thresh=0.05):
    """Full pipeline for one DRO->RO pair: search -> cluster -> optimize -> classify."""
    pair_name = f"{dro_name} -> {ro_name}"
    dro = orbits[dro_name]
    ro  = orbits[ro_name]

    # ---------- search ----------
    raw_cands, ro_sol = search_transfers(
        dro['state'], dro['period'],
        ro['state'],  ro['period'],
        pair_name=pair_name,
        n_dep=n_dep, n_alpha=n_alpha,
        dv_mags=dv_mags,
        t_max=t_max, dist_threshold=dist_thresh,
        verbose=True,
    )

    if not raw_cands:
        print(f"  *** NO candidates found for {pair_name}")
        return []

    # ---------- cluster ----------
    sel = cluster_candidates(raw_cands, max_total_dv=1.5, n_max=60)
    print(f"\n  Clustered -> {len(sel)} candidates for optimisation", flush=True)

    # ---------- optimise ----------
    print(f"\n  OPTIMISING  ({pair_name})", flush=True)
    opt_results = []
    for ic, cand in enumerate(sel):
        tag = f"    [{ic+1}/{len(sel)}]"
        res = optimize_candidate(cand, ro_sol, ro['period'], verbose=True)
        if res is not None and res['success']:
            opt_results.append(res)

    print(f"\n  Optimisation: {len(opt_results)} converged / {len(sel)} tried")

    if not opt_results:
        print(f"  *** No converged solutions for {pair_name}")
        return []

    # ---------- classify ----------
    print(f"\n  CLASSIFYING trajectories …")
    classified = []
    for res in opt_results:
        info = classify_and_get_trajectory(res, ro_sol, ro['period'])
        res['class'] = info['type']
        classified.append({
            'opt': res,
            'type': info['type'],
            'T_days': info['T_days'],
            'max_r': info['max_r'],
            'min_r_moon': info['min_r_moon'],
            'trajectory': info['trajectory'],
        })

    # summary
    from collections import Counter
    type_counts = Counter(c['type'] for c in classified)
    print(f"  Transfer types: {dict(type_counts)}")
    for c in sorted(classified, key=lambda c: c['opt']['total_dv'])[:5]:
        print(f"    {c['type']:12s}  ΔV={c['opt']['total_dv']*VU:7.1f} m/s  "
              f"T={c['T_days']:6.1f} d  r_max={c['max_r']:.2f}  "
              f"r_moon_min={c['min_r_moon']:.4f}")

    # ---------- save ----------
    save_data = []
    for c in classified:
        d = dict(c['opt'])
        d['class'] = c['type']
        d['T_days'] = c['T_days']
        d['max_r']  = c['max_r']
        d['min_r_moon'] = c['min_r_moon']
        save_data.append(d)

    fname = _safe_filename(pair_name)
    with open(Path(outdir) / f'{fname}_results.json', 'w') as f:
        json.dump(save_data, f, indent=2)

    # ---------- plot ----------
    plot_solution_plane(opt_results, pair_name, outdir)
    plot_sample_transfers(classified,
                          dro['state'], dro['period'],
                          ro['state'], ro['period'],
                          pair_name, outdir)

    return classified


def _tee_print(*args, _logfh=None, **kwargs):
    """Print to both stdout and log file."""
    import builtins
    builtins.print(*args, **kwargs)
    if _logfh is not None:
        builtins.print(*args, **kwargs, file=_logfh, flush=True)


def main():
    # CLI: python phase2_transfer_search.py [pair_index]
    # pair_index: 0-3 for specific pair, omit or -1 for all
    pair_idx = -1
    if len(sys.argv) > 1:
        pair_idx = int(sys.argv[1])

    outdir = Path(__file__).resolve().parent.parent / 'output' / 'phase2_transfer'
    outdir.mkdir(parents=True, exist_ok=True)

    # Open log file for tee
    logpath = outdir.parent / 'phase2_log2.txt'
    logfh = open(logpath, 'w', encoding='utf-8', buffering=1)

    def tprint(*a, **kw):
        _tee_print(*a, _logfh=logfh, **kw)

    tprint("="*60)
    tprint("Phase 2: Two-Impulse Transfer Design (CR3BP)")
    tprint("="*60)

    orbits = load_phase1_data()
    for name, orb in orbits.items():
        tprint(f"  {name:10s}  x0={orb['state'][0]:.6f}  "
               f"T={orb['period']:.6f} ({orb['period']*TU:.2f} d)")

    if 0 <= pair_idx < len(TRANSFER_PAIRS):
        pairs_to_run = [TRANSFER_PAIRS[pair_idx]]
        tprint(f"\n  Running pair {pair_idx}: {pairs_to_run[0][0]} -> {pairs_to_run[0][1]}")
    else:
        pairs_to_run = TRANSFER_PAIRS
        tprint(f"\n  Running all {len(TRANSFER_PAIRS)} pairs")

    all_results = {}
    for dro_name, ro_name in pairs_to_run:
        pair_name = f"{dro_name} -> {ro_name}"

        # --- Skip if result JSON already exists ---
        fname = _safe_filename(pair_name)
        result_file = Path(outdir) / f'{fname}_results.json'
        if result_file.exists():
            tprint(f"\n  [SKIP] {pair_name}: {result_file.name} already exists")
            with open(result_file) as f:
                saved = json.load(f)
            tprint(f"         {len(saved)} solutions loaded from cache")
            all_results[pair_name] = saved
            continue

        try:
            results = process_one_pair(dro_name, ro_name, orbits, str(outdir),
                                       n_dep=24, n_alpha=48,
                                       dv_mags=(0.1, 0.2, 0.4),
                                       t_max=25.0, dist_thresh=0.03)
        except Exception as e:
            tprint(f"\n  [ERROR] {pair_name}: {e}")
            import traceback; traceback.print_exc()
            all_results[pair_name] = []
            continue

        all_results[pair_name] = results

        # incremental save: summary JSON after each pair
        summary_path = Path(outdir) / 'summary.json'
        summary = {}
        if summary_path.exists():
            with open(summary_path) as f:
                summary = json.load(f)
        if results:
            best = min(results, key=lambda c: c['opt']['total_dv'])
            summary[pair_name] = {
                'n_solutions': len(results),
                'best_dv': best['opt']['total_dv'],
                'best_dv_ms': best['opt']['total_dv'] * VU,
                'best_T_days': best['T_days'],
                'best_type': best['type'],
            }
        else:
            summary[pair_name] = {'n_solutions': 0}
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        tprint(f"\n  [SAVED] {pair_name} -> {summary_path}")

    # ---------- summary ----------
    tprint("\n" + "="*60)
    tprint("OVERALL SUMMARY")
    tprint("="*60)
    for pair_name, results in all_results.items():
        if isinstance(results, list) and len(results) == 0:
            tprint(f"  {pair_name}: no solutions")
            continue
        if isinstance(results, list) and isinstance(results[0], dict) and 'opt' in results[0]:
            best = min(results, key=lambda c: c['opt']['total_dv'])
            tprint(f"  {pair_name}")
            tprint(f"    {len(results)} solutions found")
            tprint(f"    Best: dV={best['opt']['total_dv']*VU:.1f} m/s  "
                   f"T={best['T_days']:.1f} d  type={best['type']}")
        else:
            # Loaded from JSON (flat dict list)
            best = min(results, key=lambda c: c['total_dv'])
            tprint(f"  {pair_name}")
            tprint(f"    {len(results)} solutions (cached)")
            tprint(f"    Best: dV={best['total_dv']*VU:.1f} m/s  "
                   f"T={best.get('T_days', best['T']*TU):.1f} d  "
                   f"type={best.get('class','?')}")

    tprint("\nDone. Results saved to:", outdir)
    logfh.close()


if __name__ == '__main__':
    main()
