# DRO 轨道生成

## 概述

本项目在地球-月球 CR3BP 系统中生成远距离逆行轨道（Distant Retrograde Orbit, DRO）族。DRO 是一种稳定的周期轨道，其特性使其成为月球任务中重要的中间轨道。

## DRO 轨道特征

| 特征 | 描述 |
|------|------|
| **运动方向** | 逆行（与月球运动方向相反） |
| **位置** | 位于月球轨道之外 |
| **对称性** | 关于 x 轴对称（平面情况） |
| **周期性** | 在旋转坐标系中闭合 |

### 轨道类型

| 类型 | 周期 | 共振比 | 典型 x₀ |
|------|------|--------|---------|
| 2:1 DRO | ≈3.47 TU (~15 天) | 1:2 | 0.7919 |
| 3:1 DRO | ≈2.09 TU (~9 天) | 1:3 | ~0.73 |

## 算法原理

### 微分修正

DRO 种子轨道使用 **2D 对称 X-Fixed** 微分修正算法生成：

```
约束条件：
- y(0) = 0 — 在 x 轴上出发
- vx(0) = 0 — 垂直离开
- y(T/2) = 0 — 半周期时穿过 x 轴
- vx(T/2) = 0 — 垂直穿过

自由参数：x₀, vy₀
```

### 自然延拓

使用自然参数延拓生成完整轨道族：

```
1. 从种子轨道 (x₀, vy₀) 开始
2. 逐步改变 x₀ 参数
3. 每步使用前一条轨道作为初始猜测
4. 应用微分修正收敛到新轨道
```

## 脚本使用

### generate_dro_family.py

生成 DRO 轨道族：

```bash
python scripts/generate/generate_dro_family.py
```

**关键参数**：

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `x0` | 0.7919 | 初始 x 坐标 |
| `vy0` | 0.5368 | 初始 y 方向速度 |
| `param_min` | 0.6 | 延拓起始 x₀ |
| `param_max` | 0.8 | 延拓终止 x₀ |
| `step_size` | 0.005 | 延拓步长 |

**输出文件**：`output/dro/dro_family_{x0_min}-{x0_max}-{step_size}_{timestamp}.json`

### plot_dro_family.py

可视化 DRO 轨道族：

```bash
python scripts/plot/plot_dro_family.py
```

**输出**：
- 整个族的 2D XY 投影
- Jacobi 常数 vs 轨道索引
- 稳定性指数 vs 轨道索引
- 种子轨道的 3D 轨迹

## 输出格式

轨道族 JSON 结构：

```json
{
  "n_orbits": 41,
  "system": {"mu": 0.0121506683, "primary": "earth", "secondary": "moon"},
  "orbits": [
    {
      "states": [[x, y, z, vx, vy, vz], ...],
      "times": [0.0, dt, 2*dt, ...],
      "period": 3.4725,
      "jacobi_constant": 3.0125,
      "stability_index": 0.892,
      "metadata": {
        "continuation_step": 0,
        "x0": 0.7919
      }
    }
  ]
}
```

## 与 e2m2e 库的接口

```python
import e2m2e
from e2m2e.core import Orbit

# 系统初始化
system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")
dynamic = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

# 微分修正
corrector = e2m2e.algorithms.DifferentialCorrection(dynamics=dynamic)
corrector.setup_2D_symmetric_x_fixed_x0(x0=0.7919)
seed_DRO = corrector.iterate_correction(initial_guess=seed_state)

# 自然延拓
continuation = e2m2e.algorithms.Continuation(corrector=corrector)
family_result = continuation.natural_continuation(
    seed_orbit=seed_DRO,
    param_range=(0.6, 0.8),
    step_size=0.005
)
```

## 物理参数

| 符号 | 值 | 描述 |
|------|-----|------|
| μ | 1.21506683×10⁻² | 地月质量比 |
| DU | 384,405 km | 距离单位 |
| TU | 4.34811305 天 | 时间单位 |
| VU | 1023.23281 m/s | 速度单位 |
