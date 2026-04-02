"""
生成远距离逆行轨道族

本脚本实现：
1. 创建CR3BP系统和动力学模型
2. 设置DRO种子轨道的初始状态向量
3. 利用差分修正器修正种子轨道
4. 采用自然延拓方法生成完整轨道族

"""

from pathlib import Path

from fontTools.misc.timeTools import timestampNow
from scripts.utils.common import MU

import e2m2e
from e2m2e.core import Orbit

project_root = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = project_root / "output" / "dro"

# =============================================================================
# 1. 系统与动力学模型初始化
# =============================================================================
system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
dynamic = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

# =============================================================================
# 2. 种子轨道初始状态定义
# =============================================================================
# DRO特征：平面内运动（y=z=0），关于x轴对称（vx=vz=0）
# 初始状态向量格式：[x, y, z, vx, vy, vz]，均为无量纲量
x0 = 0.79188556619742  # 初始x坐标（无量纲）
vy0 = 0.53682  # 初始y方向速度（无量纲）

initial_state = [x0, 0.0, 0.0, 0.0, vy0, 0.0]
times = [0]  # 第一个历元时刻

seed_state = Orbit(states=[initial_state], times=times)
seed_state.period = 3.472526005624708  # 初始周期猜测（无量纲时间）

# =============================================================================
# 3. 种子轨道差分修正
# =============================================================================
corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamic)
corrector.setup_2D_symmetric_x_fixed_x0(x0=x0)
seed_DRO = corrector.iterate_correction(initial_guess=seed_state)

# =============================================================================
# 4. 自然延拓生成轨道族
# =============================================================================
continuation = e2m2e.algorithms.Continuation(corrector=corrector)
param_min = 0.141886  # 延拓到再下一步，就发散了（2026年3月21日21:16:19计算得到的结论）
param_max = 0.9
step_size = 0.005
family_result = continuation.natural_continuation(
    seed_orbit=seed_DRO,
    param_range=(param_min, param_max),  # x0参数延拓范围
    step_size=step_size,  # 延拓步长
)

# =============================================================================
# 5. 保存轨道数据
# =============================================================================
# 命名规则：dro_family_x0start-x0end-stepsize_timestamp.json
family_result.save_to_file(
    filename=str(
        OUTPUT_DIR
        / f"dro_family_{param_min}-{param_max}-{step_size}_{timestampNow()}.json"
    )
)
