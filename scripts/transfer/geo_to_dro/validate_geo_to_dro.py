"""
技术预研：验证 GEO → DRO 转移轨道搜索的可行性

测试内容：
1. 在 CR3BP 旋转系中生成 GEO 近似圆轨道
2. 验证 TransferSearch 的出发速度模型在 GEO 上的行为
3. 用少量网格点测试正向积分轨迹是否能到达月球附近
4. 测试 TransferSearch(departure=GEO, arrival=DRO) 的网格搜索

运行: python scripts/transfer/geo_to_dro/validate_geo_to_dro.py
"""

import numpy as np
import sys
from pathlib import Path

# 添加项目根目录到 path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

from scripts.utils.common import DU, MU, TU, VU
from scripts.utils.geo import (
    R_GEO,
    V_CIRCULAR_GEO,
    T_GEO,
    EARTH_CENTER,
    geo_circular_velocity_rotating,
)

import e2m2e
from e2m2e.core import CR3BP_System, CR3BP_Dynamics
from e2m2e.core.orbit import Orbit
from e2m2e.transfer import TransferSearch, load_orbit_from_json


def generate_geo_orbit(n_points: int = 500) -> Orbit:
    """在 CR3BP 旋转系中生成 GEO 近似圆轨道。

    GEO 被建模为以地心为圆心、半径为 R_GEO 的圆轨道。
    速度通过 geo_circular_velocity_rotating 计算（包含 Coriolis 修正）。

    注意：这不是 CR3BP 精确周期轨道，而是两体近似。对于搜索阶段的粗筛足够。
    """
    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    states = np.zeros((n_points, 6))

    for i, th in enumerate(theta):
        # 位置：以地心为圆心
        x = EARTH_CENTER[0] + R_GEO * np.cos(th)
        y = R_GEO * np.sin(th)
        z = 0.0

        # 速度：旋转系下的圆轨道速度
        pos = np.array([x, y, z])
        vel = geo_circular_velocity_rotating(pos)

        states[i] = [x, y, z, vel[0], vel[1], vel[2]]

    times = np.linspace(0, T_GEO, n_points, endpoint=False)

    orbit = Orbit(states, times)
    orbit.period = T_GEO
    return orbit


def test_velocity_model():
    """测试 1：出发速度模型在 GEO 上的物理行为"""
    print("\n" + "=" * 70)
    print("测试 1：GEO 出发速度模型分析")
    print("=" * 70)

    geo_orbit = generate_geo_orbit(n_points=100)

    # 选取几个代表性出发点
    test_indices = [0, 25, 50, 75]  # θ = 0°, 90°, 180°, 270°

    for idx in test_indices:
        state = geo_orbit.states[idx]
        pos = state[:3]
        vel = state[3:]

        # 几何分析
        r_from_origin = np.linalg.norm(pos)
        r_from_earth = np.linalg.norm(pos - EARTH_CENTER)
        v_mag = np.linalg.norm(vel)

        # 切向/径向分解（与 _compute_departure_velocity 一致）
        r_xy = np.sqrt(pos[0] ** 2 + pos[1] ** 2)
        tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
        radial = pos / r_from_origin

        v_rad = np.dot(vel, radial)
        v_tan = np.dot(vel, tangential)

        print(f"\n  出发点 idx={idx} (θ={idx * 3.6:.0f}°):")
        print(f"    位置: [{pos[0]:.6f}, {pos[1]:.6f}, {pos[2]:.6f}] DU")
        print(f"    速度: [{vel[0]:.6f}, {vel[1]:.6f}, {vel[2]:.6f}] VU")
        print(f"    |v| = {v_mag:.4f} VU = {v_mag * VU:.1f} m/s")
        print(f"    到原点距离: {r_from_origin:.6f} DU = {r_from_origin * DU:.0f} km")
        print(f"    到地心距离: {r_from_earth:.6f} DU = {r_from_earth * DU:.0f} km")
        print(f"    v_radial = {v_rad:.4f} VU, v_tangential = {v_tan:.4f} VU")

        # 测试不同 alpha 值
        for alpha in [1.0, 1.2, 1.5, 2.0]:
            new_vel = v_rad * radial + alpha * v_tan * tangential
            new_speed = np.linalg.norm(new_vel)
            dv = np.linalg.norm(new_vel - vel)
            print(f"    alpha={alpha:.1f}: |v_new|={new_speed:.3f} VU = {new_speed * VU:.0f} m/s, "
                  f"Δv={dv:.3f} VU = {dv * VU:.0f} m/s")


def test_forward_integration():
    """测试 2：从 GEO 出发的正向积分"""
    print("\n" + "=" * 70)
    print("测试 2：GEO 出发正向积分测试")
    print("=" * 70)

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12

    geo_orbit = generate_geo_orbit(n_points=100)

    # 月球位置
    moon_pos = np.array([1.0 - MU, 0.0, 0.0])

    # 从 θ=0 出发（GEO 上最远离月球的点），测试不同 alpha
    state = geo_orbit.states[0].copy()
    pos = state[:3]
    vel = state[3:]

    r_xy = np.sqrt(pos[0] ** 2 + pos[1] ** 2)
    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)
    v_rad = np.dot(vel, radial)
    v_tan = np.dot(vel, tangential)

    transfer_time = 30.0  # ~130 天
    dt = 0.01

    print(f"\n出发状态: pos=[{pos[0]:.6f}, {pos[1]:.6f}], "
          f"|vel|={np.linalg.norm(vel):.4f} VU")
    print(f"积分时间: {transfer_time:.1f} TU = {transfer_time * TU:.1f} 天")
    print(f"到月球距离: {np.linalg.norm(pos - moon_pos):.4f} DU")
    print()

    for alpha in [1.0, 1.2, 1.4, 1.6, 1.8, 2.0]:
        new_vel = v_rad * radial + alpha * v_tan * tangential
        initial_state = np.concatenate([pos, new_vel])

        n_steps = max(int(transfer_time / dt) + 1, 2)
        t_eval = np.linspace(0, transfer_time, n_steps)

        result = dynamics.propagate(
            initial_state=initial_state,
            t_span=(0.0, transfer_time),
            t_eval=t_eval,
            with_stm=False,
            with_jacobi=False,
        )

        traj = result["states"]

        # 到月球的最小距离
        moon_dists = np.linalg.norm(traj[:, :3] - moon_pos, axis=1)
        min_moon_dist = np.min(moon_dists)
        min_moon_idx = np.argmin(moon_dists)

        # 到 DRO 区域的距离（DRO 大约在 x≈0.99 附近）
        x_max = np.max(traj[:, 0])
        x_min = np.min(traj[:, 0])

        # 碰撞检测
        earth_dists = np.linalg.norm(traj[:, :3] - EARTH_CENTER, axis=1)
        collision_earth = np.min(earth_dists) < 200.0 / DU
        collision_moon = min_moon_dist < 100.0 / DU

        status = "OK"
        if collision_earth:
            status = "撞地"
        elif collision_moon:
            status = "撞月"

        print(f"  alpha={alpha:.1f}: 月球最近={min_moon_dist:.4f} DU = {min_moon_dist * DU:.0f} km "
              f"(t={result['time'][min_moon_idx]:.2f} TU = {result['time'][min_moon_idx] * TU:.1f} 天), "
              f"x∈[{x_min:.4f}, {x_max:.4f}], 状态: {status}")


def test_transfer_search():
    """测试 3：TransferSearch(departure=GEO, arrival=DRO) 网格搜索"""
    print("\n" + "=" * 70)
    print("测试 3：TransferSearch(GEO→DRO) 小规模网格搜索")
    print("=" * 70)

    system = CR3BP_System(mu=MU, primary="earth", secondary="moon")
    dynamics = CR3BP_Dynamics(system=system)
    dynamics.integrator = "DOP853"
    dynamics.rtol = 1e-12
    dynamics.atol = 1e-12
    dynamics.max_step = 1.0 / (24.0 * TU)

    # 加载 DRO 轨道
    dro_file = project_root / "output/dro/dro_31_3857117998.json"
    if not dro_file.exists():
        # 尝试其他文件
        dro_dir = project_root / "output/dro"
        dro_files = list(dro_dir.glob("dro_31_*.json"))
        if dro_files:
            dro_file = dro_files[0]
        else:
            print("错误：找不到 DRO 轨道文件！")
            return

    dro_orbit = load_orbit_from_json(str(dro_file))
    # 设置 DRO 周期
    import json
    with open(dro_file) as f:
        dro_data = json.load(f)
    dro_orbit.period = dro_data.get("properties", {}).get("period", None)

    assert dro_orbit.period is not None, "DRO 轨道周期缺失"
    print(f"DRO 轨道: {dro_orbit.states.shape[0]} 个状态点, "
          f"周期={dro_orbit.period:.6f} TU = {dro_orbit.period * TU:.3f} 天")
    print(f"DRO x 范围: [{dro_orbit.states[:, 0].min():.6f}, {dro_orbit.states[:, 0].max():.6f}]")

    # 生成 GEO 轨道
    geo_orbit = generate_geo_orbit(n_points=200)
    geo_orbit.system = system

    assert geo_orbit.period is not None
    print(f"GEO 轨道: {geo_orbit.states.shape[0]} 个状态点, "
          f"周期={geo_orbit.period:.6f} TU = {geo_orbit.period * TU:.3f} 天")

    # 创建搜索器
    searcher = TransferSearch(dynamics)

    # 小规模测试：少量出发点，少量 alpha
    results = searcher.search(
        departure_orbit=geo_orbit,
        arrival_orbit=dro_orbit,
        alpha_min=1.0,
        alpha_max=2.0,
        n_alpha=20,
        n_departure=20,
        max_transfer_time=30.0,
        intersection_threshold=0.01,
        min_distance_threshold=500.0 / DU,
        collision_earth_radius=200.0 / DU,
        collision_moon_radius=100.0 / DU,
        integration_dt=0.01,
        verbose=True,
        n_workers=1,
        parallel_backend="threads",
    )

    feasible = searcher.get_feasible_results()

    print(f"\n搜索结果: {len(results)} 个候选解, {len(feasible)} 个可行解")

    if feasible:
        print("\n可行解摘要:")
        for i, r in enumerate(feasible[:10]):
            print(f"  #{i+1}: dep_idx={r.get('departure_time_index')}, "
                  f"alpha={r.get('alpha', 0):.4f}, "
                  f"T={r.get('transfer_time', 0):.2f} TU, "
                  f"dv_dep={r.get('dv_departure', 0):.4f} VU, "
                  f"min_dist={r.get('min_distance', float('inf')):.6f} DU = "
                  f"{r.get('min_distance', float('inf')) * DU:.0f} km, "
                  f"相交={r.get('intersection_found', False)}")
    else:
        print("\n没有找到可行解。分析所有结果的最小距离分布...")
        if results:
            min_dists = [r.get("min_distance", float("inf")) for r in results]
            min_dists = [d for d in min_dists if d != float("inf")]
            if min_dists:
                print(f"  最小距离范围: [{min(min_dists):.6f}, {max(min_dists):.6f}] DU")
                print(f"  最小距离范围: [{min(min_dists) * DU:.0f}, {max(min_dists) * DU:.0f}] km")
                print(f"  最佳 5 个:")
                sorted_results = sorted(results, key=lambda r: r.get("min_distance", float("inf")))
                for r in sorted_results[:5]:
                    md = r.get("min_distance", float("inf"))
                    print(f"    dep_idx={r.get('departure_time_index')}, "
                          f"alpha={r.get('alpha', 0):.4f}, "
                          f"T={r.get('transfer_time', 0):.2f} TU, "
                          f"min_dist={md:.6f} DU = {md * DU:.0f} km, "
                          f"碰撞={r.get('collision_found', False)}")


def main():
    print("GEO → DRO 转移轨道搜索可行性验证")
    print(f"GEO 参数: R={R_GEO:.6f} DU = {R_GEO * DU:.0f} km, "
          f"V_circ={V_CIRCULAR_GEO:.4f} VU = {V_CIRCULAR_GEO * VU:.1f} m/s, "
          f"T={T_GEO:.4f} TU = {T_GEO * TU:.3f} 天")

    test_velocity_model()
    test_forward_integration()
    test_transfer_search()

    print("\n" + "=" * 70)
    print("验证完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
