# API 参考

## e2m2e 核心模块

### e2m2e.core.system.CR3BP_System

带有主天体和次天体的 CR3BP 系统。

```python
from e2m2e.core.system import CR3BP_System

system = CR3BP_System(
    mu=0.0121506683,  # 地月质量比
    primary="earth",
    secondary="moon"
)
```

**属性**：
- `mu`：质量比
- `primary`, `secondary`：天体名称
- `libration_points`：5 个 Lagrange 点列表
- `jacobi_constant(state)`：计算状态的 C_J

### e2m2e.core.dynamics.CR3BP_Dynamics

CR3BP 运动方程积分。

```python
from e2m2e.core.dynamics import CR3BP_Dynamics

dynamics = CR3BP_Dynamics(system=system)
```

**方法**：
- `propagate(state, t_span, ...)`：积分轨迹
- `compute_stm(state, t_span)`：带 STM 积分

### e2m2e.core.orbit.Orbit

单个周期轨道容器。

```python
from e2m2e.core import Orbit

orbit = Orbit(states=[[x, y, z, vx, vy, vz]], times=[0.0])
orbit.period = 3.4725
orbit.jacobi_constant = 3.05
orbit.stability_index = 0.95
```

**属性**：
- `states`：[x, y, z, vx, vy, vz] 数组列表
- `times`：对应的时间
- `period`：轨道周期
- `jacobi_constant`, `stability_index`：轨道属性

**方法**：
- `save_to_file(filename)`：保存为 JSON
- `load_from_file(filename, system)`：从 JSON 加载

### e2m2e.core.orbit.OrbitFamily

周期轨道集合。

```python
from e2m2e.core import OrbitFamily

family = OrbitFamily(orbits=[orbit1, orbit2, ...])
family.save_to_file("output.json")
OrbitFamily.load_from_file("output.json", system=system)
```

**方法**：
- `get_jacobi_constants()`：C_J 值数组
- `get_stability_indices()`：稳定性指数数组

## e2m2e 算法

### e2m2e.algorithms.DifferentialCorrection

```python
from e2m2e.algorithms import DifferentialCorrection

corrector = DifferentialCorrection(dynamics=dynamics)
corrector.setup_2D_symmetric_x_fixed_x0(x0=0.7919)
corrected = corrector.iterate_correction(initial_guess)
```

### e2m2e.algorithms.Continuation

```python
from e2m2e.algorithms import Continuation

continuation = Continuation(corrector=corrector)
family = continuation.natural_continuation(
    seed_orbit=seed,
    param_range=(0.6, 0.8),
    step_size=0.005
)
```

## e2m2e 可视化

### e2m2e.visualization.plotting.OrbitVisualizer

```python
from e2m2e.visualization.plotting import OrbitVisualizer, compute_stability_for_family

plotter = OrbitVisualizer(system=system)
plotter.plot_2d_projection(orbit, plane="xy")
plotter.plot_3d_trajectory(orbit)
plotter.plot_family_overview(family)
```

## 本地脚本

### scripts/utils/params.py

论文 Table 1 的物理常数。

### scripts/utils/common.py

共享工具函数。

```python
from scripts.utils.common import MU, DU, TU, VU, T_MOON
```
