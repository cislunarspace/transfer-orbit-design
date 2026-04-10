"""
系统参数（论文Table 1）
"""

import math

# 地月系统质量比，μ = m2/(m1+m2)，其中m1为地球质量，m2为月球质量
MU = 1.21506683e-2  # Mass ratio of the Earth–moon system

# 太阳的无量纲质量，用于后续考虑太阳引力摄动
M_SUN = 3.28900541e5  # Nondimensional mass of the sun

# 太阳的无量纲角速度，描述太阳在旋转坐标系中的运动
OMEGA_SUN = 9.25195985e-1  # Nondimensional angular velocity of the sun

# 太阳到地月系统的无量纲距离
RHO = 3.88811143e2  # Nondimensional sun–(Earth–moon) distance

# 距离单位：1 DU = 384405 km，地月平均距离
DU = 3.84405000e5  # Distance unit km

# 时间单位：1 TU = 4.34811305 天，地月系统的特征时间尺度
TU = 4.34811305  # Time unit days

# 速度单位：1 VU = 1023.23281 m/s，基于DU和TU计算得出
VU = 1023.23281  # Velocity unit m/s

# 月球轨道周期（无量纲）
T_MOON = 2.0 * math.pi  # 2π ≈ 6.283
