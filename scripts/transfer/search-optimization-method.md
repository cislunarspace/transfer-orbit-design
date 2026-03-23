# DRO-RO 转移轨道搜索优化方法

本文档描述了从远距离逆行轨道（DRO）到共振轨道（RO）的双脉冲转移轨道设计的两步法搜索优化方法，基于论文 [Cui et al., 2025]。

---

## 1. 方法概述

由于 DRO 和 RO 均属于稳定周期轨道，无法利用不稳定流形结构，因此采用**搜索阶段（Search Phase）** + **优化阶段（Optimization Phase）**的两步法设计双脉冲转移轨道。

```
搜索阶段 → 优化阶段
   ↓            ↓
网格搜索    NLP求解 (SQP)
   ↓            ↓
初始可行解  最优转移轨道
```

---

## 2. 搜索阶段

### 2.1 搜索变量定义

搜索变量必须能够完整描述整个转移过程，一旦给定变量，转移轨道即被唯一确定。

| 变量 | 含义 | 范围/数量 |
|------|------|----------|
| 出发点 (Departure Point) | 初始轨道上的离散位置 | 200 个等时间间隔点 |
| α (Alpha) | 切向速度比例系数 | [0.5, 2.5]，1001 个网格点 |
| β (Beta) | 法向速度比例系数 | [-0.5, 0.5]，101 个网格点（非平面转移） |
| θs0 (Sun Phase) | 太阳初始相位 | [0, 2π]，18 个网格点（BR4BP 模型） |

**论文 Table 3** 给出了推荐的搜索参数设置。

### 2.2 速度扰动模型

在出发点施加双脉冲转移的第一次脉冲：

$$
\pmb{v}_{dep} = \alpha \cdot \pmb{v}_{tangential} + \beta \cdot \pmb{v}_{normal}
$$

- **α**：切向速度比例，控制轨道面内的速度大小
- **β**：法向速度比例，控制轨道面外的速度分量（三维情况）

### 2.3 前向积分与轨迹筛选

1. 对网格中的每个参数组合进行**前向积分**
2. 检测转移轨迹是否与目标轨道**相交**
3. 检测是否存在**局部最小距离**
4. 记录满足条件的候选解作为优化阶段的初始猜测

```
网格搜索流程:
for each departure_point in DRO:
    for each alpha in [alpha_min, alpha_max]:
        for each beta in [beta_min, beta_max]:
            v_dep = alpha * v_tang + beta * v_norm
            integrate_trajectory(v_dep, T_max)
            if intersects_RO or local_min_distance:
                record_candidate()
```

### 2.4 搜索参数配置

代码中的默认搜索参数（对应论文 Table 3）：

```python
N_DEPARTURE = 200   # 出发点采样数量
N_ALPHA = 101       # α 方向网格点数
N_BETA = 21         # β 方向网格点数
MAX_TRANSFER_TIME = 15.0  # 最大转移时间 (CR3BP 无量纲时间)

ALPHA_MIN, ALPHA_MAX = 0.5, 2.5
BETA_MIN, BETA_MAX = -0.5, 0.5
```

---

## 3. 优化阶段

### 3.1 NLP 问题构建

将双脉冲转移问题转换为非线性规划（NLP）问题，在固定出发点的情况下优化燃料消耗。

**优化变量**（平面转移）：

$$
\pmb{y} = \{\alpha, T, t_{ins}\}
$$

- α：切向速度比例
- T：转移时间
- t_ins：从远地点到插入点的时间

**目标函数**（最小化总脉冲）：

$$
J(\pmb{y}) = \Delta v_1 + \Delta v_2
$$

**脉冲计算**：

$$
\Delta v_1 = \sqrt{(\dot{x}_i - \dot{x}_{dep})^2 + (\dot{y}_i - \dot{y}_{dep})^2 + (\dot{z}_i - \dot{z}_{dep})^2}
$$

$$
\Delta v_2 = \sqrt{(\dot{x}_{ins} - \dot{x}_f)^2 + (\dot{y}_{ins} - \dot{y}_f)^2 + (\dot{z}_{ins} - \dot{z}_f)^2}
$$

### 3.2 约束条件

1. **位置连续性约束**（插入点重合）：
   $$
   (x_f - x_{ins})^2 + (y_f - y_{ins})^2 + (z_f - z_{ins})^2 = 0
   $$

2. **速度平行约束**（平面情况）：
   $$
   \frac{\pmb{v}_f \cdot \pmb{v}_{ins}}{|\pmb{v}_f| |\pmb{v}_{ins}|} - 1 = 0
   $$

3. **天体碰撞约束**：
   $$
   r_e^2 - (x + \mu)^2 - y^2 - z^2 < 0 \quad \text{（地球）}
   $$
   $$
   r_m^2 - (x + \mu - 1)^2 - y^2 - z^2 < 0 \quad \text{（月球）}
   $$

### 3.3 松弛速度约束

为扩大解空间，可将速度平行约束从等式松弛为不等式：

$$
\cos\theta - \frac{\pmb{v}_f \cdot \pmb{v}_{ins}}{|\pmb{v}_f| |\pmb{v}_{ins}|} < 0
$$

其中 θ 为允许的速度角度偏差。

### 3.4 求解器配置

论文使用 MATLAB 的 `fmincon` 求解器，采用序贯二次规划（SQP）算法：

- 目标函数容差：10⁻¹⁰
- 约束容差：10⁻¹⁰
- 积分方法：7-8 阶变步长 Runge-Kutta，精度 10⁻¹²

---

## 4. 转移轨道分类

优化阶段得到的解平面（Solution Plane）中可识别三种典型转移类型：

### 4.1 直接转移 (Direct Transfer)

- **位置**：解平面最左侧
- **特征**：转移时间短（通常 < 20 天）
- **几何**：近椭圆轨道，在惯性系中绕地球公转不到一周

### 4.2 月球引力辅助转移 (LGA Transfer)

- **位置**：解平面底部
- **特征**：靠近月球飞越，显著改变速度方向
- **优势**：比直接转移节省超过 200 m/s 的燃料

### 4.3 外部转移 (External Transfer)

- **位置**：解平面中分散分布
- **特征**：远地点高度超过地月距离的 3 倍
- **特点**：对太阳相位敏感，在 BR4BP 中类似于弱稳定边界（WSB）转移

---

## 5. 代码实现

### 5.1 核心类

| 类名 | 位置 | 功能 |
|------|------|------|
| `TransferSearchConfig` | `e2m2e/transfer/dro_ro_search.py` | 搜索参数配置 |
| `DROROTransferSearch` | `e2m2e/transfer/dro_ro_search.py` | 网格搜索执行 |
| `DROTRONLPOptimizer` | `e2m2e/transfer/dro_ro_nlp.py` | NLP 问题构建与求解 |

### 5.2 使用流程

**步骤 1：网格搜索**

```python
from e2m2e.transfer.dro_ro_search import DROROTransferSearch, TransferSearchConfig

config = TransferSearchConfig(
    alpha_min=0.5, alpha_max=2.5, n_alpha=101,
    beta_min=-0.5, beta_max=0.5, n_beta=21,
    n_departure=200, max_transfer_time=15.0
)

searcher = DROROTransferSearch(system=system, dynamics=dynamics, config=config)
results = searcher.grid_search(departure_orbit=dro_orbit, arrival_orbit=ro_orbit)
```

**步骤 2：NLP 优化**

```python
from e2m2e.transfer.dro_ro_nlp import DROTRONLPOptimizer

optimizer = DROTRONLPOptimizer(
    system=system, dynamics=dynamics,
    departure_orbit=dro_orbit, arrival_orbit=ro_orbit,
    departure_state=departure_state
)

result = optimizer.optimize(
    initial_guess=NLPOptimizationVariables(alpha=1.0, transfer_time=15.0, t_ins=5.0),
    use_relaxed_velocity_constraint=True,
    velocity_angle_constraint=np.deg2rad(5.0)
)
```

### 5.3 搜索脚本

| 脚本 | 功能 |
|------|------|
| `scripts/transfer/grid_search.py` | 执行网格搜索，生成候选解 |
| `scripts/transfer/optimize.py` | 对候选解进行 NLP 优化 |
| `scripts/transfer/plot_transfer.py` | 可视化转移轨迹 |

---

## 6. 参考文献

- Cui, S., et al. (2025). "Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits." *Journal of Guidance, Control, and Dynamics*. https://doi.org/10.2514/1.G008582
