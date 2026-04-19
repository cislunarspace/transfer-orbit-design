---
sidebar_position: 10
---

# 微分修正

## 目的

微分修正迭代改进初始猜测以满足周期轨道约束。这对于在 CR3BP 中找到精确的周期轨道至关重要。

## 理论

给定初始状态 $\mathbf{x}_0$ 和期望周期 $T$，目标是满足：

$$\mathbf{F}(\mathbf{x}_0, T) = \mathbf{x}(T) - \mathbf{x}_0 = \mathbf{0}$$

对于对称轨道（如 DRO），我们利用对称条件来降低维度。

## 2D 对称 X-Fixed 算法

对于关于 x 轴对称的平面轨道：

### 约束条件

- $y(0) = 0$ — 在 x 轴上出发
- $v_x(0) = 0$ — 垂直离开
- $y(T/2) = 0$ — 半周期时穿过 x 轴
- $v_x(T/2) = 0$ — 垂直穿过

### 状态向量

仅有两个自由参数：$x_0$ 和 $\dot{y}_0$

### 修正过程

```
1. 从初始状态积分半个周期
2. 计算半周期时的误差：
   - e₁ = y(T/2) 
   - e₂ = v_x(T/2)
3. 计算误差关于 [x₀, vy₀] 的 Jacobian
4. 求解线性系统得到修正量 Δ[x₀, vy₀]
5. 更新状态并重复直到收敛
```

### 实现

```python
from e2m2e.algorithms import DifferentialCorrection

corrector = DifferentialCorrection(dynamic=dynamics)
corrector.setup_2D_symmetric_x_fixed_x0(x0=0.7919)
corrected_orbit = corrector.iterate_correction(initial_guess)
```

## 多点射击变体

对于困难轨道，多点射击可以提高收敛性：

- 将轨迹分成 $N$ 段
- 每段有一个中点修正
- 所有中点处有连续性约束
- 线性系统更大但收敛性更好

## 收敛标准

| 参数 | 典型值 |
|------|--------|
| 位置容差 | 1e-10 |
| 速度容差 | 1e-10 |
| 最大迭代次数 | 50 |
