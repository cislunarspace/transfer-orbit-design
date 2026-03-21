---
goal: "复现 Cui et al. (2025) 两脉冲转移轨道设计论文"
version: "1.1"
date_created: 2026-03-20
last_updated: 2026-03-21
owner: transfer-orbit-design
status: 'In progress'
tags: ['feature', 'replication', 'orbital-mechanics', 'cr3bp', 'br4bp', 'ephemeris']
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

本计划旨在复现论文 "Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits" (Cui et al., 2025, JGCD) 的研究成果，实现在地月系统中从 DRO 到 RO 的两脉冲转移轨道设计。

## 1. Requirements & Constraints

- **REQ-001**: 实现 CR3BP 动力学模型（已完成，`e2m2e/core/dynamics.py`）
- **REQ-002**: 实现微分修正算法（已完成，`e2m2e/algorithms/differential_correction.py`）
- **REQ-003**: 实现自然参数延拓算法（已完成，`e2m2e/algorithms/continuation.py`）
- **REQ-004**: 生成完整 DRO 族并计算 Jacobi 常数与稳定性指标（已完成）
- **REQ-005**: 生成 RO 族种子（已完成 phase1_generate_ro.py）
- **REQ-006**: 完整 RO 族延拓（延拓参数和范围待确定）
- **REQ-007**: 生成 3D RRO 和 ARO 族（切分岔计算）
  - 实现分岔检测算法（检测单值矩阵特征值 λ ≈ 1）
  - 从 3:2/3:1 RO 族识别分岔点并生成 RRO 族
  - 固定 x0 改变 z0 幅值延拓生成 ARO 族
- **REQ-008**: 实现搜索阶段算法（网格化搜索 + 前向积分 + 筛选）
- **REQ-009**: 实现优化阶段算法（NLP + SQP 求解器）
- **REQ-010**: 实现 BR4BP 动力学模型
- **REQ-011**: 建立基于 DE438 星历的 RNBP 动力学模型
- **REQ-012**: 实现定时多段射击法（fixed-time multiple shooting）
- **SEC-001**: 确保转移轨道不撞击地球和月球
- **CON-001**: 转移问题转化为 NLP 问题，优化目标 $J(y) = \Delta v_1 + \Delta v_2$
- **CON-002**: 使用 DE438 星历进行真实场景验证
- **GUD-001**: 轨道族生成使用自然参数延拓或伪弧长延拓
- **GUD-002**: 微分修正算法参考 `DifferentialCorrection` 类实现
- **PAT-001**: 轨道数据结构使用 `Orbit` 和 `OrbitFamily` 类（`e2m2e/core/orbit.py`）

## 2. Implementation Steps

### Implementation Phase 1: 基线轨道族生成

- GOAL-001: 完成 DRO 和 RO 族生成，为转移设计提供基线轨道

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | DRO 族生成（已完成：`scripts/phase1_generate_dro.py`） | ✅ | 2026-03-20 |
| TASK-002 | DRO 族 Jacobi 常数与稳定性指标计算 | ✅ | 2026-03-20 |
| TASK-003 | RO 族种子搜索（已完成：`scripts/phase1_generate_ro.py`） | ✅ | 2026-03-20 |
| TASK-004 | 3:2 RO 族完整延拓（确定延拓参数：x0 范围 [−1.2, −0.8]，步长 0.005） | ✅ | 2026-03-21 |
| TASK-005 | 3:1 RO 族完整延拓（确定延拓参数：x0 范围 [−1.0, −0.7]，步长 0.005） | ✅ | 2026-03-21 |
| TASK-006 | 切分岔计算生成 3D RRO 族（`scripts/phase1_generate_3d_ro.py`） | | |

### TASK-006 细化分解

**目标**: 通过检测平面 RO 族的特征值分岔点，生成 3D RRO（反射共振轨道）族

**技术背景**:
- 论文 Section II.D: "当单值矩阵的一对特征值在实轴 +1 处碰撞时，发生切分岔，伴随 3D 轨道的生成"
- RRO 特征：关于 x-z 平面对称（Mirror Theorem），类似于 LPO 中的 Halo 轨道
- ARO 特征：关于 x 轴对称，类似于 LPO 中的轴向轨道

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-006-01 | **实现分岔检测算法**: 在延拓过程中检测单值矩阵特征值是否接近 +1 | P0 | - |
| SUB-006-02 | **确定分岔点参数**: 从 3:2 RO 族中识别 x0 ≈ -1.0878（对应 Az=0.2 的 RRO） | P0 | SUB-006-01 |
| SUB-006-03 | **配置 3D 对称修正器**: 使用 `setup_3D_symmetric_x_fixed_x0` 配置 RRO 微分修正 | P0 | - |
| SUB-006-04 | **实现 RRO 族延拓**: 从分岔点出发，固定 x0 改变 z0 幅值延拓生成 RRO 族 | P0 | SUB-006-02, SUB-006-03 |
| SUB-006-05 | **验证 RRO 轨道参数**: 对比论文 Table 2 中 3:2 RRO (x=-1.0878, z=0.2, Az=0.2) | P1 | SUB-006-04 |
| SUB-006-06 | **生成 3:1 RRO 族**: 同样方法处理 3:1 RO 族（分岔点 x0 ≈ -0.7660） | P1 | SUB-006-01 ~ SUB-006-05 |
| SUB-006-07 | **编写 `scripts/phase1_generate_3d_ro.py`**: 整合以上模块为可执行脚本 | P0 | SUB-006-04 |

**实现方案**:

```python
# 1. 加载已有的 3:2 RO 族数据
# 2. 对每个轨道计算单值矩阵特征值
# 3. 检测 |λ - 1| < tolerance 的分岔点
# 4. 在分岔点处提取状态，配置 3D 修正器
# 5. 以 z0 为延拓参数继续延拓生成 RRO 族
```

**参考代码**:
- `e2m2e/algorithms/stability.py`: `compute_floquet_multipliers()`, `compute_stability_index()`
- `e2m2e/algorithms/differential_correction.py`: `setup_3D_symmetric_x_fixed_x0()`
- `e2m2e/algorithms/continuation.py`: `natural_continuation()`

| TASK-007 | 切分岔计算生成 ARO 族（$A_z = 0.2$） | | |

### TASK-007 细化分解

**目标**: 通过分岔生成 ARO（轴向共振轨道）族

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-007-01 | **配置 ARO 微分修正器**: 使用 `setup_3D_symmetric_xz_fixed_z0` 固定 z0 延拓 x0 | P0 | - |
| SUB-007-02 | **确定 ARO 族分岔起点**: 从论文 Table 2 获取 3:2 ARO 种子 (x=-1.1318, z=0.1999) | P0 | - |
| SUB-007-03 | **实现 ARO 族延拓**: 以 x0 为参数固定 z0 延拓生成 ARO 族 | P0 | SUB-007-01 |
| SUB-007-04 | **验证 ARO 轨道参数**: 对比论文 Table 2 中 3:2 ARO 参数 | P1 | SUB-007-03 |
| SUB-007-05 | **生成 3:1 ARO 族**: 同样方法处理 3:1 RO 族 | P1 | SUB-007-01 ~ SUB-007-04 |
| TASK-008a | 修复轨道族绘图点连接顺序问题（使用最近邻排序算法替代数据顺序连接） | ✅ | 2026-03-21 |

### Implementation Phase 2: CR3BP 转移轨道设计

- GOAL-002: 实现"搜索-优化"两步法，设计 CR3BP 中的 DRO→RO 转移轨道

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | 实现网格化搜索算法（搜索变量：出发点位置、切向速度比 $\alpha$、法向速度比 $\beta$） | | |
| TASK-010 | 实现前向积分模块（使用 `e2m2e/core/dynamics.py` CR3BP 积分器） | | |
| TASK-011 | 实现轨迹筛选模块（与终端轨道相交或距离局部最小） | | |
| TASK-012 | 实现 NLP 问题构建（优化变量：$y = \{\alpha, T, t_{ins}\}$） | | |
| TASK-013 | 实现 SQP 求解器（调用 scipy.optimize 或其他 NLP 求解器） | | |
| TASK-014 | 计算 4 种平面转移路径（2:1/3:1 DRO → 3:2/3:1 RO） | | |
| TASK-015 | 分类三种典型转移类型（直接转移、LGA 转移、外部转移） | | |
| TASK-016 | 绘制解平面（转移时间 vs 总脉冲） | | |
| TASK-017 | 分析出发点和插入点分布（四分位图） | | |
| TASK-018 | 计算非平面转移（2:1 DRO → 3D RO） | | |

### Implementation Phase 3: BR4BP 转移轨道设计

- GOAL-003: 将太阳引力纳入模型，精化转移轨道设计

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-019 | 实现 BR4BP 动力学模型（`e2m2e/core/dynamics.py` 新增类） | | |
| TASK-020 | 将太阳初始相位 $\theta_{s0}$ 纳入搜索/优化变量 | | |
| TASK-021 | 计算 BR4BP 中的转移解 | | |
| TASK-022 | 对比 CR3BP 与 BR4BP 转移解差异 | | |
| TASK-023 | 分析太阳相位对转移轨道的影响（延拓方法） | | |
| TASK-024 | 识别 WSB-like 外部转移 | | |

### Implementation Phase 4: 星历模型验证

- GOAL-004: 在真实星历模型中验证转移轨道可行性

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | 建立基于 DE438 星历的 RNBP 动力学模型 | | |
| TASK-026 | 实现定时多段射击法（fixed-time multiple shooting） | | |
| TASK-027 | 将三种典型转移轨道转入星历模型 | | |
| TASK-028 | 分析不同出发历元对转移代价的影响 | | |

## 3. Alternatives

- **ALT-001**: 直接使用 BR4BP 而跳过 CR3BP — 不采用，因为论文明确使用 CR3BP 作为初步设计工具
- **ALT-002**: 使用 STK/GMAT 代替自实现 — 不采用，保持代码可控性和复现透明度
- **ALT-003**: 仅计算平面转移，跳过 3D 转移 — 不采用，论文包含非平面转移分析

## 4. Dependencies

- **DEP-001**: `e2m2e` 核心库（`algorithms/`, `core/`, `transfer/` 模块）
- **DEP-002**: DE438 星历文件（SPICE kernels）
- **DEP-003**: scipy.optimize（SQP 求解器）
- **DEP-004**: matplotlib（可视化）
- **DEP-005**: numpy（数值计算）

## 5. Files

- **FILE-001**: `transfer-orbit-design/scripts/phase1_generate_dro.py` — DRO 族生成脚本
- **FILE-002**: `transfer-orbit-design/scripts/phase1_generate_ro.py` — RO 族生成脚本
- **FILE-003**: `transfer-orbit-design/scripts/phase1_generate_3d_ro.py` — 3D RO 族生成脚本（待创建）
- **FILE-004**: `transfer-orbit-design/scripts/phase2_transfer_search.py` — 转移搜索算法脚本（待创建）
- **FILE-005**: `e2m2e/e2m2e/core/dynamics.py` — CR3BP/BR4BP 动力学模型
- **FILE-006**: `e2m2e/e2m2e/algorithms/differential_correction.py` — 微分修正算法
- **FILE-007**: `e2m2e/e2m2e/algorithms/continuation.py` — 轨道族延拓算法
- **FILE-008**: `e2m2e/e2m2e/core/orbit.py` — 轨道数据结构
- **FILE-009**: `transfer-orbit-design/output/phase1_dro/` — DRO 族输出
- **FILE-010**: `transfer-orbit-design/output/phase1_ro/` — RO 族输出

## 6. Testing

- **TEST-001**: 验证 DRO 族对称性（关于 x 轴对称，$y(T/2)=0, v_x(T/2)=0$）
- **TEST-002**: 验证 DRO 族 Jacobi 常数单调性与稳定性指标
- **TEST-003**: 验证 RO 族周期满足 3:2 和 3:1 共振比（误差 < 1%）
- **TEST-004**: 验证转移轨道满足位置连续性约束
- **TEST-005**: 验证转移轨道不撞击地球（距离 > 1 DU）和月球（距离 > 0.5 DU）
- **TEST-006**: 对比 CR3BP 与 BR4BP 转移解偏差（预期 < 5%）

## 7. Risks & Assumptions

- **RISK-001**: RO 族延拓可能遇到分岔或不稳定区域 — 缓解：使用伪弧长延拓方法
- **RISK-002**: NLP 求解可能不收敛 — 缓解：使用搜索阶段结果作为初始猜测
- **RISK-003**: BR4BP 计算量大 — 缓解：使用延拓方法减少优化变量
- **ASSUMPTION-001**: 论文参数（μ, DU, TU, VU）准确无误
- **ASSUMPTION-002**: DE438 星历文件可用且格式正确
- **ASSUMPTION-003**: DRO 和 RO 族存在且可以通过微分修正收敛

## 8. Related Specifications / Further Reading

- [Cui et al. (2025) Two-Impulse Transfers from DRO to RO, JGCD](https://doi.org/10.2514/1.G008582)
- [Szebehely (1967) Theory of Orbit: The Restricted Problem of Three Bodies](https://www.sciencedirect.com/book/9780123957328/theory-of-orbit)
- [e2m2e 核心库文档](../e2m2e/README.md)
