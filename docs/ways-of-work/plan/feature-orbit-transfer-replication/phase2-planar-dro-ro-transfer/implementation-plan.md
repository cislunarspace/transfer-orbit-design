---
goal: "实现平面DRO到RO的两脉冲转移轨道设计（Phase 2）"
version: "1.0"
date_created: 2026-03-21
owner: transfer-orbit-design
status: 'Planning'
tags: ['phase-2', 'transfer-design', 'search-optimization', 'copt', 'nlp']
---

# Phase 2: 平面DRO到RO转移轨道设计 - 实施计划

## 1. 概述

本计划详细描述Phase 2的实施细节，实现Cui et al. (2025)论文中的"搜索-优化"两步法，设计CR3BP中从DRO到RO的两脉冲转移轨道。

### 1.1 核心方法论

```
┌─────────────────────────────────────────────────────────────────┐
│                      两步法转移设计                               │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: 搜索阶段                                               │
│  ├── 网格化搜索变量：出发点位置、α(切向速度比)、β(法向速度比)         │
│  ├── 前向积分获取转移轨迹                                         │
│  └── 筛选：与终端轨道相交或距离局部最小 → 初始可行解               │
│                              ↓                                   │
│  Phase 2: 优化阶段                                               │
│  ├── NLP问题：优化变量 y = {α, T, t_ins}                         │
│  ├── 目标函数：J(y) = Δv₁ + Δv₂                                 │
│  ├── 约束：位置连续、速度平行（角度约束）、不撞击天体               │
│  └── 使用COPT求解器求解                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 优化求解器 | COPT | 用户指定，国产高性能优化器 |
| 积分器 | DOP853 | 论文指定，高精度变步长Runge-Kutta 7-8阶 |
| 微分修正 | e2m2e原有模块 | 已完成 |
| 动力学模型 | CR3BP | 论文指定 |

## 2. 任务分解

### 2.1 核心任务列表

| 任务ID | 描述 | 优先级 | 依赖 | 状态 |
|--------|------|--------|------|------|
| TASK-009 | 实现网格化搜索算法 | P0 | - | Pending |
| TASK-010 | 实现前向积分模块 | P0 | TASK-009 | Pending |
| TASK-011 | 实现轨迹筛选模块 | P0 | TASK-010 | Pending |
| TASK-012 | 实现NLP问题构建 | P0 | TASK-011 | Pending |
| TASK-013 | 集成COPT求解器 | P0 | TASK-012 | Pending |
| TASK-014 | 计算4种平面转移路径 | P1 | TASK-013 | Pending |
| TASK-015 | 分类三种典型转移类型 | P1 | TASK-014 | Pending |
| TASK-016 | 绘制解平面（转移时间 vs 总脉冲） | P1 | TASK-014 | Pending |
| TASK-017 | 分析出发点和插入点分布 | P2 | TASK-014 | Pending |

## 3. 详细技术分解

### TASK-009: 网格化搜索算法

**目标**: 实现论文Section III.A的搜索阶段算法

**搜索变量**:
| 变量 | 最小值 | 最大值 | 离散点数 | 含义 |
|------|--------|--------|----------|------|
| 出发点 | - | - | 200 | 等时间间隔离散初始轨道 |
| α | 0.5 | 2.5 | 1001 | 切向速度比 |
| β | -0.5 | 0.5 | 101 | 法向速度比（平面转移固定为0） |

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-009-01 | **定义搜索变量结构**: 创建`TransferSearchVariables` dataclass | P0 | - |
| SUB-009-02 | **实现出发点采样**: 从DRO族中等时间间隔采样200个点 | P0 | - |
| SUB-009-03 | **实现速度比例计算**: 根据α,β计算出发速度 | P0 | - |
| SUB-009-04 | **配置搜索空间网格**: 使用`numpy.meshgrid`生成完整网格 | P0 | SUB-009-02, SUB-009-03 |
| SUB-009-05 | **实现并行搜索支持**: 使用`joblib`并行化网格搜索 | P1 | SUB-009-04 |

**实现方案**:

```python
# 伪代码：搜索变量定义
@dataclass
class TransferSearchVariables:
    """转移搜索变量"""
    departure_orbit: Orbit              # 出发点所在轨道
    departure_time_index: int            # 出发点时间索引 (0-199)
    alpha: float                        # 切向速度比 (0.5-2.5)
    beta: float                         # 法向速度比 (-0.5-0.5), 平面为0
    
    @property
    def departure_state(self) -> np.ndarray:
        """获取出发点状态"""
        t_dep = (self.departure_time_index / 200) * self.departure_orbit.period
        return self.departure_orbit.interpolate_at_time(t_dep)
    
    @property
    def departure_velocity_ratio(self) -> Tuple[float, float]:
        """获取速度比例(α, β)"""
        return (self.alpha, self.beta)
```

### TASK-010: 前向积分模块

**目标**: 实现转移弧的前向积分

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-010-01 | **实现初始速度计算**: 根据α,β从出发点速度计算注入速度 | P0 | - |
| SUB-010-02 | **实现CR3BP积分**: 使用DOP853积分转移弧 | P0 | SUB-010-01 |
| SUB-010-03 | **实现积分事件检测**: 检测与RO的相交/距离最小事件 | P0 | SUB-010-02 |
| SUB-010-04 | **实现积分结果缓存**: 避免重复计算 | P1 | SUB-010-02 |

**速度计算公式**（论文Eq.11-12基础）:

```python
def compute_departure_velocity(state_dep: np.ndarray, alpha: float, beta: float = 0.0) -> np.ndarray:
    """
    计算出发速度
    
    参数:
        state_dep: 出发点状态 [x, y, z, vx, vy, vz]
        alpha: 切向速度比
        beta: 法向速度比（平面转移为0）
    
    返回:
        注入速度 [vx, vy, vz]
    """
    pos = state_dep[:3]
    vel = state_dep[3:]
    
    # 轨道面法向（CR3BP中为z轴）
    normal = np.array([0, 0, 1.0])
    
    # 切向和法向单位向量
    tangential = vel / np.linalg.norm(vel)
    normal_dir = np.cross(tangential, normal)
    normal_dir = normal_dir / np.linalg.norm(normal_dir)
    
    # 速度大小
    v_mag = np.linalg.norm(vel)
    
    # 注入速度 = alpha * 切向分量 + beta * 法向分量
    v_injection = alpha * v_mag * tangential + beta * v_mag * normal_dir
    
    return v_injection
```

### TASK-011: 轨迹筛选模块

**目标**: 从搜索结果中筛选出可行初始解

**筛选条件**（论文Section III.A）:
1. 转移轨迹与最终轨道相交
2. 转移轨迹与最终轨道距离局部最小

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-011-01 | **实现相交检测**: 检测转移弧与RO的相交点 | P0 | - |
| SUB-011-02 | **实现距离计算**: 计算转移弧与RO的最小距离 | P0 | - |
| SUB-011-03 | **实现局部最小检测**: 使用梯度检测识别距离局部最小点 | P0 | SUB-011-02 |
| SUB-011-04 | **实现筛选结果存储**: 存储可行解及其转移时间 | P0 | SUB-011-01, SUB-011-03 |

**筛选算法**:

```python
def filter_transfer_candidates(
    transfer_arc: np.ndarray,  # [n_steps, 6] 状态序列
    arrival_orbit: Orbit,
    min_distance_threshold: float = 0.01,
    intersection_threshold: float = 0.001
) -> List[Dict]:
    """筛选转移候选解"""
    candidates = []
    
    # 方法1: 检测相交
    for i, state in enumerate(transfer_arc):
        for j, orbit_state in enumerate(arrival_orbit.states):
            if np.linalg.norm(state[:3] - orbit_state[:3]) < intersection_threshold:
                candidates.append({
                    'type': 'intersection',
                    'transfer_time': transfer_arc[i, 0],  # 假设第一列为时间
                    'departure_idx': i,
                    'arrival_idx': j,
                    'state': state
                })
    
    # 方法2: 检测距离局部最小
    distances = []
    for state in transfer_arc:
        min_dist = min(np.linalg.norm(state[:3] - os[:3]) for os in arrival_orbit.states)
        distances.append(min_dist)
    
    # 找局部最小（梯度变号处）
    for k in range(1, len(distances)-1):
        if distances[k-1] > distances[k] < distances[k+1]:
            if distances[k] < min_distance_threshold:
                candidates.append({
                    'type': 'local_minimum',
                    'transfer_time': transfer_arc[k, 0],
                    'min_distance': distances[k],
                    'state': transfer_arc[k]
                })
    
    return candidates
```

### TASK-012: NLP问题构建

**目标**: 将转移优化问题构建为NLP问题

**优化变量**（论文Eq.9）:
```
y = {α, T, t_ins}
```

**目标函数**（论文Eq.10）:
```
J(y) = Δv₁ + Δv₂
```

**约束条件**:
1. 位置连续约束（论文Eq.13）
2. 速度平行约束/角度约束（论文Eq.14/17）
3. 不撞击约束（论文Eq.15-16）

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-012-01 | **定义NLP变量结构**: 创建`TransferNLPVariables` dataclass | P0 | - |
| SUB-012-02 | **实现目标函数**: J(y) = Δv₁ + Δv₂ | P0 | - |
| SUB-012-03 | **实现位置约束**: 转移终点=插入点位置 | P0 | - |
| SUB-012-04 | **实现角度约束**: 转移终点速度//插入点速度 | P0 | - |
| SUB-012-05 | **实现不撞击约束**: 距离地球和月球 > 阈值 | P0 | - |
| SUB-012-06 | **构建COPT兼容问题格式**: 将NLP转为COPT可解形式 | P0 | SUB-012-02~05 |

**NLP数学公式**:

```
minimize: J(y) = Δv₁ + Δv₂

subject to:
    g₁(y) = (x_f - x_ins)² + (y_f - y_ins)² + (z_f - z_ins)² = 0     [位置连续]
    g₂(y) = cos(θ) - (v_f · v_ins) / (||v_f|| ||v_ins||) ≤ 0          [角度松弛]
    g₃(y) = r_e² - (x+μ)² - y² - z² < 0                                  [不撞地球]
    g₄(y) = r_m² - (x+μ-1)² - y² - z² < 0                                [不撞月球]
    
where:
    Δv₁ = ||v_i - v_dep||
    Δv₂ = ||v_ins - v_f||
```

### TASK-013: COPT求解器集成

**目标**: 使用COPT求解NLP问题

**COPT为国产高性能优化器，支持**:
- 连续变量NLP
- SQP-like方法处理非线性约束
- 通过`coptpy`Python接口调用

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-013-01 | **验证COPT安装**: 确认coptpy可用 | P0 | - |
| SUB-013-02 | **创建COPT求解封装**: `COPTNLPSolver`类 | P0 | - |
| SUB-013-03 | **配置求解参数**: 容差、迭代限制等 | P0 | SUB-013-02 |
| SUB-013-04 | **实现回退求解器**: COPT不可用时使用scipy.optimize | P1 | SUB-013-02 |
| SUB-013-05 | **实现结果解析**: 提取最优解和代价 | P0 | SUB-013-02 |

**COPT集成方案**:

```python
class COPTNLPSolver:
    """基于COPT的NLP求解器封装"""
    
    def __init__(self, options: Optional[Dict] = None):
        self.options = options or {}
        self.model = None
        self.solution = None
        
    def setup(self, n_vars: int, objective, constraints, bounds):
        """设置NLP问题"""
        try:
            import coptpy
            self.env = coptpy.Envr()
            self.model = self.env.createModel("transfer_nlp")
            
            # 添加变量
            x = self.model.addVars(n_vars, lb=bounds[:, 0], ub=bounds[:, 1])
            
            # 设置目标函数
            self.model.setObjective(objective(x), coptpy.COPT.MINIMIZE)
            
            # 添加约束
            for constraint in constraints:
                self.model.addConstr(constraint(x) <= 0)
                
        except ImportError:
            raise RuntimeError("COPT not available, use fallback solver")
    
    def solve(self, x0: np.ndarray) -> Dict:
        """求解NLP问题"""
        self.model.setParam(coptpy.COPT.Param.MaxIter, self.options.get('max_iter', 1000))
        self.model.setParam(coptpy.COPT.Param.FeasTol, self.options.get('feas_tol', 1e-10))
        self.model.setParam(coptpy.COPT.Param.OptTol, self.options.get('opt_tol', 1e-10))
        
        self.model.solve()
        
        return {
            'status': self.model.status,
            'objective': self.model.objval,
            'solution': self.model.x,
            'iterations': self.model.itercount
        }
```

### TASK-014: 计算4种平面转移路径

**目标**: 计算论文Table 4中的4种转移情况

| 编号 | 转移路径 | 特点 |
|------|----------|------|
| 1 | 2:1 DRO → 3:2 RO | 短周期→长周期 |
| 2 | 3:1 DRO → 3:2 RO | 短周期→长周期 |
| 3 | 2:1 DRO → 3:1 RO | 短周期→中周期 |
| 4 | 3:1 DRO → 3:1 RO | 短周期→中周期 |

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-014-01 | **加载DRO族数据**: 读取2:1和3:1 DRO | P0 | - |
| SUB-014-02 | **加载RO族数据**: 读取3:2和3:1 RO | P0 | - |
| SUB-014-03 | **实现转移搜索**: 对4种组合执行完整搜索-优化流程 | P0 | SUB-014-01, SUB-014-02 |
| SUB-014-04 | **存储转移结果**: 按论文格式保存JSON | P0 | SUB-014-03 |
| SUB-014-05 | **验证结果**: 对比论文Table 4数值 | P1 | SUB-014-04 |

### TASK-015: 分类三种典型转移类型

**目标**: 识别并分类三种典型转移（论文Section IV.B）

| 类型 | 特征 | 位置 |
|------|------|------|
| 直接转移 | 转移时间短(<20天)，解平面最左侧 | Pareto前沿 |
| LGA转移 | 月球借力，底部解，Δv大幅降低 | 最小Δv区域 |
| 外部转移 | 远地点>3倍地月距离 | 分散分布 |

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-015-01 | **实现转移类型分类器**: 基于转移时间和轨道特征分类 | P0 | - |
| SUB-015-02 | **实现LGA检测**: 检测月球flyby几何 | P0 | - |
| SUB-015-03 | **实现外部转移检测**: 基于远地点高度检测 | P0 | - |
| SUB-015-04 | **生成分类报告**: 统计各类型数量和特征 | P1 | SUB-015-01~03 |

### TASK-016: 绘制解平面

**目标**: 复现论文Fig.6，展示解平面结构

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-016-01 | **实现解平面绘图**: T (转移时间) vs Δv (总脉冲) | P0 | - |
| SUB-016-02 | **实现Pareto前沿标记**: 标识最优解 | P0 | - |
| SUB-016-03 | **实现转移类型着色**: 不同颜色区分三种类型 | P0 | SUB-015-01 |
| SUB-016-04 | **保存高清图像**: 300dpi PNG和矢量PDF | P1 | SUB-016-01~03 |

### TASK-017: 分析出发点和插入点分布

**目标**: 复现论文Fig.11四分位图

**子任务分解**:

| 子任务 | 描述 | 优先级 | 依赖 |
|--------|------|--------|------|
| SUB-017-01 | **实现四分位计算**: 计算Q1, Q2, Q3 | P0 | - |
| SUB-017-02 | **实现四分位图绘制**: 箱线图形式 | P0 | - |
| SUB-017-03 | **实现距离分析**: 出发点/插入点距地距离 | P0 | - |
| SUB-017-04 | **对比论文结论**: 验证"解集中在远地点附近" | P2 | SUB-017-01~03 |

## 4. 文件结构

```
transfer-orbit-design/
├── scripts/
│   ├── phase2_transfer_search.py          # 搜索阶段主脚本
│   ├── phase2_transfer_optimize.py         # 优化阶段主脚本
│   └── utils/
│       ├── __init__.py
│       ├── transfer_search.py             # 搜索算法
│       ├── transfer_nlp.py                 # NLP问题构建
│       ├── copt_solver.py                 # COPT求解器封装
│       └── visualization.py                # 解平面可视化
├── output/
│   └── phase2/
│       ├── transfer_solutions/            # 转移解
│       └── figures/                       # 图像
└── docs/
    └── ways-of-work/plan/
        └── feature-orbit-transfer-replication/
            └── phase2-planar-dro-ro-transfer/
                └── implementation-plan.md  # 本文档
```

## 5. 测试计划

| 测试ID | 描述 | 验收标准 |
|--------|------|----------|
| TEST-007 | 验证搜索算法正确性 | 网格搜索返回有效候选解 |
| TEST-008 | 验证NLP问题构建 | 目标函数和约束正确计算 |
| TEST-009 | 验证COPT求解器 | 求解收敛且结果合理 |
| TEST-010 | 验证转移轨道位置连续性 | \|Δpos\| < 1e-6 |
| TEST-011 | 验证转移轨道速度连续性 | 速度角度差 < 1e-3 rad |
| TEST-012 | 验证不撞击约束 | 最小距离 > 阈值 |
| TEST-013 | 对比论文Table 4 | Δv偏差 < 10% |

## 6. 风险与缓解

| 风险ID | 描述 | 影响 | 缓解策略 |
|--------|------|------|----------|
| RISK-004 | COPT NLP接口不熟悉 | 中 | 预留研究时间，准备scipy回退 |
| RISK-005 | 网格搜索计算量大 | 高 | 并行化，稀疏采样 |
| RISK-006 | NLP求解不收敛 | 高 | 使用搜索结果作为初值，多起点 |
| RISK-007 | 解平面结构复杂 | 中 | 先实现直接转移，再扩展 |

## 7. 里程碑

| 里程碑 | 描述 | 验收标准 |
|--------|------|----------|
| M2-1 | 完成搜索-优化基础框架 | 4种转移路径可计算 |
| M2-2 | 完成解平面可视化 | Fig.6可复现 |
| M2-3 | 完成转移类型分类 | 3种类型正确识别 |
| M2-4 | 验证结果精度 | 对比论文Table 4偏差<10% |

## 8. 参考资料

- [Cui et al. (2025) Section III: Optimization Method for Two-Impulse Transfers](file:../paper/Cui%20等%20-%202025%20-%20Two-impulse%20transfers%20from%20lunar%20distant%20retrograde%20orbits%20to%20resonant%20orbits.md)
- [COPT Python API文档](file:///C:\Users\ouyangjiahong\Codes\MinerU\temp\copt-userguide_cn.pdf)
- [e2m2e transfer模块](../e2m2e/e2m2e/transfer/inter_orbit.py)
