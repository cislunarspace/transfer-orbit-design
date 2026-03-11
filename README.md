# Transfer Orbit Design — DRO to RO Two-Impulse Transfer

## 项目概述

本项目旨在复现以下论文的研究成果：

> **Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits**  
> Shuhao Cui, Yue Wang, Ruikang Zhang, Hao Zhang, Yang Gao  
> *Journal of Guidance, Control, and Dynamics*, Vol. 48, No. 6, June 2025  
> DOI: [10.2514/1.G008582](https://doi.org/10.2514/1.G008582)

该论文研究了地月系统中从远距离逆行轨道（DRO）到共振轨道（RO）的两脉冲转移轨道设计问题。由于 DRO 和 RO 均为稳定轨道，无法利用不稳定流形结构，论文提出了一种"搜索-优化"两步法来设计转移轨道，并在 CR3BP、BR4BP 和星历模型中分别进行了计算与验证。

## 论文核心内容

### 动力学模型

| 模型 | 说明 |
|------|------|
| **CR3BP**（圆型限制性三体问题） | 地月系统基本模型，用于计算基线轨道和初步转移设计 |
| **BR4BP**（双圆限制性四体问题） | 在 CR3BP 基础上加入太阳引力，用于转移轨道精化 |
| **星历模型**（Ephemeris Model） | 基于 DE438 星历的限制性 N 体问题，用于真实场景验证 |

### 基线轨道

- **初始轨道**：2:1 DRO 和 3:1 DRO（周期分别为月球恒星周期的 1/2 和 1/3）
- **终端轨道（平面）**：3:2 RO 和 3:1 RO（精确共振比的轨道）
- **终端轨道（非平面）**：3D 反射共振轨道（RRO）和轴向共振轨道（ARO），z 振幅 $A_z = 0.2$

### 两步转移设计方法

1. **搜索阶段（Search Phase）**
   - 搜索变量：出发点位置、切向速度比 $\alpha$、法向速度比 $\beta$（非平面情况）、太阳初始相位 $\theta_{s0}$（BR4BP）
   - 对搜索变量在设定范围内进行网格化，前向积分获取可行转移轨迹
   - 筛选与终端轨道相交或距离局部最小的轨迹作为初始猜测

2. **优化阶段（Optimization Phase）**
   - 将转移问题转化为非线性规划（NLP）问题
   - 优化变量：$y = \{\alpha, T, t_{ins}\}$（平面 CR3BP 情况）
   - 目标函数：$J(y) = \Delta v_1 + \Delta v_2$（最小化总脉冲）
   - 约束条件：位置连续性、速度方向约束、避免撞击地球和月球
   - 使用序列二次规划（SQP）算法求解

### 三种典型转移类型

| 转移类型 | 特点 | 转移时间 | 燃料消耗 |
|----------|------|----------|----------|
| **直接转移（Direct Transfer）** | 短时间，近似椭圆轨道，不到一圈地球 | < 20 天 | 较高 |
| **月球借力转移（LGA Transfer）** | 利用月球近飞段改变速度方向，多圈调相 | 60–80 天 | 最低 |
| **外部转移（External Transfer）** | 远地点超过 3 倍地月距离；BR4BP 中类似 WSB 转移 | 60–100 天 | 中等 |

### 关键物理参数

| 符号 | 值 | 含义 |
|------|-----|------|
| $\mu$ | $1.21506683 \times 10^{-2}$ | 地月系统质量比 |
| $m_s$ | $3.28900541 \times 10^{5}$ | 太阳无量纲质量 |
| $\omega_s$ | $9.25195985 \times 10^{-1}$ | 太阳无量纲角速度 |
| $\rho$ | $3.88811143 \times 10^{2}$ | 太阳至地月质心无量纲距离 |
| DU | $3.84405 \times 10^{5}$ km | 距离单位 |
| TU | 4.34811305 天 | 时间单位 |
| VU | 1023.23281 m/s | 速度单位 |

## 复现计划

### 阶段一：基线轨道生成 ✅ 已完成

- [x] CR3BP 动力学模型实现
- [x] 微分修正算法（2D 对称 x 轨道）
- [x] 自然参数延拓（生成 DRO 族）
- [x] 生成完整 DRO 族并计算 Jacobi 常数与稳定性指标
- [ ] 生成 3:2 和 3:1 RO 族（平面共振轨道）
- [ ] 生成 3D RO（RRO 和 ARO）——通过切分岔计算

### 阶段二：CR3BP 中的转移设计

- [ ] 实现搜索阶段算法（网格化搜索变量 + 前向积分 + 筛选）
- [ ] 实现优化阶段算法（NLP 问题，SQP 求解器）
- [ ] 计算四种平面转移路径（2:1/3:1 DRO → 3:2/3:1 RO）
- [ ] 分类三种典型转移类型（直接转移、LGA 转移、外部转移）
- [ ] 绘制解平面（转移时间 vs 总脉冲）
- [ ] 分析出发点和插入点分布（四分位图）
- [ ] 计算非平面转移（2:1 DRO → 3D RO）

### 阶段三：BR4BP 中的转移设计

- [ ] 实现 BR4BP 动力学模型
- [ ] 将太阳初始相位纳入搜索/优化变量
- [ ] 计算 BR4BP 中的转移解并与 CR3BP 对比
- [ ] 分析太阳相位对转移轨道的影响（延拓方法）
- [ ] 识别 WSB-like 外部转移

### 阶段四：星历模型验证

- [ ] 建立基于 DE438 星历的 RNBP 动力学模型
- [ ] 实现定时多段射击法（fixed-time multiple shooting）
- [ ] 将三种典型转移轨道转入星历模型
- [ ] 分析不同出发历元对转移代价的影响

## 当前代码架构

代码采用面向过程与面向对象两套实现并行开发：

### 面向过程版本

- `CoordinateTrans/`：坐标转换矩阵相关函数
- `Dynamics/`：动力学外推函数（CR3BP）
- `Parameters/`：系统参数定义
- `Funcs/`：辅助功能函数（Jacobi 常数、拉格朗日点、稳定性分析等）
- `Main/`：主函数与高层算法（微分修正、延拓）
- `Test/`：测试脚本

### 面向对象版本（`OOP/`）

- `CR3BP_System.py`：三体系统参数管理
- `CR3BP_Dynamics.py`：动力学方程与状态转移矩阵
- `DifferentialCorrection.py`：微分修正算法
- `Continuation.py`：自然参数延拓
- `StabilityAnalysis.py`：稳定性分析
- `Orbit.py`：轨道数据结构
- `Visualization.py`：可视化工具
- `CoordinateTransformation.py`：坐标转换

### 数据与环境

- `Spice/`：星历文件（SPICE kernels）
- `envi/`：Python 虚拟环境

## 参考文献

[1] Szebehely V G. Theory of orbit: the restricted problem of three bodies[M]. Place of publication not identified: Academic Press, 1967.

[2] Cui S, Wang Y, Zhang R, et al. Two-impulse transfers from lunar distant retrograde orbits to resonant orbits[J]. Journal Of Guidance, Control, And Dynamics, 2025, 48(6): 1348-1365.
