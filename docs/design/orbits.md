---
sidebar_position: 4
---

# 基线轨道生成

按任务流程，首先需要生成基线轨道（DRO、RO、Halo），再进行转移设计。

## DRO（远距离逆行轨道）

### 概述

DRO（Distant Retrograde Orbit）是一种稳定的周期轨道，运动方向与月球公转方向相反，位于月球轨道之外。

### 轨道类型

| 类型 | 周期 | 共振比 | 典型 x₀ |
|------|------|--------|---------|
| 2:1 DRO | ≈3.47 TU (~15 天) | 1:2 | 0.7919 |
| 3:1 DRO | ≈2.09 TU (~9 天) | 1:3 | ~0.73 |

### 算法原理

**微分修正**：种子轨道使用 2D 对称 X-Fixed 微分修正算法生成。

**自然参数延拓**：逐步改变 x₀ 参数，以种子轨道为初始猜测逐条收敛，生成完整轨道族。

### 脚本

```bash
# 生成 DRO 族
uv run python -m tod.pipelines.dro.generate.generate_dro_family

# 生成单个 3:1 DRO
uv run python -m tod.pipelines.dro.generate.generate_31_dro_orbit

# 可视化
uv run python -m tod.pipelines.dro.plot.plot_dro_family
```

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `x0` | 0.7919 | 种子轨道初始 x₀ |
| `vy0` | 0.5368 | 种子轨道初始 vy |
| `param_min` | 0.6 | 延拓起始 x₀ |
| `param_max` | 0.8 | 延拓终止 x₀ |
| `step_size` | 0.005 | 延拓步长 |

---

## RO（共振轨道）

### 概述

RO（Resonant Orbit）周期与月球轨道周期成简单整数比。

### 轨道类型

| 类型 | 周期 | 共振比 | x₀ | vy₀ |
|------|------|--------|-----|------|
| 3:2 RO | ≈12.57 TU | 3:2 | -1.1453 | 0.4633 |
| 3:1 RO | ≈6.28 TU | 3:1 | -0.8805 | 0.3921 |

### 算法原理

**微分修正**：2D 对称 X-Fixed 模式，约束 y(0)=0, vx(0)=0, y(T/2)=0, vx(T/2)=0。

**自然延拓**：逐步改变 x₀，轨道按与种子轨道的距离排序存储。

### 脚本

```bash
# 生成 3:1 RO 族
uv run python -m tod.pipelines.ro.generate.generate_31_ro_family

# 生成 3:2 RO 族
uv run python -m tod.pipelines.ro.generate.generate_32_ro_family

# 生成单个 3:1 RO
uv run python -m tod.pipelines.ro.generate.generate_31_ro_orbit

# 可视化
uv run python -m tod.pipelines.ro.plot.plot_31_ro_family
uv run python -m tod.pipelines.ro.plot.plot_32_ro_family
```

| 参数（3:1） | 默认值 | 描述 |
|------|--------|------|
| `x0` | -0.8805 | 初始 x₀ |
| `vy0` | 0.3921 | 初始 vy |
| `param_min` | -0.8905 | 延拓起始 x₀ |
| `param_max` | -0.8305 | 延拓终止 x₀ |

---

## RRO / ARO（3D 共振轨道）

### 概述

RRO（反射共振轨道）和 ARO（轴向共振轨道）通过检测 2D RO 族中的切分岔点生成。RRO 关于 x-z 平面对称，ARO 关于 x 轴对称。

### 算法原理

**切分岔检测**：当单值矩阵的一对特征值在 +1 处碰撞时，发生切分岔，伴随 3D 轨道产生。

**RRO 生成**：固定 x₀（从分岔点获得），逐步增大 z₀，延拓生成。

**ARO 生成**：固定 z₀，逐步改变 x₀，延拓生成。

### 脚本

```bash
# 生成 RRO 族（需先有 3:2 RO 族）
uv run python -m tod.pipelines.ro.generate.generate_rro_family

# 生成 ARO 族
uv run python -m tod.pipelines.ro.generate.generate_aro_family

# 可视化
uv run python -m tod.pipelines.ro.plot.plot_rro_family
uv run python -m tod.pipelines.ro.plot.plot_aro_family
```

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `target_x0` | -1.0878（RRO）/ -1.1318（ARO） | 目标 x₀ |
| `z0` | 0.1999 | 固定 z₀（ARO） |

---

## Halo 轨道

### 概述

Halo 轨道是 L1 / L2 点附近的周期轨道，非平面，关于 x 轴或 x-z 平面对称。

### 脚本

```bash
# 生成单个 Halo
uv run python -m tod.pipelines.halo.generate.generate_halo_orbit

# 生成 Halo 族
uv run python -m tod.pipelines.halo.generate.generate_halo_family

# 可视化
uv run python -m tod.pipelines.halo.plot.plot_halo_orbit
uv run python -m tod.pipelines.halo.plot.plot_halo_family
```

---

## 输出格式

所有轨道族使用统一 JSON 格式：

```json
{
  "n_orbits": 41,
  "system": {"mu": 1.21506683e-2, "primary": "earth", "secondary": "moon"},
  "orbit_type": "DRO",
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
