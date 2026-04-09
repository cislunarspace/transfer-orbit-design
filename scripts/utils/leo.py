"""
LEO (Low Earth Orbit) 工具函数

在 CR3BP 归一化坐标系中定义 LEO 参数和辅助函数。
LEO 建模为固定半径球面（以地心为圆心），非 CR3BP 周期轨道。

归一化参数:
    r_LEO = altitude + R_earth / DU
    v_circular = sqrt((1-μ)/r_LEO)
    T_LEO = 2π * r_LEO / v_circular
"""

import numpy as np

from .common import DU, MU, TU, VU

# 地球半径 (km)
R_EARTH_KM = 6371.0

# 典型 LEO 高度和对应参数
# 400 km ISS 轨道
LEO_ALT_400KM = 400.0
R_LEO_400KM = (R_EARTH_KM + LEO_ALT_400KM) / DU
V_CIRCULAR_LEO_400KM = np.sqrt((1.0 - MU) / R_LEO_400KM)
T_LEO_400KM = 2.0 * np.pi * R_LEO_400KM / V_CIRCULAR_LEO_400KM

# 200 km 低轨
LEO_ALT_200KM = 200.0
R_LEO_200KM = (R_EARTH_KM + LEO_ALT_200KM) / DU
V_CIRCULAR_LEO_200KM = np.sqrt((1.0 - MU) / R_LEO_200KM)
T_LEO_200KM = 2.0 * np.pi * R_LEO_200KM / V_CIRCULAR_LEO_200KM

# 默认使用 400 km
R_LEO = R_LEO_400KM
V_CIRCULAR_LEO = V_CIRCULAR_LEO_400KM
T_LEO = T_LEO_400KM
LEO_ALT_KM = LEO_ALT_400KM

EARTH_CENTER = np.array([-MU, 0.0, 0.0])


def leo_circular_velocity_rotating(position: np.ndarray, r_leo: float = R_LEO) -> np.ndarray:
    """计算旋转系下 LEO 圆轨道速度。

    v_rot = v_inertial - Ω × r, 其中 Ω = 1（归一化旋转角速度）。

    Args:
        position: 旋转系坐标 [x, y, z]
        r_leo: LEO 归一化半径

    Returns:
        旋转系速度 [vx, vy, vz]
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


def generate_leo_orbit_states(n_points: int = 500, r_leo: float = R_LEO) -> np.ndarray:
    """生成 LEO 近似圆轨道状态数组。

    Args:
        n_points: 采样点数
        r_leo: 归一化 LEO 半径

    Returns:
        (n_points, 6) 状态数组
    """
    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    states = np.zeros((n_points, 6))

    for i, th in enumerate(theta):
        x = EARTH_CENTER[0] + r_leo * np.cos(th)
        y = r_leo * np.sin(th)
        z = 0.0

        pos = np.array([x, y, z])
        vel = leo_circular_velocity_rotating(pos, r_leo)

        states[i] = [x, y, z, vel[0], vel[1], vel[2]]

    return states
