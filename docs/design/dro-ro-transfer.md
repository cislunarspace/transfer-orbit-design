# DRO 到 RO 转移设计

## 概述

本项目实现从远距离逆行轨道（DRO）到共振轨道（RO）的两脉冲转移设计。由于 DRO 和 RO 均为稳定轨道，无法利用不稳定流形结构，论文提出了一种"搜索-优化"两步法来设计转移轨道。

## 问题陈述

设计从出发 DRO 到目标 RO 的两脉冲转移，使得：

1. 在 DRO 上的出发点点火 $\Delta v_1$
2. 自由传播沿 ballistic 弧段
3. 在 RO 上的插入点点火 $\Delta v_2$

**目标**：最小化总脉冲 $J = \Delta v_1 + \Delta v_2$

## 两步法设计

### 第一步：搜索阶段

网格搜索可行转移：

```
对于每个网格点：
    1. 计算出发状态（以速度 α·v_tangential 在 DRO 上）
    2. 前向积分找到轨迹
    3. 检查轨迹是否接近目标 RO
    4. 记录可行的转移
```

**搜索变量**：

| 变量 | 描述 | 范围 |
|------|------|------|
| 出发位置 | DRO 上的位置 | 沿轨道分布 |
| α | 切向速度比 | 0.5 ~ 2.5 |
| θs0 | 太阳初始相位（BR4BP） | 0 ~ 2π |

### 第二步：优化阶段

使用 NLP 优化改进初始猜测：

**决策变量**：$y = \{\alpha, T, t_{ins}\}$

**目标函数**：$J(y) = \Delta v_1 + \Delta v_2$

**约束条件**：
- 出发点位置连续性
- 插入点位置连续性
- 速度方向约束
- 不与地球或月球碰撞

**求解器**：序列二次规划（SQP）

## 转移类型

| 类型 | 持续时间 | $\Delta v$ | 特征 |
|------|----------|------------|------|
| 直接转移 | < 20 天 | 高 | 短椭圆，少于 1 圈地球 |
| 月球借力转移 | 60-80 天 | 最低 | 月球引力辅助，多圈 |
| 外部转移 | 60-100 天 | 中等 | 远地点 > 3 倍地月距离 |

### 直接转移

```
特点：
- 转移时间短（< 20 天）
- 燃料消耗较高
- 轨迹近似椭圆，不到一圈地球
```

### 月球借力转移（LGA Transfer）

```
特点：
- 利用月球近飞段改变速度方向
- 需要多圈调相
- 燃料消耗最低
- 转移时间 60-80 天
```

### 外部转移

```
特点：
- 远地点超过 3 倍地月距离
- BR4BP 中类似 WSB 转移
- 转移时间 60-100 天
- 燃料消耗中等
```

## 动力学模型

### CR3BP（圆型限制性三体问题）

地月系统基本模型，用于计算基线轨道和初步转移设计。

### BR4BP（双圆限制性四体问题）

在 CR3BP 基础上加入太阳引力：

```
太阳参数（与 params.py 一致）：
- μs = 3.28900541 × 10^5
- ωs = 9.25195985 × 10^-1
- ρ = 3.88811143 × 10^2
```

太阳初始相位 θs0 成为优化变量。

### 星历模型

基于 DE438 星历的限制性 N 体问题，用于最终真实场景验证。

## 出发 DRO 和目标 RO 选择

### 出发轨道

| 类型 | 周期 | 典型应用 |
|------|------|----------|
| 2:1 DRO | ≈3.47 TU (~15 天) | 更稳定，更大能量 |
| 3:1 DRO | ≈2.09 TU (~9 天) | 周期更短 |

### 目标轨道

| 类型 | 周期 | 特点 |
|------|------|------|
| 3:2 RO | 12.57 TU (~55 天) | 3:2 共振 |
| 3:1 RO | 6.28 TU (~27 天) | 3:1 共振 |
| 3D RRO/ARO | 12.57 TU | 非平面，z 振幅 Az=0.2 |

## 脚本使用

### grid_search_dro_to_ro.py

网格搜索转移轨道：

```bash
python scripts/transfer/grid_search_dro_to_ro.py
```

**搜索变量**：
- `alpha`：切向速度比（0.5 ~ 2.5）
- 出发点位置沿 DRO 轨道分布

### optimize_dro_to_ro.py

优化阶段（NLP/SQP）：

```bash
python scripts/transfer/optimize_dro_to_ro.py
```

### plot_search_results.py

可视化转移搜索结果：

```bash
python scripts/transfer/plot_search_results.py <results.json>
```

**参数**：
- `--time-dv`：绘制转移时间 vs delta-v 散点图
- `--orbit`：绘制 3D 转移轨道图
- `--idx <int|best|random|all|best:N>`：选择绘制的可行解
- `--save <path>`：保存图片而非显示

## 与 e2m2e 库的接口

```python
from e2m2e.transfer import (
    TransferSearch,
    DROTRONLPOptimizer,
)

# 网格搜索
transfer_search = TransferSearch(system=system, dynamics=dynamics)
results = transfer_search.search(dro_orbit, ro_orbit)

# NLP 优化
optimizer = DROTRONLPOptimizer(system=system, dynamics=dynamics)
nlp_result = optimizer.optimize(initial_variables=initial_vars)
```

## 几何示意

```
         月球
          •
                    目标 RO
                   (椭圆)
                      
   出发 DRO          ballistic 弧段
   (绕月球) ----/---------\----
                        \       /
                         \     /
                          \   /
                           \ /
                            •
                      地球
```

## 物理参数

| 符号 | 值 | 描述 |
|------|-----|------|
| μ | 1.21506683×10⁻² | 地月质量比 |
| DU | 384,405 km | 距离单位 |
| TU | 4.34811305 天 | 时间单位 |
| VU | 1023.23281 m/s | 速度单位 |
