# Phase 2 追踪看板

## 📊 状态总览

| 状态 | 数量 | 图标 |
|------|------|------|
| 🔵 未开始 | 6 | ██████░░░░ |
| 🟡 进行中 | 1 | █░░░░░░░░░ |
| 🟢 已完成 | 3 | ███░░░░░░░ |
| ⚠️ 阻塞 | 0 | ░░░░░░░░░░ |

---

## 🎯 Sprint目标

**Sprint 1 (Week 1-2): 核心框架**
- [x] TASK-009: 转移搜索变量定义
- [x] TASK-010: 出发点选择算法
- [x] TASK-011: 速度计算函数
- [x] TASK-012: 前向积分模块
- [x] TASK-013: 轨迹筛选模块

**Sprint 2 (Week 3-4): 优化求解**
- [ ] TASK-014: NLP问题构建
- [ ] TASK-015: COPT求解器集成
- [ ] TASK-016: 求解结果解析

**Sprint 3 (Week 5-6): 集成与验证**
- [ ] TASK-017: 4种转移路径计算
- [ ] TASK-018: 解平面可视化
- [ ] TASK-019: 转移类型分类
- [ ] TASK-020: 精度验证

---

## 📋 任务详情

### TASK-009: 转移搜索变量定义
**类型**: 🟢 Completed | **优先级**: P0 | **预估工时**: 2h

**内容**:
- 定义`TransferSearchVariables`数据结构
- 定义`TransferNLPVariables`数据结构
- 定义`TransferResult`数据结构

**验收标准**:
- [x] `TransferSearchVariables`包含departure_point, alpha, beta, t_departure
- [x] `TransferNLPVariables`包含alpha, T, t_ins
- [x] `TransferResult`包含states, dv_total, transfer_type

**依赖**: None

**Labels**: `task`, `phase-2`, `data-structure`

---

### TASK-010: 出发点选择算法
**类型**: 🟢 Completed | **优先级**: P0 | **预估工时**: 4h

**内容**:
- 实现DRO族等间隔采样
- 实现时间参数化选择
- 实现基于能量的选择

**验收标准**:
- [x] 可指定采样点数
- [x] 可指定能量范围
- [x] 返回正确的状态向量

**依赖**: TASK-009

**Labels**: `task`, `phase-2`, `search-phase`

---

### TASK-011: 速度计算函数
**类型**: 🟢 Completed | **优先级**: P0 | **预估工时**: 4h

**内容**:
- 实现compute_departure_velocity
- 实现α,β参数到速度的映射
- 实现切向/法向速度分解

**验收标准**:
- [x] 输入departure_point, α, β返回速度向量
- [x] 速度方向正确（切向）
- [x] 速度大小符合比例关系

**依赖**: TASK-009, TASK-010

**Labels**: `task`, `phase-2`, `search-phase`

---

### TASK-012: 前向积分模块
**类型**: 🟢 Completed | **优先级**: P0 | **预估工时**: 6h

**内容**:
- 实现单条轨迹前向积分
- 实现并行批量积分
- 实现积分结果缓存

**验收标准**:
- [x] 积分结果与SaturnV一致
- [x] 支持变步长积分
- [x] 可设置最大积分时间

**依赖**: TASK-010, TASK-011

**Labels**: `task`, `phase-2`, `search-phase`

---

### TASK-013: 轨迹筛选模块
**类型**: 🟢 Completed | **优先级**: P0 | **预估工时**: 4h

**内容**:
- 实现RO相交检测
- 实现局部最小距离检测
- 实现候选解排序

**验收标准**:
- [x] 正确检测RO相交
- [x] 正确计算最小距离
- [x] 正确筛选有效候选

**依赖**: TASK-012

**Labels**: `task`, `phase-2`, `search-phase`

**备注**: 网格搜索v2已成功运行，45个候选解中33个可行解

---

### TASK-014: NLP问题构建
**类型**: 🔵 ToDo | **优先级**: P0 | **预估工时**: 8h

**内容**:
- 实现目标函数 J(y) = Δv₁ + Δv₂
- 实现位置连续约束
- 实现速度角度约束
- 实现不撞击约束

**验收标准**:
- [ ] 目标函数梯度正确
- [ ] 约束函数雅可比正确
- [ ] 约束边界正确

**依赖**: TASK-009, TASK-013

**Labels**: `task`, `phase-2`, `optimization-phase`

---

### TASK-015: COPT求解器集成
**类型**: 🔵 ToDo | **优先级**: P0 | **预估工时**: 6h

**内容**:
- 验证COPT安装
- 实现COPT NLPSolver封装
- 实现scipy回退方案

**验收标准**:
- [ ] COPT可用时正常求解
- [ ] COPT不可用时切换scipy
- [ ] 求解参数可配置

**依赖**: TASK-014

**Labels**: `task`, `phase-2`, `solver-integration`

---

### TASK-016: 求解结果解析
**类型**: 🔵 ToDo | **优先级**: P0 | **预估工时**: 4h

**内容**:
- 实现最优解提取
- 实现约束违反度计算
- 实现收敛性判断

**验收标准**:
- [ ] 正确提取最优变量
- [ ] 正确计算约束违反度
- [ ] 正确判断求解状态

**依赖**: TASK-015

**Labels**: `task`, `phase-2`, `optimization-phase`

---

### TASK-017: 4种转移路径计算
**类型**: 🔵 ToDo | **优先级**: P1 | **预估工时**: 8h

**内容**:
- 计算DRO(2:1)→RO(3:2)转移
- 计算DRO(3:1)→RO(3:2)转移
- 计算DRO(2:1)→RO(3:1)转移
- 计算DRO(3:1)→RO(3:1)转移

**验收标准**:
- [ ] 4种转移均可计算
- [ ] 结果保存为JSON
- [ ] 与论文Table 4对比偏差<10%

**依赖**: TASK-016

**Labels**: `task`, `phase-2`, `transfer-computation`

---

### TASK-018: 解平面可视化
**类型**: 🔵 ToDo | **优先级**: P1 | **预估工时**: 6h

**内容**:
- 实现T-Δv解平面图
- 实现能量着色
- 实现转移类型标记

**验收标准**:
- [ ] 解平面图与论文Fig.6一致
- [ ] Pareto前沿正确标识
- [ ] 三种转移类型颜色区分

**依赖**: TASK-017

**Labels**: `task`, `phase-2`, `visualization`

---

### TASK-019: 转移类型分类
**类型**: 🔵 ToDo | **优先级**: P1 | **预估工时**: 4h

**内容**:
- 实现直接转移分类
- 实现LGA转移分类
- 实现外部转移分类

**验收标准**:
- [ ] 分类准确率>95%
- [ ] 分类结果与论文一致
- [ ] 分类阈值可配置

**依赖**: TASK-017

**Labels**: `task`, `phase-2`, `classification`

---

### TASK-020: 精度验证
**类型**: 🔵 ToDo | **优先级**: P1 | **预估工时**: 6h

**内容**:
- 对比论文Table 4数据
- 计算偏差统计量
- 生成验证报告

**验收标准**:
- [ ] Δv偏差<10%
- [ ] T偏差<15%
- [ ] 验证报告生成

**依赖**: TASK-017, TASK-018, TASK-019

**Labels**: `task`, `phase-2`, `validation`

---

## 📈 燃尽图数据

```
Week 1: ████████░░░░░░░░░░░ 8/20 tasks (40%) ✅ Sprint 1完成
Week 2: ████████░░░░░░░░░░░ 8/20 tasks (40%) - Sprint 2开始
Week 3: ████████████░░░░░░░ 12/20 tasks (60%)
Week 4: ██████████████░░░░░ 16/20 tasks (80%)
Week 5: ██████████████████░ 19/20 tasks (95%)
Week 6: ████████████████████ 20/20 tasks (100%)
```

**里程碑进度**:
- [x] M2-1: 完成搜索-优化基础框架 (Sprint 1) ✅
- [ ] M2-2: 完成解平面可视化 (Sprint 2-3)
- [ ] M2-3: 完成转移类型分类 (Sprint 3)
- [ ] M2-4: 验证结果精度 (Sprint 3)

---

## 🔗 关键链接

- **实施方案**: [implementation-plan.md](./implementation-plan.md)
- **Issues创建清单**: [issues-checklist.md](./issues-checklist.md)
- **Phase 1文档**: [../phase1-dro-ro-family-generation](../phase1-dro-ro-family-generation)
- **GitHub Issues**: (待创建)
- **论文数据**: [../../../../paper/Cui 等 - 2025 - Two-impulse transfers from lunar distant retrograde orbits to resonant orbits.md](../../../../paper/Cui 等 - 2025 - Two-impulse transfers from lunar distant retrograde orbits to resonant orbits.md)

---

## 📝 备注

- Sprint节奏: 每周五Sprint回顾
- 每日站会: 9:00 AM (可选)
- 遇到阻塞请创建Blocker Issue并标记@负责人
