"""
测试 LEO/GEO → DRO 转移轨道工具函数
"""

import numpy as np
import pytest


class TestGeoUtils:
    """测试 GEO 工具函数。"""

    def test_geo_constants(self):
        from scripts.utils.common import VU
        from scripts.utils.geo import R_GEO, V_CIRCULAR_GEO, T_GEO, EARTH_CENTER, DU, MU

        # GEO 半径 ~42164 km
        assert abs(R_GEO * DU - 42164.0) < 1.0
        # 速度 ~3071 m/s
        assert abs(V_CIRCULAR_GEO * VU - 3071.0) < 5.0
        # 周期 ~1 天
        assert abs(T_GEO * 4.34811305 - 1.0) < 0.01
        # 地心在 [-mu, 0, 0]
        np.testing.assert_allclose(EARTH_CENTER, [-MU, 0.0, 0.0])

    def test_geo_circular_velocity_rotating(self):
        from scripts.utils.geo import geo_circular_velocity_rotating, EARTH_CENTER

        # θ=0: x = EARTH_CENTER[0] + R_GEO, y = 0
        pos = EARTH_CENTER + np.array([0.11, 0.0, 0.0])
        vel = geo_circular_velocity_rotating(pos)
        # 速度应该有 y 分量（逆行方向）
        assert abs(vel[1]) > 0
        # z 分量为零
        assert vel[2] == 0.0

    def test_compute_departure_velocity(self):
        from scripts.utils.geo import compute_departure_velocity

        # θ=0 位置: pos 沿 x 轴, vel 沿 y 轴
        state = np.array([0.1, 0.0, 0.0, 0.0, 1.0, 0.0])
        # alpha=1 不变
        v_new = compute_departure_velocity(state, 1.0)
        np.testing.assert_allclose(v_new, state[3:], atol=1e-12)
        # alpha=2 切向翻倍
        v_new2 = compute_departure_velocity(state, 2.0)
        np.testing.assert_allclose(v_new2, [0.0, 2.0, 0.0], atol=1e-12)

    def test_check_collision(self):
        from scripts.utils.geo import check_collision, EARTH_CENTER, DU

        # 靠近地心的状态
        states = np.array([[EARTH_CENTER[0] + 100 / DU, 0, 0, 0, 0, 0]])
        found, body, idx = check_collision(states, 0.01215, 200 / DU, 100 / DU)
        assert found
        assert body == "earth"

    def test_detect_geo_sphere_crossing(self):
        from scripts.utils.geo import detect_geo_sphere_crossing, R_GEO, EARTH_CENTER

        # 创建一条从 GEO 内到 GEO 外的轨迹
        n = 100
        states = np.zeros((n, 6))
        for i in range(n):
            t = i / (n - 1)
            r = R_GEO * (0.9 + 0.2 * t)  # 从 0.9*R_GEO 到 1.1*R_GEO
            states[i, :3] = EARTH_CENTER + np.array([r, 0, 0])

        crossed, idx, dist = detect_geo_sphere_crossing(states)
        assert crossed
        assert idx >= 0


class TestLeoUtils:
    """测试 LEO 工具函数。"""

    def test_leo_constants(self):
        from scripts.utils.leo import R_LEO, V_CIRCULAR_LEO, T_LEO, DU

        # LEO 半径 ~6771 km (6371 + 400)
        assert abs(R_LEO * DU - 6771.0) < 1.0
        # 速度 ~7.7 km/s
        v_ms = V_CIRCULAR_LEO * VU
        assert 7500 < v_ms < 8000
        # 周期 ~92 分钟 ≈ 0.064 天
        t_days = T_LEO * 4.34811305
        assert 0.05 < t_days < 0.07

    def test_leo_circular_velocity_rotating(self):
        from scripts.utils.leo import leo_circular_velocity_rotating, EARTH_CENTER, R_LEO

        # θ=0: 正 x 方向
        pos = EARTH_CENTER + np.array([R_LEO, 0, 0])
        vel = leo_circular_velocity_rotating(pos)
        # 应该有 y 分量
        assert abs(vel[1]) > 0
        assert vel[2] == 0.0

    def test_generate_leo_orbit_states(self):
        from scripts.utils.leo import generate_leo_orbit_states, EARTH_CENTER, R_LEO

        states = generate_leo_orbit_states(100)
        assert states.shape == (100, 6)

        # 检查所有点距地心距离 ≈ R_LEO
        dists = np.linalg.norm(states[:, :3] - EARTH_CENTER, axis=1)
        np.testing.assert_allclose(dists, R_LEO, rtol=1e-10)

        # z=0（平面轨道）
        np.testing.assert_allclose(states[:, 2], 0.0, atol=1e-15)


class TestGeoOrbitGeneration:
    """测试 GEO 轨道生成。"""

    def test_generate_geo_orbit(self):
        # 避免完整 import 循环，直接内联测试
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

        from scripts.utils.geo import R_GEO, EARTH_CENTER, geo_circular_velocity_rotating
        from e2m2e.core.orbit import Orbit

        n_points = 100
        theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
        states = np.zeros((n_points, 6))

        for i, th in enumerate(theta):
            x = EARTH_CENTER[0] + R_GEO * np.cos(th)
            y = R_GEO * np.sin(th)
            pos = np.array([x, y, 0.0])
            vel = geo_circular_velocity_rotating(pos)
            states[i] = [x, y, 0.0, vel[0], vel[1], vel[2]]

        times = np.linspace(0, 1.0, n_points, endpoint=False)
        orbit = Orbit(states, times)

        assert orbit.states.shape == (100, 6)

        # 检查距地心距离 ≈ R_GEO
        dists = np.linalg.norm(states[:, :3] - EARTH_CENTER, axis=1)
        np.testing.assert_allclose(dists, R_GEO, rtol=1e-10)

        # 平面轨道
        np.testing.assert_allclose(states[:, 2], 0.0, atol=1e-15)
