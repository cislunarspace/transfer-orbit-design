# 轨道生成

## 概述

本项目在地月 CR3BP 系统中生成两种类型的周期轨道：
- **DRO（远距离逆行轨道）**：月球周围的逆行轨道
- **RO（共振轨道）**：相对于月球周期的轨道

## DRO 生成

### 特征

- **逆行**：与月球运动方向相反
- **远距离**：位于月球轨道之外
- **对称**：关于 x 轴对称（平面情况）
- **周期性**：在旋转坐标系中闭合

### 种子轨道参数

根据论文，DRO 种子通过周期共振识别：

| DRO 类型 | x₀ | 周期 (TU) |
|----------|-----|-------------|
| 2:1 DRO | 0.7919 | ~3.47 |
| 3:1 DRO | ~0.73 | ~2.09 |

### 算法

```
1. 设置初始状态向量 [x₀, 0, 0, 0, vy₀, 0]
2. 应用微分修正满足周期约束
3. 使用自然延拓生成轨道族
4. 改变 x₀ 参数探索轨道族
```

### 脚本使用

```bash
python scripts/generate_dro_family.py
```

输出：`output/dro/dro_family_{x0_min}-{x0_max}-{step}_{timestamp}.json`

## RO 生成

### 共振轨道特征

| 类型 | 周期 | 共振比 | 描述 |
|------|--------|--------|------|
| 3:2 RO | 4π ≈ 12.566 TU | 3:2 | 航天器 3 圈 / 月球 2 圈 |
| 3:1 RO | 2π ≈ 6.283 TU | 3:1 | 航天器 3 圈 / 月球 1 圈 |

### 种子轨道参数（论文 Table 2）

| 类型 | x₀ | y₀ | 周期 (TU) |
|------|-----|-----|-------------|
| 3:2 RO | -1.1453 | 0.4633 | 12.566 |
| 3:1 RO | -0.8805 | 0.3921 | 6.283 |

注意：x₀, y₀ 是 y 幅值点（vy=0），不是 x 轴交点。

### 算法

```
1. 在 y 幅值点设置初始状态 [x₀, y₀, 0, 0, vy₀, 0]
2. 应用带周期约束的微分修正
3. 使用自然延拓生成完整轨道族
4. 改变 x₀ 参数（例如 3:2 RO 为 -1.2 到 -0.8）
```

### 脚本使用

```bash
# 生成 3:2 和 3:1 RO 族
python scripts/generate_ro_family.py

# 仅生成 3:1 RO 族
python scripts/generate_31_ro_family.py

# 仅生成 3:2 RO 族
python scripts/generate_32_ro_family.py
```

## 输出格式

轨道族 JSON 结构：

```json
{
  "n_orbits": 94,
  "system": {"mu": 0.0121506683, "primary": "earth", "secondary": "moon"},
  "metadata": {
    "family_type": "DRO",
    "param_range": [0.6, 0.8],
    "step_size": 0.005,
    "generated_at": "timestamp"
  },
  "orbits": [
    {
      "states": [[x, y, z, vx, vy, vz], ...],
      "times": [0.0, 0.01, ...],
      "period": 3.4725,
      "jacobi_constant": 3.05,
      "stability_index": 0.95
    }
  ]
}
```

## 可视化

```bash
# 绘制 DRO 族
python scripts/plot_dro_family.py

# 绘制 RO 族
python scripts/plot_ro_family.py
```
