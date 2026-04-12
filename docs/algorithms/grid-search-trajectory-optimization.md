# DRO-RO 网格搜索与轨迹优化结合算法设计

## 1. 问题背景

### 1.1 任务目标

从远距离逆行轨道（DRO）到共振轨道（RO）的双脉冲转移轨道设计，核心问题：
- DRO 和 RO 均为**稳定周期轨道**，无法利用不稳定流形结构
- 需要通过**网格搜索**找到初始可行解，再通过**NLP优化**求最优解

### 1.2 两步法流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        两步法转移轨道设计                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   第一阶段：网格搜索 (Search)          第二阶段：NLP优化 (Optimization)     │
│         ↓                                    ↓                          │
│   遍历 α-β 网格                      优化变量 y = {α, T, t_ins}          │
│         ↓                                    ↓                          │
│   前向积分轨迹                      SQP求解器最小化 Δv₁ + Δv₂            │
│         ↓                                    ↓                          │
│   筛选可行候选解                    输出最优转移轨道                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 数学模型

### 2.1 CR3BP 系统参数

| 参数 | 符号 | 值 | 单位 |
|------|------|-----|------|
| 地月质量比 | μ | 1.21506683×10⁻² | 无量纲 |
| 距离单位 | DU | 384405 | km |
| 时间单位 | TU | 4.34811305 | days |
| 速度单位 | VU | 1023.23281 | m/s |

### 2.2 搜索变量

| 变量 | 符号 | 范围 | 网格点数 |
|------|------|------|----------|
| 出发点 | — | DRO轨道等时间采样 | 200 |
| 切向速度比 | α | [0.5, 2.5] | 100 |

### 2.3 速度扰动模型

在出发点施加脉冲，将速度分解为径向和切向分量，仅缩放切向分量：

```
v_dep_new = v_radial · radial + α · v_tangential · tangential
```

其中 `tangential` 是轨道切向方向（xy 平面内垂直于位置矢量），`radial` 是径向方向。

### 2.4 优化问题定义

**决策变量**：
```
y = {α, T, t_ins}
```

**目标函数**：
```
J(y) = Δv₁ + Δv₂
```

**约束条件**：
1. 位置连续性：x_f 与 x_ins 重合
2. 速度平行：v_f 与 v_ins 方向一致
3. 碰撞约束：轨迹不经过地球/月球

---

## 3. 算法流程

### 3.1 网格搜索算法

```
ALGORITHM: Grid_Search

INPUT:
  dro_orbit        # 出发点DRO轨道
  ro_orbit         # 目标RO轨道
  config           # 搜索配置

OUTPUT:
  results[]        # 可行候选解列表

PROCEDURE:

1. # 采样出发点
   departure_states, departure_times ← Sample_Departure_Points(dro_orbit, N_DEPARTURE=200)

2. # 遍历所有出发点
   FOR EACH (state, t_dep) IN (departure_states, departure_times) DO:

      # 遍历α网格
      FOR EACH α IN α_grid DO:

            # Step 1: 计算扰动速度
            v_dep ← Orbit_Velocity(dro_orbit, t_dep)
            v_new ← Compute_Perturbed_Velocity(state, α)

            # Step 2: 前向积分（使用 DOP853 高阶 Runge-Kutta 积分器）
            X_f, T_f ← Forward_Integrate([state.position, v_new], T_max=100.0/TU)

            # Step 3: 计算到目标轨道的最小距离
            min_dist ← Compute_Min_Distance(X_f, ro_orbit)

            # Step 4: 碰撞检测
            collision ← Check_Collision(X_f, mu)

            # Step 5: 筛选条件
            IF collision == FALSE AND min_dist < threshold THEN:
                record_result(state, α, min_dist, X_f)

            END
      END

3. RETURN all_recorded_results
```

### 3.2 前向积分

```python
def forward_integrate(initial_state, transfer_time, dt=1.0/(24.0*TU)):
    """
    前向积分转移轨迹。实际实现使用 scipy DOP853（8阶 Runge-Kutta）积分器。

    Parameters:
    -----------
    initial_state : np.ndarray [6]
        初始状态 [x, y, z, vx, vy, vz]
    transfer_time : float
        积分时间 (TU)
    dt : float
        最大积分步长（默认约 0.0095 TU ≈ 1 小时）

    Returns:
    --------
    states : np.ndarray [n_steps, 6]
        轨迹状态序列
    times : np.ndarray [n_steps]
        对应时间序列
    """
    # 实际使用 e2m2e 的 TransferSearch._forward_integrate
    # 积分器配置: DOP853, rtol=1e-12, atol=1e-12
    ...
```

### 3.3 最小距离计算

```python
def compute_min_distance(trajectory_states, arrival_orbit):
    """
    计算转移轨迹到目标轨道的最小距离。

    使用向量化操作避免嵌套循环。

    Parameters:
    -----------
    trajectory_states : np.ndarray [n_steps, 6]
        转移轨迹状态
    arrival_orbit : Orbit
        目标轨道

    Returns:
    --------
    min_distance : float
        最小距离
    min_idx : int
        最小距离对应的轨迹索引
    orbit_idx : int
        最小距离对应的轨道点索引
    """
    # 提取位置: shape (n_steps, 3)
    traj_pos = trajectory_states[:, :3]

    # 轨道位置: shape (n_orbit, 3)
    orbit_pos = arrival_orbit.states[:, :3]

    # 计算距离矩阵: shape (n_steps, n_orbit)
    # 使用广播避免显式循环
    diff = traj_pos[:, np.newaxis, :] - orbit_pos[np.newaxis, :, :]
    distances = np.sqrt(np.sum(diff**2, axis=2))

    # 找到最小值
    flat_idx = np.argmin(distances)
    n_orbit = len(orbit_pos)
    min_idx = flat_idx // n_orbit
    orbit_idx = flat_idx % n_orbit

    return distances.flatten()[flat_idx], min_idx, orbit_idx
```

### 3.4 碰撞检测

```python
def check_collision(trajectory_states, mu, r_earth=200.0/DU, r_moon=100.0/DU):
    """
    检测轨迹是否与地球或月球碰撞。

    Parameters:
    -----------
    trajectory_states : np.ndarray [n_steps, 6]
        转移轨迹
    mu : float
        CR3BP质量比
    r_earth : float
        地球碰撞半径 (无量纲距离)
    r_moon : float
        月球碰撞半径

    Returns:
    --------
    collision : bool
        是否碰撞
    body : str or None
        碰撞天体 'earth' 或 'moon'
    idx : int
        碰撞点索引
    """
    positions = trajectory_states[:, :3]

    # 地球中心位置 (-mu, 0, 0)
    earth_center = np.array([-mu, 0.0, 0.0])
    # 月球中心位置 (1-mu, 0, 0)
    moon_center = np.array([1.0 - mu, 0.0, 0.0])

    # 向量化距离计算
    dist_earth = np.linalg.norm(positions - earth_center, axis=1)
    dist_moon = np.linalg.norm(positions - moon_center, axis=1)

    # 检测碰撞
    earth_hit = np.where(dist_earth < r_earth)[0]
    moon_hit = np.where(dist_moon < r_moon)[0]

    if len(earth_hit) > 0:
        return True, 'earth', earth_hit[0]
    if len(moon_hit) > 0:
        return True, 'moon', moon_hit[0]

    return False, None, -1
```

### 3.5 局部最小值检测

```python
def detect_local_minimum(trajectory_states, arrival_orbit):
    """
    检测轨迹到目标轨道距离的局部最小值。

    局部最小值表示轨迹"最接近"目标轨道的点，
    即使没有相交，也可作为候选解。

    Returns:
    --------
    has_local_min : bool
    min_distance : float
    min_idx : int
    """
    # 计算每一步到目标轨道的最小距离
    distances = []
    for state in trajectory_states:
        pos = state[:3]
        d = compute_point_to_orbit_min_distance(pos, arrival_orbit)
        distances.append(d)

    distances = np.array(distances)

    # 寻找局部最小: d[i-1] > d[i] < d[i+1]
    local_mins = []
    for i in range(1, len(distances) - 1):
        if distances[i] < distances[i-1] and distances[i] < distances[i+1]:
            local_mins.append((i, distances[i]))

    if local_mins:
        best = min(local_mins, key=lambda x: x[1])
        return True, best[1], best[0]

    return False, np.inf, -1
```

---

## 4. 配置参数

### 4.1 搜索配置 (`TransferSearchConfig`)

```python
@dataclass
class TransferSearchConfig:
    """网格搜索配置"""

    # α搜索范围
    alpha_min: float = 0.5
    alpha_max: float = 2.5
    n_alpha: int = 100

    # 出发点采样
    n_departure: int = 200

    # 积分配置（使用 DOP853 高阶积分器）
    max_transfer_time: float = 100.0 / TU  # ≈ 23.0 TU
    dt: float = 1.0 / (24.0 * TU)  # 最大步长 ≈ 0.0095 TU

    # 积分精度
    rtol: float = 1e-12
    atol: float = 1e-12

    # 筛选阈值
    intersection_threshold: float = 0.001  # 相交判定距离
    min_distance_threshold: float = 100.0 / DU   # 候选解最小距离阈值，默认 100 km（无量纲 DU）

    # 碰撞半径（物理值 200 km / 100 km）
    earth_radius: float = 200.0 / DU  # ≈ 0.00052
    moon_radius: float = 100.0 / DU   # ≈ 0.00026
```

### 4.2 调试参数（可人工修改）

| 参数 | 默认值 | 说明 | 建议修改范围 |
|------|--------|------|--------------|
| `n_departure` | 200 | 出发点数量 | 50-500 |
| `n_alpha` | 100 | α方向网格点 | 51-501 |
| `max_transfer_time` | 100.0/TU (≈23.0) | 最大积分时间(TU) | 10.0-30.0 |
| `intersection_threshold` | 0.001 | 相交判定 | 0.0001-0.01 |
| `min_distance_threshold` | `100/DU`（≈2.6×10⁻⁴ DU，物理 100 km） | 候选解阈值 | 按任务放宽/收紧 |

---

## 5. 常见问题与排查

### 5.1 网格搜索无解的可能原因

| 问题 | 症状 | 排查方法 | 解决方案 |
|------|------|----------|----------|
| 动力学模型错误 | 轨迹发散 | 检查μ值 | 确认μ=1.21506683e-2 |
| 积分步长过大 | 精度不足 | 减小dt | dt=0.0001 |
| 搜索范围不当 | 无候选解 | 可视化轨迹 | 扩大α范围 |
| 阈值过严 | 过滤掉所有解 | 检查min_dist分布 | 放宽threshold |
| 坐标系错误 | 位置完全不对 | 检查orbit数据 | 确认CR3BP坐标系 |
| 碰撞检测过严 | 大量collision | 检查r_earth/r_moon | 调整碰撞半径 |

### 5.2 调试步骤

```python
# Step 1: 验证轨道数据加载
dro_orbit = load_orbit_from_json(DRO_FILE)
print(f"DRO周期: {dro_orbit.period}")
print(f"DRO点数: {len(dro_orbit.states)}")
print(f"DRO状态范围: x=[{dro.states[:,0].min():.3f}, {dro.states[:,0].max():.3f}]")

# Step 2: 验证出发点采样
departure_states = sample_departure_points(dro_orbit, n_departure=10)
print(f"出发点x坐标: {departure_states[:,0]}")

# Step 3: 验证速度计算
state = departure_states[0]
v_new = compute_departure_velocity(state, alpha=1.0, beta=0.0)
print(f"原始速度: {state[3:]}")
print(f"扰动速度: {v_new}")

# Step 4: 验证前向积分（短时间）
X_test, T_test = forward_integrate([state[:3], v_new], transfer_time=1.0, dt=0.001)
print(f"积分点数: {len(X_test)}")
print(f"终点位置: {X_test[-1,:3]}")

# Step 5: 验证最小距离计算
min_dist, idx, orbit_idx = compute_min_distance(X_test, ro_orbit)
print(f"最小距离: {min_dist:.6f}")

# Step 6: 验证碰撞检测
collision, body, hit_idx = check_collision(X_test, MU)
print(f"碰撞: {collision}, {body}")
```

### 5.3 快速测试脚本

```python
"""
快速调试脚本 - 用于验证各模块功能
"""
import numpy as np
from pathlib import Path

def quick_debug_test():
    """运行快速调试测试"""

    # 1. 加载轨道数据
    print("=" * 60)
    print("1. 加载轨道数据")
    print("=" * 60)

    DRO_FILE = Path("output/dro/dro_31_3857029810.json")
    RO_FILE = Path("output/ro/ro_31_3857030320.json")

    dro_orbit = load_orbit_from_json(str(DRO_FILE))
    ro_orbit = load_orbit_from_json(str(RO_FILE))

    print(f"DRO周期: {dro_orbit.period:.4f} TU")
    print(f"RO周期: {ro_orbit.period:.4f} TU")

    # 2. 采样出发点
    print("\n" + "=" * 60)
    print("2. 采样出发点")
    print("=" * 60)

    n_test = 5
    times = np.linspace(0, dro_orbit.period, n_test, endpoint=False)
    departure_states = np.array([dro_orbit.interpolate_at_time(t) for t in times])

    for i, (t, state) in enumerate(zip(times, departure_states)):
        print(f"  [{i}] t={t:.4f}, pos=({state[0]:.4f}, {state[1]:.4f}, {state[2]:.4f})")

    # 3. 测试速度扰动
    print("\n" + "=" * 60)
    print("3. 测试速度扰动")
    print("=" * 60)

    state = departure_states[0]
    for alpha in [0.5, 1.0, 1.5, 2.0]:
        v_new = compute_departure_velocity(state, alpha)
        print(f"  α={alpha:.1f}: |v|={np.linalg.norm(v_new):.6f}")

    # 4. 测试前向积分
    print("\n" + "=" * 60)
    print("4. 测试前向积分 (T=1.0 TU)")
    print("=" * 60)

    v_new = compute_departure_velocity(state, alpha=1.0)
    X, T = forward_integrate([state[:3], v_new], transfer_time=1.0, dt=DT)

    print(f"  积分步数: {len(X)}")
    print(f"  起点: ({X[0,0]:.4f}, {X[0,1]:.4f}, {X[0,2]:.4f})")
    print(f"  终点: ({X[-1,0]:.4f}, {X[-1,1]:.4f}, {X[-1,2]:.4f})")

    # 5. 测试最小距离
    print("\n" + "=" * 60)
    print("5. 测试最小距离计算")
    print("=" * 60)

    min_dist, idx, orbit_idx = compute_min_distance(X, ro_orbit)
    print(f"  最小距离: {min_dist:.6f}")
    print(f"  轨迹索引: {idx}, 轨道索引: {orbit_idx}")

    # 6. 测试碰撞检测
    print("\n" + "=" * 60)
    print("6. 测试碰撞检测")
    print("=" * 60)

    collision, body, hit_idx = check_collision(X, MU)
    print(f"  碰撞: {collision}, 天体: {body}")

    print("\n" + "=" * 60)
    print("调试测试完成")
    print("=" * 60)
```

---

## 6. 代码实现

### 6.1 完整网格搜索实现

```python
"""
DRO-RO 网格搜索实现 (可直接修改使用)

使用方法:
    1. 修改下方的配置参数
    2. 运行: python grid_search.py
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional

# =============================================================================
# 配置参数 (可人工修改)
# =============================================================================

# 轨道数据文件
DRO_FILE = "output/dro/dro_31_3857029810.json"
RO_FILE = "output/ro/ro_31_3857030320.json"

# 搜索参数
N_DEPARTURE = 200    # 出发点数量 (可改为50-500)
N_ALPHA = 100        # α网格点数 (可改为51-501)
MAX_TRANSFER_TIME = 100.0 / 384405.0 * 86400  # ≈ 22.998 TU

# α 范围
ALPHA_MIN, ALPHA_MAX = 0.5, 2.5

# 阈值参数
INTERSECTION_THRESHOLD = 0.001   # 相交判定距离
MIN_DISTANCE_THRESHOLD = 100.0 / 384405.0   # 候选解阈值，默认 100 km（无量纲 DU）；与 e2m2e 一致

# 碰撞半径 (无量纲, 物理值 200 km / 100 km)
EARTH_RADIUS = 200.0 / 384405.0
MOON_RADIUS = 100.0 / 384405.0

# 积分步长 (最大步长，实际使用 DOP853 自适应步长)
DT = 1.0 / (24.0 * 4.34811305)  # ≈ 0.0095 TU

# =============================================================================
# 数据类
# =============================================================================

@dataclass
class TransferSearchConfig:
    """搜索配置"""
    alpha_min: float = ALPHA_MIN
    alpha_max: float = ALPHA_MAX
    n_alpha: int = N_ALPHA
    n_departure: int = N_DEPARTURE
    max_transfer_time: float = MAX_TRANSFER_TIME
    intersection_threshold: float = INTERSECTION_THRESHOLD
    min_distance_threshold: float = MIN_DISTANCE_THRESHOLD


@dataclass
class SearchResult:
    """搜索结果"""
    departure_idx: int
    alpha: float
    departure_state: np.ndarray
    transfer_trajectory: np.ndarray
    transfer_times: np.ndarray
    min_distance: float
    intersection_found: bool
    collision_found: bool


# =============================================================================
# 核心函数
# =============================================================================

def load_orbit_data(filepath: str):
    """加载轨道数据 (需要根据实际数据格式修改)"""
    import json
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data


def sample_departure_points(orbit_states, orbit_period, n_points: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    从轨道采样出发点。

    Returns:
        departure_states: shape (n_points, 6)
        departure_times: shape (n_points,)
    """
    times = np.linspace(0, orbit_period, n_points, endpoint=False)
    # 这里需要根据orbit的数据结构实现插值
    # 假设orbit_states已经是等时间采样的
    step = len(orbit_states) // n_points
    departure_states = orbit_states[::step][:n_points]
    return departure_states, times


def compute_departure_velocity(orbit_state: np.ndarray, alpha: float) -> np.ndarray:
    """
    计算出发点扰动速度。将速度分解为径向/切向分量，仅缩放切向分量。

    v_new = v_radial * radial + α * v_tangential * tangential

    Parameters:
        orbit_state: [x, y, z, vx, vy, vz]
        alpha: 切向速度比例

    Returns:
        扰动后的速度向量 [vx, vy, vz]
    """
    pos = orbit_state[:3]
    vel = orbit_state[3:]

    r_xy = np.sqrt(pos[0]**2 + pos[1]**2)
    if r_xy < 1e-10:
        return vel.copy()

    tangential = np.array([-pos[1], pos[0], 0.0]) / r_xy
    radial = pos / np.linalg.norm(pos)

    # 分解速度
    v_rad = np.dot(vel, radial)
    v_tan = np.dot(vel, tangential)

    # 构建新速度（保留径向分量，缩放切向分量）
    return v_rad * radial + alpha * v_tan * tangential


def forward_integrate(initial_state: np.ndarray, transfer_time: float,
                      mu: float, dt: float = DT) -> Tuple[np.ndarray, np.ndarray]:
    """
    前向积分轨迹。实际使用 scipy DOP853（8阶 Runge-Kutta）积分器。

    Parameters:
        initial_state: [x, y, z, vx, vy, vz]
        transfer_time: 积分时间 (TU)
        mu: 质量比
        dt: 最大步长

    Returns:
        states: shape (n_steps, 6)
        times: shape (n_steps,)
    """
    # 实际实现使用 e2m2e 的 CR3BP_Dynamics.propagate()
    # 积分器: DOP853, rtol=1e-12, atol=1e-12, max_step=dt
    # 下方为 CR3BP 方程参考（非实际积分代码）
    ...


def compute_min_distance(trajectory_states: np.ndarray, orbit_states: np.ndarray) -> Tuple[float, int]:
    """
    计算轨迹到轨道的最小距离 (向量化实现)。
    """
    traj_pos = trajectory_states[:, :3]
    orbit_pos = orbit_states[:, :3]

    # 广播计算距离矩阵
    diff = traj_pos[:, np.newaxis, :] - orbit_pos[np.newaxis, :, :]
    distances = np.sqrt(np.sum(diff**2, axis=2))

    flat_idx = np.argmin(distances)
    min_distance = distances.flatten()[flat_idx]

    return min_distance, flat_idx


def check_collision(trajectory_states: np.ndarray, mu: float,
                    earth_radius: float = EARTH_RADIUS,
                    moon_radius: float = MOON_RADIUS) -> Tuple[bool, Optional[str]]:
    """
    检测碰撞。
    """
    positions = trajectory_states[:, :3]

    earth_center = np.array([-mu, 0.0, 0.0])
    moon_center = np.array([1.0 - mu, 0.0, 0.0])

    dist_earth = np.linalg.norm(positions - earth_center, axis=1)
    dist_moon = np.linalg.norm(positions - moon_center, axis=1)

    if np.any(dist_earth < earth_radius):
        return True, 'earth'
    if np.any(dist_moon < moon_radius):
        return True, 'moon'

    return False, None


# =============================================================================
# 主搜索函数
# =============================================================================

def grid_search(departure_orbit_states, departure_period,
                arrival_orbit_states, mu: float,
                config: TransferSearchConfig,
                verbose: bool = True) -> List[SearchResult]:
    """
    网格搜索主函数。
    """

    # 生成搜索网格
    alpha_grid = np.linspace(config.alpha_min, config.alpha_max, config.n_alpha)

    # 采样出发点
    departure_states, departure_times = sample_departure_points(
        departure_orbit_states, departure_period, config.n_departure
    )

    if verbose:
        print(f"出发点数量: {len(departure_states)}")
        print(f"α网格: {len(alpha_grid)} 点, [{alpha_grid[0]:.2f}, {alpha_grid[-1]:.2f}]")
        print(f"总候选解数量: {len(departure_states) * len(alpha_grid)}")
        print("-" * 60)

    results = []
    total_combinations = len(departure_states) * len(alpha_grid)
    count = 0

    for dep_idx, (dep_state, dep_time) in enumerate(zip(departure_states, departure_times)):
        for alpha in alpha_grid:
                count += 1

                # 计算扰动速度
                v_new = compute_departure_velocity(dep_state, alpha)

                # 前向积分
                initial_state = np.concatenate([dep_state[:3], v_new])
                try:
                    traj_states, traj_times = forward_integrate(
                        initial_state, config.max_transfer_time, mu
                    )
                except:
                    continue

                # 计算最小距离
                min_dist, _ = compute_min_distance(traj_states, arrival_orbit_states)

                # 碰撞检测
                collision, body = check_collision(traj_states, mu)

                # 筛选条件
                is_intersection = min_dist < config.intersection_threshold
                is_feasible_distance = min_dist < config.min_distance_threshold

                if not collision and (is_intersection or is_feasible_distance):
                    result = SearchResult(
                        departure_idx=dep_idx,
                        alpha=alpha,
                        departure_state=dep_state,
                        transfer_trajectory=traj_states,
                        transfer_times=traj_times,
                        min_distance=min_dist,
                        intersection_found=is_intersection,
                        collision_found=False
                    )
                    results.append(result)

                    if verbose and len(results) <= 5:
                        print(f"  可行解 #{len(results)}: α={alpha:.4f}, "
                              f"min_dist={min_dist:.6f}, dep_idx={dep_idx}")

                if verbose and count % 10000 == 0:
                    print(f"  进度: {count}/{total_combinations} ({100*count/total_combinations:.1f}%)")

    if verbose:
        print("-" * 60)
        print(f"搜索完成: {len(results)} 个可行解 / {total_combinations} 个候选")

    return results


# =============================================================================
# 主程序
# =============================================================================

def main():
    """主程序入口"""

    print("=" * 60)
    print("DRO-RO 网格搜索")
    print("=" * 60)

    # 加载数据 (根据实际数据格式修改)
    print("\n加载轨道数据...")
    dro_data = load_orbit_data(DRO_FILE)
    ro_data = load_orbit_data(RO_FILE)

    dro_orbit_states = np.array(dro_data['states'])
    dro_period = dro_data['period']
    ro_orbit_states = np.array(ro_data['states'])
    ro_period = ro_data['period']

    print(f"DRO: {len(dro_orbit_states)} 状态点, 周期={dro_period:.4f} TU")
    print(f"RO: {len(ro_orbit_states)} 状态点, 周期={ro_period:.4f} TU")

    # 配置
    config = TransferSearchConfig()

    # 执行搜索
    print("\n开始网格搜索...")
    results = grid_search(
        dro_orbit_states, dro_period,
        ro_orbit_states, ro_orbit_states,
        mu=1.21506683e-2,
        config=config,
        verbose=True
    )

    # 保存结果
    if results:
        print(f"\n找到 {len(results)} 个可行解")
        # 可视化或保存...
    else:
        print("\n警告: 未找到可行解！")
        print("建议检查:")
        print("  1. 轨道数据是否正确加载")
        print("  2. 搜索参数范围是否合适")
        print("  3. 阈值设置是否过严")

    return results


if __name__ == "__main__":
    results = main()
</script>
```

---

## 7. 排查清单

如果网格搜索运行一整晚没有找到任何解，按以下顺序检查：

### Step 1: 验证数据加载
- [ ] 轨道JSON文件存在且可读
- [ ] DRO和RO数据点数合理（通常>100）
- [ ] 轨道状态在正确范围内（x约0.8-1.2 for DRO, 0.5-1.5 for RO）

### Step 2: 验证动力学模型
- [ ] μ值正确（1.21506683e-2）
- [ ] 积分不发散（轨迹在150 TU内保持有限）
- [ ] 积分步长足够小（dt ≤ 0.001）

### Step 3: 验证搜索逻辑
- [ ] 出发点确实在DRO上（可视化检查）
- [ ] 速度扰动方向正确
- [ ] 最小距离计算结果合理

### Step 4: 调整参数
- [ ] 如果min_distance普遍很大 → 扩大α范围
- [ ] 如果大量collision → 检查碰撞半径或动力学模型
- [ ] 如果轨迹发散 → 减小dt或减少max_transfer_time

---

## 8. 参考信息

### 论文引用
- Cui et al. (2025). "Two-Impulse Transfers from Lunar Distant Retrograde Orbits to Resonant Orbits." *Journal of Guidance, Control, and Dynamics*.

### 关键公式
- CR3BP动力学方程: 论文Eq. (1)-(6)
- 速度扰动模型: 论文Eq. (12)
- NLP约束条件: 论文Eq. (13)-(16)

### 文件位置
- 网格搜索脚本: `scripts/transfer/grid_search_dro_to_ro.py`
- 优化脚本: `scripts/transfer/optimize_dro_to_ro.py`
- 算法文档: `scripts/transfer/search-optimization-method.md`
- 实现计划: `plan/grid-search-implementation-v2.md`
