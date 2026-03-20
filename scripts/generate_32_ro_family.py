"""
生成 3:2 共振轨道族

本脚本实现：
1. 创建CR3BP系统和动力学模型
2. 设置3:2 RO种子轨道的初始状态向量
3. 利用差分修正器修正种子轨道
4. 采用自然延拓方法生成完整轨道族

3:2共振轨道特征：
  - T = 4π ≈ 12.566 TU (航天器3圈/月球2圈)
  - y幅值点: x=-1.1453, y=0.4633

参考论文：
  Cui et al. (2025) "Two-Impulse Transfers from Lunar Distant Retrograde Orbits
  to Resonant Orbits", JGCD, Vol.48, No.6
"""

from fontTools.misc.timeTools import timestampNow

import e2m2e
from e2m2e.core import Orbit

from scripts.utils.common import MU

# =============================================================================
# 系统参数
# =============================================================================
T_MOON = 2 * 3.141592653589793  # 月球恒星周期(无量纲)
T_RO_32 = 2 * T_MOON  # 4π ≈ 12.566 TU

# 3:2 RO 种子轨道参数（论文Table 2）
SEED_X0 = -1.1453  # y幅值点x坐标
SEED_Y0 = 0.4633  # y幅值点y坐标
X0_RANGE = (-1.2, -0.8)  # 延拓x0范围

# =============================================================================
# 1. 系统与动力学模型初始化
# =============================================================================
system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

# =============================================================================
# 2. 种子轨道初始状态定义
# =============================================================================
# 3:2 RO特征：平面内运动（y幅值点处y_dot=0），关于x轴对称（vx=vz=0）
# 初始状态向量格式：[x, y, z, vx, vy, vz]，均为无量纲量
x0 = SEED_X0  # 初始x坐标（无量纲）
vy0 = 0.0  # 初始y方向速度（无量纲），需通过微分修正确定

initial_state = [x0, SEED_Y0, 0.0, 0.0, vy0, 0.0]
times = [0]  # 第一个历元时刻

seed_orbit = Orbit(states=[initial_state], times=times)
seed_orbit.period = T_RO_32  # 目标周期（无量纲时间）

# =============================================================================
# 3. 种子轨道差分修正
# =============================================================================
corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
corrector.setup_2D_symmetric_x_fixed_x0(x0=x0)
seed_RO = corrector.iterate_correction(initial_guess=seed_orbit)

# =============================================================================
# 4. 自然延拓生成轨道族
# =============================================================================
continuation = e2m2e.algorithms.Continuation(corrector=corrector)
step_size = 0.005
family_result = continuation.natural_continuation(
    seed_orbit=seed_RO,
    param_range=X0_RANGE,  # x0参数延拓范围
    step_size=step_size,  # 延拓步长
)

# =============================================================================
# 5. 保存轨道数据
# =============================================================================
# 命名规则：ro_32_family_x0start-x0end-stepsize_timestamp.json
family_result.save_to_file(
    filename=f"output/ro/ro_32_family_{X0_RANGE[0]}-{X0_RANGE[1]}-{step_size}_{timestampNow()}.json"
)
