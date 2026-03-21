# RO 轨道生成

## 概述

本项目在地月 CR3BP 系统中生成共振轨道（Resonant Orbit, RO）族。共振轨道是指航天器轨道周期与月球轨道周期成简单整数比的周期轨道。

## 共振轨道特征

| 类型 | 周期 | 共振比 | 描述 |
|------|------|--------|------|
| 3:2 RO | 4π ≈ 12.566 TU | 3:2 | 航天器 3 圈 / 月球 2 圈 |
| 3:1 RO | 2π ≈ 6.283 TU | 3:1 | 航天器 3 圈 / 月球 1 圈 |

### 种子轨道参数（论文 Table 2）

| 类型 | x₀ | y₀ | vy₀ | 周期 (TU) |
|------|-----|-----|------|------------|
| 3:2 RO | -1.1453 | 0.4633 | ~0.6124 | 12.566 |
| 3:1 RO | -0.8805 | 0.3921 | ~0.3921 | 6.283 |

**注意**：x₀, y₀ 是 y 幅值点（vy=0），不是 x 轴交点。

## 算法原理

### 微分修正

RO 轨道使用与 DRO 相同的 **2D 对称 X-Fixed** 微分修正算法：

```
约束条件：
- y(0) = y₀（幅值点）
- vy(0) = 0（幅值点条件）
- y(T/2) = 0 — 半周期时穿过 x 轴
- vy(T/2) = 0 — 垂直穿过

自由参数：x₀, vy₀
```

### 自然延拓

使用自然参数延拓生成完整轨道族：

```
1. 从 y 幅值点 (x₀, y₀, vy₀) 出发
2. 逐步改变 x₀ 参数
3. 应用微分修正收敛到新轨道
```

### 轨道排序

延拓生成的轨道按 **从种子轨道的距离** 排序，存储在 `metadata.continuation_step` 字段中：
- `continuation_step = 0`：种子轨道
- `continuation_step > 0`：正向延拓（参数增大方向）
- `continuation_step < 0`：反向延拓（参数减小方向）

排序模式确保可视化时轨道从种子向外依次展开：`[0, -1, 1, -2, 2, -3, 3, ...]`

## 脚本使用

### generate_ro_family.py

生成所有 RO 轨道族（3:2 和 3:1）：

```bash
python scripts/generate_ro_family.py
```

### generate_31_ro_family.py

仅生成 3:1 RO 轨道族：

```bash
python scripts/generate_31_ro_family.py
```

**关键参数**：

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `x0` | -0.8805 | 初始 x 坐标 |
| `vy0` | 0.3921 | 初始 y 方向速度 |
| `param_min` | 0.8905 | 延拓起始 x₀ |
| `param_max` | -0.8305 | 延拓终止 x₀ |
| `step_size` | 0.001 | 延拓步长 |

**输出文件**：`output/ro/ro_31_family_{x0_min}-{x0_max}-{step_size}_{timestamp}.json`

### generate_32_ro_family.py

仅生成 3:2 RO 轨道族：

```bash
python scripts/generate_32_ro_family.py
```

**关键参数**：

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `x0` | -1.1453 | 初始 x 坐标 |
| `vy0` | 0.4633 | 初始 y 方向速度 |
| `param_min` | -1.2 | 延拓起始 x₀ |
| `param_max` | -0.8 | 延拓终止 x₀ |
| `step_size` | 0.005 | 延拓步长 |

**输出文件**：`output/ro/ro_32_family_{x0_min}-{x0_max}-{step_size}_{timestamp}.json`

### plot_ro_family.py / plot_31_ro_family.py / plot_32_ro_family.py

可视化 RO 轨道族：

```bash
# 可视化所有 RO
python scripts/plot_ro_family.py

# 可视化 3:1 RO
python scripts/plot_31_ro_family.py

# 可视化 3:2 RO
python scripts/plot_32_ro_family.py
```

**输出**：
- 整个族的 2D XY 投影
- 周期 vs 轨道索引
- 稳定性指数 vs 轨道索引

**绘制范围控制**：在脚本顶部设置 `PLOT_START_IDX` 和 `PLOT_END_IDX` 变量，可控制绘制轨道的索引范围。

## 输出格式

轨道族 JSON 结构：

```json
{
  "n_orbits": 94,
  "system": {"mu": 0.0121506683, "primary": "earth", "secondary": "moon"},
  "orbit_type": "3:2_RO",
  "orbits": [
    {
      "states": [[x, y, z, vx, vy, vz], ...],
      "times": [0.0, dt, 2*dt, ...],
      "period": 12.566,
      "jacobi_constant": 3.0125,
      "stability_index": 0.892,
      "metadata": {
        "continuation_step": 0,
        "x0": -1.1453,
        "y0": 0.4633
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
dynamics = e2m2e.core.dynamics.CR3BP_Dynamics(system=system)

# 微分修正
corrector = e2m2e.algorithms.DifferentialCorrection(dynamic=dynamics)
corrector.setup_2D_symmetric_x_fixed_x0(x0=-0.8805)
seed_RO = corrector.iterate_correction(initial_guess=seed_orbit)

# 自然延拓
continuator = e2m2e.algorithms.Continuation(corrector=corrector)
family_result = continuator.natural_continuation(
    seed_orbit=seed_RO,
    param_range=(-1.0, -0.7),
    step_size=0.001
)
```

## 物理参数

| 符号 | 值 | 描述 |
|------|-----|------|
| μ | 1.21506683×10⁻² | 地月质量比 |
| T_Moon | 2π ≈ 6.283 TU | 月球轨道周期 |
| DU | 384,405 km | 距离单位 |
| TU | 4.34811305 天 | 时间单位 |
