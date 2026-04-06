"""
DRO → GEO 网格搜索

参考 grid_search.py，将目标从 RO（周期轨道）替换为 GEO（固定半径球面）。

到达条件: 轨迹穿越 GEO 球面（距地心 r_GEO）
速度匹配: 轨迹速度与 GEO 圆速度之差

运行: python scripts/transfer/grid_search_dro_geo.py

Windows 多进程需要 ``if __name__ == "__main__"``。
"""

import json
import os
import sys
import numpy as np
from pathlib import Path
from fontTools.misc.timeTools import timestampNow
from tqdm.auto import tqdm

import e2m2e
from e2m2e.transfer import load_orbit_from_json
from scripts.utils.common import DU, MU, TU
from scripts.utils.geo import (
    R_GEO,
    EARTH_CENTER,
    V_CIRCULAR_GEO,
    compute_departure_velocity,
    check_collision,
    detect_geo_sphere_crossing,
    find_closest_approach_to_geo,
    compute_geo_dv2,
)


def forward_integrate(dynamics, initial_state, transfer_time, dt):
    n_steps = max(int(transfer_time / dt) + 1, 2)
    t_eval = np.linspace(0.0, transfer_time, n_steps)
    result = dynamics.propagate(
        initial_state=initial_state,
        t_span=(0.0, transfer_time),
        t_eval=t_eval,
        with_stm=False,
        with_jacobi=False,
    )
    return result["states"], result["time"]


def sample_departure_points(orbit, n_departure):
    times = orbit.times
    states = orbit.states
    n_pts = len(times)
    n = int(n_departure)
    if n > n_pts:
        raise ValueError(f"n_departure ({n}) > orbit points ({n_pts})")
    if n == 1:
        idx = np.array([0], dtype=int)
    else:
        idx = (
            np.arange(n, dtype=float) * (n_pts - 1) / (n - 1)
        ).round().astype(int)
    return states[idx].copy(), times[idx].copy()


def search_single_departure(
    departure_state,
    departure_time,
    dynamics,
    mu,
    alpha_grid,
    max_transfer_time,
    integration_dt,
    earth_radius,
    moon_radius,
    geo_threshold,
):
    results = []
    for alpha in alpha_grid:
        new_vel = compute_departure_velocity(departure_state, alpha)
        dv_departure = float(np.linalg.norm(new_vel - departure_state[3:6]))
        initial_state = np.concatenate([departure_state[:3], new_vel])

        try:
            traj_states, traj_times = forward_integrate(
                dynamics, initial_state, max_transfer_time, integration_dt
            )
        except Exception:
            results.append({
                "success": False,
                "departure_state": departure_state.tolist(),
                "departure_time": float(departure_time),
                "alpha": float(alpha),
                "status": "integration_failed",
                "dv_departure": dv_departure,
                "dv_insertion": None,
            })
            continue

        collision, body, col_idx = check_collision(
            traj_states, mu, earth_radius, moon_radius
        )

        crossed, cross_idx, _ = detect_geo_sphere_crossing(traj_states)
        min_sphere_dist, closest_idx = find_closest_approach_to_geo(traj_states)
        dv_insertion = compute_geo_dv2(traj_states[closest_idx])

        if crossed:
            dv_insertion = compute_geo_dv2(traj_states[cross_idx])
            transfer_time = float(traj_times[cross_idx])
            status = "success"
        elif min_sphere_dist < geo_threshold:
            transfer_time = float(traj_times[closest_idx])
            status = "success"
        else:
            transfer_time = float(traj_times[-1])
            status = "no_crossing"

        if collision:
            status = "collision"

        results.append({
            "success": True,
            "departure_state": departure_state.tolist(),
            "departure_time": float(departure_time),
            "alpha": float(alpha),
            "transfer_time": transfer_time,
            "geo_crossing_found": crossed,
            "geo_crossing_idx": int(cross_idx) if crossed else None,
            "min_distance_to_geo": min_sphere_dist,
            "closest_geo_idx": int(closest_idx),
            "dv_departure": dv_departure,
            "dv_insertion": dv_insertion,
            "collision_found": collision,
            "collision_body": body,
            "collision_idx": int(col_idx) if collision else None,
            "status": status,
        })

    return results


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent

    # =====================================================================
    # 搜索参数配置
    # =====================================================================
    dro_file = project_root / "output/dro/dro_31_3857864736.json"

    n_departure = 200
    n_alpha = 100
    alpha_min = 0.5
    alpha_max = 2.5
    max_transfer_time = 100.0 / TU

    integration_dt = 1.0 / (24.0 * TU)

    earth_radius = 200.0 / DU
    moon_radius = 100.0 / DU
    geo_threshold = 100.0 / DU

    # =====================================================================
    # 初始化
    # =====================================================================
    for _k in [
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "GOTO_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
    ]:
        os.environ[_k] = "1"

    system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = integration_dt

    dro_orbit = load_orbit_from_json(str(dro_file))

    departure_states, departure_times = sample_departure_points(dro_orbit, n_departure)
    alpha_grid = np.linspace(alpha_min, alpha_max, n_alpha)

    print("\n" + "=" * 70)
    print("DRO → GEO 网格搜索")
    print("=" * 70)
    print(f"DRO 文件: {dro_file}")
    print(f"GEO 半径: {R_GEO:.6f} DU ({R_GEO * DU:.0f} km)")
    print(f"GEO 圆速度: {V_CIRCULAR_GEO:.4f} VU ({V_CIRCULAR_GEO * 1023.23281:.0f} m/s)")
    print(f"α 范围: [{alpha_min}, {alpha_max}], n={n_alpha}")
    print(f"出发点: {n_departure}")
    print(f"最大转移时间: {max_transfer_time:.4f} TU ({max_transfer_time * TU:.1f} days)")
    print(f"GEO 接近阈值: {geo_threshold:.6f} DU ({geo_threshold * DU:.0f} km)")

    # =====================================================================
    # 搜索
    # =====================================================================
    all_results = []
    total_steps = n_departure * n_alpha
    pbar = tqdm(total=total_steps, desc="网格搜索", file=sys.stderr, dynamic_ncols=True)

    for i, (dep_state, dep_time) in enumerate(zip(departure_states, departure_times)):
        results = search_single_departure(
            dep_state, dep_time, dynamics, MU,
            alpha_grid, max_transfer_time, integration_dt,
            earth_radius, moon_radius, geo_threshold,
        )
        for r in results:
            r["departure_time_index"] = i
        all_results.extend(results)
        pbar.update(n_alpha)
        pbar.set_postfix_str(f"dep={i}")

    pbar.close()

    # =====================================================================
    # 筛选可行解
    # =====================================================================
    def is_feasible(r):
        if r.get("collision_found", False):
            return False
        return r.get("status") == "success"

    for r in all_results:
        r["is_feasible"] = is_feasible(r)

    feasible = [r for r in all_results if r["is_feasible"]]

    print(f"\n搜索完成: {len(all_results)} 候选解, {len(feasible)} 可行解")

    if feasible:
        best = min(feasible, key=lambda r: r["dv_departure"] + (r.get("dv_insertion") or 1e10))
        print(f"最优可行解: α={best['alpha']:.4f}, dv_dep={best['dv_departure']:.4f}, "
              f"dv_ins={best.get('dv_insertion', 'N/A')}, "
              f"T={best['transfer_time']:.4f} TU ({best['transfer_time'] * TU:.1f} days)")

    # =====================================================================
    # 保存
    # =====================================================================
    output_dir = project_root / "output/transfer"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / (
        f"search_dro_geo_{n_departure}-{n_alpha}-"
        f"{alpha_min:g}-{alpha_max:g}-{max_transfer_time:.4f}_{timestampNow()}.json"
    )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存: {output_file}")


if __name__ == "__main__":
    main()
