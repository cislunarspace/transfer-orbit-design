"""GEO / LEO 圆轨道几何工具。

在 CR3BP 归一化坐标系中定义 GEO（地球静止轨道）与 LEO（低地球轨道）的
参数与辅助函数。两者都建模为以地心为圆心的固定半径圆轨道（非 CR3BP 周期轨道）。

归一化常量（MU/DU/TU/VU）复用 :mod:`tod.commons.constants`，单一来源。

本模块原属 e2m2e.orbits 包，因 e2m2e 误删（commit fd99f27，当孤儿删但 tod
依赖它）而移植至此。几何逻辑与原实现一致；``compute_departure_velocity``
同时整合了 tod 内此前的 4 处重复副本。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from .constants import DU, MU

if TYPE_CHECKING:
    from e2m2e.core.orbit import Orbit

# =============================================================================
# GEO（地球静止轨道）参数
# =============================================================================

R_GEO_KM: float = 42164.0
R_GEO: float = R_GEO_KM / DU
V_CIRCULAR_GEO: float = float(np.sqrt((1.0 - MU) / R_GEO))
T_GEO: float = float(2.0 * np.pi * R_GEO / V_CIRCULAR_GEO)
EARTH_CENTER: npt.NDArray[np.floating] = np.array([-MU, 0.0, 0.0])

def geo_circular_velocity_rotating(position: npt.NDArray[np.floating]) -> npt.NDArray[np.floating]:
    """计算旋转系下 GEO 圆轨道速度。

    Args:
        position: 旋转系位置 ``(3,)``。

    Returns:
        旋转系下 GEO 圆轨道速度 ``(3,)``。
    """
    r_rel = position - EARTH_CENTER
    r_rel_xy = np.sqrt(r_rel[0] ** 2 + r_rel[1] ** 2)
    if r_rel_xy < 1e-12:
        return np.array([0.0, V_CIRCULAR_GEO, 0.0])

    tangential = np.array([-r_rel[1], r_rel[0], 0.0]) / r_rel_xy
    v_inertial = V_CIRCULAR_GEO * tangential

    omega_cross_r = np.array([-position[1], position[0], 0.0])
    return v_inertial - omega_cross_r

def compute_geo_dv2(trajectory_state: npt.NDArray[np.floating]) -> float:
    """计算 GEO 插入 delta-v。

    Args:
        trajectory_state: 转移轨迹末端状态 ``(6,)``。

    Returns:
        GEO 插入 Δv 标量。
    """
    v_geo = geo_circular_velocity_rotating(trajectory_state[:3])
    return float(np.linalg.norm(trajectory_state[3:] - v_geo))

# =============================================================================
# LEO（低地球轨道）参数
# =============================================================================

R_EARTH_KM: float = 6371.0

LEO_ALT_KM: float = 400.0
R_LEO: float = (R_EARTH_KM + LEO_ALT_KM) / DU
V_CIRCULAR_LEO: float = float(np.sqrt((1.0 - MU) / R_LEO))
T_LEO: float = float(2.0 * np.pi * R_LEO / V_CIRCULAR_LEO)

def leo_circular_velocity_rotating(
    position: npt.NDArray[np.floating], r_leo: float = R_LEO
) -> npt.NDArray[np.floating]:
    """计算旋转系下 LEO 圆轨道速度。

    Args:
        position: 旋转系位置 ``(3,)``。
        r_leo: LEO 归一化半径，默认 400 km 高度。

    Returns:
        旋转系下 LEO 圆轨道速度 ``(3,)``。
    """
    r_rel = position - EARTH_CENTER
    r_rel_xy = np.sqrt(r_rel[0] ** 2 + r_rel[1] ** 2)
    v_circ = np.sqrt((1.0 - MU) / r_leo)

    if r_rel_xy < 1e-12:
        return np.array([0.0, v_circ, 0.0])

    tangential = np.array([-r_rel[1], r_rel[0], 0.0]) / r_rel_xy
    v_inertial = v_circ * tangential

    omega_cross_r = np.array([-position[1], position[0], 0.0])
    return v_inertial - omega_cross_r

def generate_leo_orbit(
    n_points: int = 500, r_leo: float = R_LEO
) -> "Orbit":
    """在 CR3BP 旋转系中生成 LEO 近似圆轨道。

    LEO 被建模为以地心为圆心、半径为 R_LEO 的圆轨道。
    速度通过 leo_circular_velocity_rotating 计算（包含 Coriolis 修正）。

    Args:
        n_points: 采样点数。
        r_leo: LEO 归一化半径，默认 400 km 高度。

    Returns:
        ``Orbit`` 对象，包含 states、times 和 period。
    """
    from e2m2e.core.orbit import Orbit

    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    states = np.zeros((n_points, 6))

    for i, th in enumerate(theta):
        x = EARTH_CENTER[0] + r_leo * np.cos(th)
        y = r_leo * np.sin(th)
        z = 0.0

        pos = np.array([x, y, z])
        vel = leo_circular_velocity_rotating(pos, r_leo)

        states[i] = [x, y, z, vel[0], vel[1], vel[2]]

    t_leo = float(2.0 * np.pi * r_leo / np.sqrt((1.0 - MU) / r_leo))
    times = np.linspace(0, t_leo, n_points, endpoint=False)

    orbit = Orbit(states, times)
    orbit.period = t_leo
    return orbit

# =============================================================================
# 共享：出发速度分解 + 碰撞检测
# =============================================================================

def compute_departure_velocity(
    state: npt.ArrayLike, alpha: float
) -> npt.NDArray[np.floating]:
    """按切向速度比 α 计算出发速度。

    径向分量（沿位置矢量）保持不变，切向分量（垂直位置矢量、在赤道面内）
    乘以 α。模拟在出发轨道点上缩放切向速度的脉冲机动。

    Args:
        state: 出发点状态 ``(6,)``，前 3 为位置、后 3 为速度。
        alpha: 切向速度比例。

    Returns:
        调整后的速度 ``(3,)``。
    """
    pos = np.asarray(state[:3], dtype=np.float64)
    vel = np.asarray(state[3:6], dtype=np.float64)
    r_xy = float(np.sqrt(pos[0] ** 2 + pos[1] ** 2))
    if r_xy < 1e-10:
        # r_xy ≈ 0 时切向向量 [-y, x, 0]/r_xy 无定义，返回原始速度。
        return vel.copy()
    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)
    v_radial_comp = float(np.dot(vel, radial))
    v_tangential_comp = float(np.dot(vel, tangential))
    return v_radial_comp * radial + alpha * v_tangential_comp * tangential

def check_collision(
    states: npt.NDArray[np.floating],
    mu: float,
    earth_radius: float,
    moon_radius: float,
) -> tuple[bool, str | None, int]:
    """碰撞检测（地球/月球）。

    Args:
        states: 轨迹状态序列 ``(n, 6)``。
        mu: CR3BP 质量参数。
        earth_radius: 地球归一化半径。
        moon_radius: 月球归一化半径。

    Returns:
        ``(是否碰撞, 碰撞天体名或 None, 首次碰撞索引)``。
    """
    if earth_radius <= 0 or moon_radius <= 0:
        raise ValueError("Radii must be positive")
    positions = states[:, :3]
    earth_center = np.array([-mu, 0.0, 0.0])
    moon_center = np.array([1.0 - mu, 0.0, 0.0])
    d_earth = np.linalg.norm(positions - earth_center, axis=1)
    d_moon = np.linalg.norm(positions - moon_center, axis=1)
    e_col = np.where(d_earth < earth_radius)[0]
    m_col = np.where(d_moon < moon_radius)[0]
    if len(e_col) > 0:
        return True, "earth", int(e_col[0])
    if len(m_col) > 0:
        return True, "moon", int(m_col[0])
    return False, None, -1

# =============================================================================
# GEO 轨道生成
# =============================================================================

def generate_geo_orbit(n_points: int = 500) -> "Orbit":
    """在 CR3BP 旋转系中生成 GEO 近似圆轨道。

    GEO 被建模为以地心为圆心、半径为 R_GEO 的圆轨道。
    速度通过 geo_circular_velocity_rotating 计算（包含 Coriolis 修正）。

    Args:
        n_points: 采样点数。

    Returns:
        ``Orbit`` 对象，包含 states、times 和 period。
    """
    from e2m2e.core.orbit import Orbit

    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    states = np.zeros((n_points, 6))

    for i, th in enumerate(theta):
        x = EARTH_CENTER[0] + R_GEO * np.cos(th)
        y = R_GEO * np.sin(th)
        z = 0.0

        pos = np.array([x, y, z])
        vel = geo_circular_velocity_rotating(pos)

        states[i] = [x, y, z, vel[0], vel[1], vel[2]]

    times = np.linspace(0, T_GEO, n_points, endpoint=False)

    orbit = Orbit(states, times)
    orbit.period = T_GEO
    return orbit
