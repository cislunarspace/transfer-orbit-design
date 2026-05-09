---
sidebar_position: 7
---

# RRO 和 ARO 轨道生成

## 概述

本项目通过检测 2D 共振轨道（RO）族中的**切分岔点**，生成立体的反射共振轨道（RRO）和轴向共振轨道（ARO）。这两种 3D 轨道是月球任务中重要的非平面轨道选项。

## 轨道类型

| 类型 | 全称 | 特征 | 生成方式 |
|------|------|------|----------|
| RRO | Reflective Resonant Orbit | 关于 x-z 平面对称，类似于 Halo 轨道 | 从分岔点出发，固定 x₀，改变 z₀ |
| ARO | Axial Resonant Orbit | 关于 x 轴对称，类似于轴向轨道 | 从分岔点出发，固定 z₀，改变 x₀ |

### 目标参数（论文 Table 2）

| 类型 | x₀ | z₀ | 描述 |
|------|-----|-----|------|
| RRO | -1.0878 | 变化 | 反射共振轨道 |
| ARO | -1.1318 | 0.1999 | 轴向共振轨道 |

## 算法原理

### 切分岔检测

当单值矩阵的一对特征值在实轴 +1 处碰撞时，发生切分岔，伴随 3D 轨道的生成：

```
检测条件：
|λ_i - 1| < tolerance (tol=1e-8)

其中 λ_i 是单值矩阵的特征值
```

### 分岔点识别流程

```
1. 加载已有的 2D RO 族
2. 对每条轨道计算单值矩阵特征值
3. 寻找 |λ - 1| 最小的点作为分岔点
4. 从分岔点出发，生成 3D 轨道族
```

### RRO 生成（固定 x₀，改变 z₀）

```
1. 从分岔点 RO 获取 x₀
2. 设置初始 z₀ = 0.001
3. 使用自然延拓，逐步增大 z₀
4. 应用微分修正收敛
```

### ARO 生成（固定 z₀，改变 x₀）

```
1. 从分岔点 RO 获取 z₀
2. 设置目标 x₀（如 -1.1318）
3. 使用自然延拓，逐步改变 x₀
4. 应用微分修正收敛
```

## 脚本使用

### generate_rro_family.py

生成 RRO 轨道族：

```bash
python -m tod.pipelines.ro.generate_rro_family
```

**关键参数**：

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `TARGET_X0_RRO` | -1.0878 | RRO 目标 x₀ |
| `RO_32_FAMILY_FILE` | `output/ro/ro_32_family_...json` | 输入 2D RO 族文件 |

**输出文件**：`output/ro/rro_32_family_{timestamp}.json`

### generate_aro_family.py

生成 ARO 轨道族：

```bash
python -m tod.pipelines.ro.generate_aro_family
```

**关键参数**：

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `TARGET_X0_ARO` | -1.1318 | ARO 目标 x₀ |
| `Z0_ARO` | 0.1999 | 固定 z₀ |
| `RO_32_FAMILY_FILE` | `output/ro/ro_32_family_...json` | 输入 2D RO 族文件 |

**输出文件**：`output/ro/aro_32_family_{timestamp}.json`

### plot_rro_family.py / plot_aro_family.py

可视化 3D 轨道族：

```bash
# 可视化 RRO
python -m tod.pipelines.ro.plot_rro_family

# 可视化 ARO
python -m tod.pipelines.ro.plot_aro_family
```

## 与 e2m2e 库的接口

```python
import e2m2e
from e2m2e.algorithms.stability import BifurcationType

# 加载 2D RO 族
family_32 = e2m2e.core.orbit.OrbitFamily.load_from_file(RO_32_FAMILY_FILE)

# 检测分岔点
bifurcation_points = e2m2e.algorithms.StabilityAnalysis.detect_bifurcation_in_family(
    orbits=family_32.orbits,
    dynamics=dynamics,
    tolerance=1e-8,
)

# 生成分岔点信息
bifurcation_info = {
    "orbit_index": best_orbit_idx,
    "orbit": family_32.orbits[best_orbit_idx],
    "eigenvalues": best_eigenvalues,
    "eigenvalue_diff": min_diff,
    "bifurcation_type": BifurcationType.SADDLE_NODE,
}
```

## 输出格式

RRO/ARO 族 JSON 结构与 2D RO 族相同，包含：

```json
{
  "n_orbits": 20,
  "system": {"mu": 0.0121506683, "primary": "earth", "secondary": "moon"},
  "orbit_type": "RRO_32",
  "orbits": [
    {
      "states": [[x, y, z, vx, vy, vz], ...],
      "times": [0.0, dt, 2*dt, ...],
      "period": 12.566,
      "jacobi_constant": 3.0125,
      "stability_index": 0.892,
      "metadata": {
        "z0": 0.05,
        "x0": -1.0878
      }
    }
  ]
}
```

## 物理背景

### Halo 轨道与 RRO

RRO 类似于经典 Halo 轨道，关于 x-z 平面对称：

- 运动关于 x-z 平面对称（y → -y 映射到自身）
- z 振幅决定轨道的"高度"
- 常用于月球 L1/L2 附近的任务

### 轴向轨道与 ARO

ARO 关于 x 轴对称：

- 运动关于 x 轴对称
- z 振幅固定，x₀ 沿族变化
- 提供与 RRO 不同的转移选项
