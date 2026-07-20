"""tod.commons.orbits 单元测试。

覆盖 orbits.py 中的纯函数：物理正确性、返回形状、边界条件。
"""

import numpy as np
import pytest

from tod.commons.constants import DU, MU
from tod.commons.orbits import (
    EARTH_CENTER,
    R_GEO,
    R_LEO,
    T_GEO,
    T_LEO,
    V_CIRCULAR_GEO,
    V_CIRCULAR_LEO,
    check_collision,
    compute_departure_velocity,
    compute_geo_dv2,
    geo_circular_velocity_rotating,
    generate_geo_orbit,
    generate_leo_orbit,
    leo_circular_velocity_rotating,
)


# ── geo_circular_velocity_rotating ─────────────────────────


class TestGeoCircularVelocityRotating:
    """验证旋转系下 GEO 圆轨道速度的物理正确性。"""

    def test_geo_point_velocity_magnitude(self):
        """GEO 圆轨道上一点的速度大小应接近 |V_CIRCULAR_GEO - position[0]|。"""
        pos = np.array([EARTH_CENTER[0] + R_GEO, 0.0, 0.0])
        v = geo_circular_velocity_rotating(pos)
        # 旋转系下圆轨道速度 = v_inertial - omega × r
        # v_inertial = [0, V_CIRCULAR_GEO, 0]
        # omega × r = [0, position[0], 0]
        # v_rotating = [0, V_CIRCULAR_GEO - position[0], 0]
        expected_mag = abs(V_CIRCULAR_GEO - pos[0])
        assert np.linalg.norm(v) == pytest.approx(expected_mag, rel=1e-10)

    def test_geo_point_velocity_direction(self):
        """GEO 圆轨道上 x 轴正方向点的速度应沿 y 方向。"""
        pos = np.array([EARTH_CENTER[0] + R_GEO, 0.0, 0.0])
        v = geo_circular_velocity_rotating(pos)
        assert abs(v[0]) < 1e-12  # x 分量应为 0
        assert abs(v[2]) < 1e-12  # z 分量应为 0

    def test_geo_point_at_90_degrees(self):
        """GEO 圆轨道上 y 轴正方向点的速度应沿 -x 方向（y 分量为 MU）。"""
        pos = np.array([EARTH_CENTER[0], R_GEO, 0.0])
        v = geo_circular_velocity_rotating(pos)
        # v_inertial = [-V_CIRCULAR_GEO, 0, 0]
        # omega_cross_r = [-R_GEO, -MU, 0]
        # v_rotating = [-V_CIRCULAR_GEO + R_GEO, MU, 0]
        assert v[1] == pytest.approx(MU, rel=1e-10)
        assert v[2] == pytest.approx(0.0, abs=1e-12)

    def test_near_earth_center_returns_fallback(self):
        """接近地心时应返回 fallback 速度（避免除零）。"""
        pos = EARTH_CENTER.copy()
        v = geo_circular_velocity_rotating(pos)
        assert np.linalg.norm(v) == pytest.approx(V_CIRCULAR_GEO, rel=1e-10)


# ── leo_circular_velocity_rotating ─────────────────────────


class TestLeoCircularVelocityRotating:
    """验证旋转系下 LEO 圆轨道速度的物理正确性。"""

    def test_leo_point_velocity_magnitude(self):
        """LEO 圆轨道上一点的速度大小应接近 |V_CIRCULAR_LEO - position[0]|。"""
        pos = np.array([EARTH_CENTER[0] + R_LEO, 0.0, 0.0])
        v = leo_circular_velocity_rotating(pos)
        expected_mag = abs(V_CIRCULAR_LEO - pos[0])
        assert np.linalg.norm(v) == pytest.approx(expected_mag, rel=1e-10)

    def test_leo_near_earth_center_returns_fallback(self):
        """接近地心时应返回 fallback 速度。"""
        pos = EARTH_CENTER.copy()
        v = leo_circular_velocity_rotating(pos)
        assert np.linalg.norm(v) == pytest.approx(V_CIRCULAR_LEO, rel=1e-10)


# ── compute_departure_velocity ─────────────────────────────


class TestComputeDepartureVelocity:
    """验证出发速度计算。"""

    def test_alpha_1_preserves_velocity(self):
        """alpha=1 时应保持原始速度。"""
        state = np.array([R_GEO, 0.0, 0.0, 0.0, 1.0, 0.0])
        v = compute_departure_velocity(state, alpha=1.0)
        np.testing.assert_allclose(v, state[3:6], atol=1e-12)

    def test_alpha_0_removes_tangential(self):
        """alpha=0 时应只保留径向分量。"""
        state = np.array([R_GEO, 0.0, 0.0, 0.0, 1.0, 0.0])
        v = compute_departure_velocity(state, alpha=0.0)
        # 径向方向沿 [R_GEO, 0, 0]，速度 [0, 1, 0] 的径向分量为 0
        assert np.linalg.norm(v) == pytest.approx(0.0, abs=1e-12)

    def test_alpha_2_doubles_tangential(self):
        """alpha=2 时切向分量应翻倍。"""
        state = np.array([R_GEO, 0.0, 0.0, 0.0, 1.0, 0.0])
        v = compute_departure_velocity(state, alpha=2.0)
        # 切向方向沿 [0, 1, 0]（在 xy 平面垂直于位置矢量）
        assert v[1] == pytest.approx(2.0, rel=1e-10)

    def test_near_origin_returns_original(self):
        """接近原点时应返回原始速度（避免除零）。"""
        state = np.array([0.0, 0.0, 0.0, 1.0, 2.0, 3.0])
        v = compute_departure_velocity(state, alpha=0.5)
        np.testing.assert_allclose(v, state[3:6], atol=1e-12)


# ── compute_geo_dv2 ────────────────────────────────────────


class TestComputeGeoDv2:
    """验证 GEO 插入 delta-v 计算。"""

    def test_geo_circular_orbit_dv_is_zero(self):
        """GEO 圆轨道状态的 delta-v 应接近零。"""
        geo = generate_geo_orbit(n_points=500)
        # 取轨道上第一个点
        state = geo.states[0]
        dv = compute_geo_dv2(state)
        assert dv == pytest.approx(0.0, abs=1e-6)

    def test_non_geo_orbit_dv_is_positive(self):
        """非 GEO 轨道的 delta-v 应为正。"""
        state = np.array([R_GEO + 0.1, 0.0, 0.0, 0.0, 0.5, 0.0])
        dv = compute_geo_dv2(state)
        assert dv > 0


# ── check_collision ────────────────────────────────────────


class TestCheckCollision:
    """验证碰撞检测逻辑。"""

    def test_no_collision(self):
        """远离天体的轨迹应无碰撞。"""
        states = np.array([
            [0.5, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.6, 0.0, 0.0, 0.0, 0.0, 0.0],
        ])
        hit, body, idx = check_collision(states, MU, 0.01, 0.01)
        assert not hit
        assert body is None
        assert idx == -1

    def test_earth_collision(self):
        """穿过地球的轨迹应检测到碰撞。"""
        states = np.array([
            [-MU + 0.001, 0.0, 0.0, 0.0, 0.0, 0.0],  # 接近地心
        ])
        hit, body, idx = check_collision(states, MU, 0.01, 0.01)
        assert hit
        assert body == "earth"
        assert idx == 0

    def test_moon_collision(self):
        """穿过月球的轨迹应检测到碰撞。"""
        states = np.array([
            [1.0 - MU + 0.001, 0.0, 0.0, 0.0, 0.0, 0.0],  # 接近月心
        ])
        hit, body, idx = check_collision(states, MU, 0.01, 0.01)
        assert hit
        assert body == "moon"
        assert idx == 0

    def test_invalid_radius_raises(self):
        """半径为负应抛出异常。"""
        states = np.array([[0.5, 0.0, 0.0, 0.0, 0.0, 0.0]])
        with pytest.raises(ValueError):
            check_collision(states, MU, -1.0, 0.01)


# ── generate_geo_orbit ─────────────────────────────────────


class TestGenerateGeoOrbit:
    """验证 GEO 轨道生成。"""

    def test_returns_orbit_object(self):
        """应返回 Orbit 对象。"""
        from e2m2e.core.orbit import Orbit
        geo = generate_geo_orbit()
        assert isinstance(geo, Orbit)

    def test_shape(self):
        """返回的轨道状态形状应为 (n_points, 6)。"""
        geo = generate_geo_orbit(n_points=100)
        assert geo.states.shape == (100, 6)

    def test_period(self):
        """周期应接近 T_GEO。"""
        geo = generate_geo_orbit()
        assert geo.period == pytest.approx(T_GEO, rel=1e-10)

    def test_states_are_finite(self):
        """所有状态值应为有限数。"""
        geo = generate_geo_orbit()
        assert np.all(np.isfinite(geo.states))


# ── generate_leo_orbit ─────────────────────────────────────


class TestGenerateLeoOrbit:
    """验证 LEO 轨道生成。"""

    def test_returns_orbit_object(self):
        """应返回 Orbit 对象。"""
        from e2m2e.core.orbit import Orbit
        leo = generate_leo_orbit()
        assert isinstance(leo, Orbit)

    def test_shape(self):
        """返回的轨道状态形状应为 (n_points, 6)。"""
        leo = generate_leo_orbit(n_points=100)
        assert leo.states.shape == (100, 6)

    def test_period(self):
        """周期应接近 T_LEO。"""
        leo = generate_leo_orbit()
        assert leo.period == pytest.approx(T_LEO, rel=1e-10)

    def test_states_are_finite(self):
        """所有状态值应为有限数。"""
        leo = generate_leo_orbit()
        assert np.all(np.isfinite(leo.states))
