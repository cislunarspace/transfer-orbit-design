# 同伦法星历模型轨道修正

## 目标
实现基于摄动天体逐步引入的同伦法，加速 CR3BP → 星历模型的 DRO 轨道修正，替代直接多重打靶法。

## 建模方案
论文公式 H = (1-λ)·F_CR3BP + λ·F_Ephemeris 存在量纲不匹配问题（CR3BP 无量纲 vs Ephemeris 有量纲 km/km·s⁻¹）。

**修正方案（方案 A）**：在 J2000 坐标系下，逐步引入摄动天体（Sun）的引力：
- λ=0：仅 Earth + Moon（接近 CRTBP 的星历模型）
- λ→1：逐步增加 Sun 引力权重至满值
- H(x,λ) 始终在 J2000 下、有量纲、物理意义一致

## 同伦路径
```
CR3BP DRO → 坐标转换 → J2000 patch points
                         ↓
              Phase 1: λ=0, E+M only, MultipleShooting 修正
                         ↓
              Phase 2: λ: 0→1, 逐步引入 Sun, 自然延拓
              每步: 前一步解 → MultipleShooting 修正 → 收敛则前进
```

## 任务列表
- [x] 1. 验证论文同伦法数学建模，识别问题
- [x] 2. 在 e2m2e 中实现 HomotopyEphemerisDynamics 类
- [x] 3. 更新 e2m2e 导出
- [x] 4. 编写 homotopy_dro_to_ephemeris.py 脚本
- [x] 5. 运行验证，与直接多重打靶法对比（迭代次数、收敛率）

## 备注
- HomotopyEphemerisDynamics 继承 EphemerisDynamics，重写 equations_of_motion 和 equations_with_stm
- 摄动天体的加速度及其 Jacobian 均乘以 λ
- 自然延拓先用固定步长 Δλ=0.1，不收敛则减半
