"""
DRO-RO 网格搜索独立实现
=========================

可直接修改和运行的网格搜索代码实现。
建议配合 docs/grid-search-trajectory-optimization.md 文档使用。

使用方法:
    1. 修改下方 "可配置参数" 部分
    2. 确保轨道数据JSON文件存在
    3. 运行: python grid_search_impl.py

调试模式:
    python grid_search_impl.py --debug
"""

import argparse
import json
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import sys

# =============================================================================
# 可配置参数 (人工可修改)
# =============================================================================

# 轨道数据文件路径
DRO_FILE = "output/dro/dro_31_3857029810.json"
RO_FILE = "output/ro/ro_31_3857030320.json"

# 搜索参数
N_DEPARTURE = 200      # 出发点采样数量 (范围: 50-500)
N_ALPHA = 101          # α方向网格点数 (范围: 51-501)
N_BETA = 21            # β方向网格点数 (范围: 11-101)
MAX_TRANSFER_TIME = 15.0  # 最大转移时间 (TU)

# α, β 搜索范围
ALPHA_MIN = 0.5
ALPHA_MAX = 2.5
BETA_MIN = -0.5
BETA_MAX = 0.5

# 筛选阈值
INTERSECTION_THRESHOLD = 0.001   # 相交判定距离 (当距离小于此值认为相交)
MIN_DISTANCE_THRESHOLD = 0.05   # 候选解最小距离阈值

# 碰撞检测半径 (无量纲)
EARTH_RADIUS = 0.01
MOON_RADIUS = 0.01

# 积分配置
DT = 0.001   # 积分步长
INTEGRATOR = 'euler'  # 'euler' 或 'rk4'

# 物理常数
MU = 1.21506683e-2  # 地月质量比

# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class TransferSearchConfig:
    """网格搜索配置"""
    alpha_min: float = ALPHA_MIN
    alpha_max: float = ALPHA_MAX
    n_alpha: int = N_ALPHA
    beta_min: float = BETA_MIN
    beta_max: float = BETA_MAX
    n_beta: int = N_BETA
    n_departure: int = N_DEPARTURE
    max_transfer_time: float = MAX_TRANSFER_TIME
    intersection_threshold: float = INTERSECTION_THRESHOLD
    min_distance_threshold: float = MIN_DISTANCE_THRESHOLD
    dt: float = DT
    earth_radius: float = EARTH_RADIUS
    moon_radius: float = MOON_RADIUS

    def __post_init__(self):
        self.alpha_grid = np.linspace(self.alpha_min, self.alpha_max, self.n_alpha)
        self.beta_grid = np.linspace(self.beta_min, self.beta_max, self.n_beta)


@dataclass
class SearchResult:
    """单次搜索结果"""
    departure_idx: int
    departure_time: float
    alpha: float
    beta: float
    min_distance: float
    intersection_found: bool
    collision_found: bool
    collision_body: Optional[str] = None

    # 轨迹信息 (可选, 用于调试)
    trajectory: Optional[np.ndarray] = None

    @property
    def is_feasible(self) -> bool:
        return (self.intersection_found or
                self.min_distance < self.min_distance_threshold) and \
               not self.collision_found


@dataclass
class OrbitData:
    """轨道数据结构"""
    states: np.ndarray  # shape: (n, 6) - [x, y, z, vx, vy, vz]
    period: float       # 轨道周期 (TU)
    name: str = ""

    @classmethod
    def from_json(cls, filepath: str) -> 'OrbitData':
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(
            states=np.array(data['states']),
            period=data['period'],
            name=data.get('name', Path(filepath).stem)
        )


# =============================================================================
# 动力学模型
# =============================================================================

def cr3bp_dynamics(state: np.ndarray, mu: float = MU) -> np.ndarray:
    """
    CR3BP动力学方程。

    Parameters:
        state: [x, y, z, vx, vy, vz]
        mu: 质量比

    Returns:
        dstate/dt: [vx, vy, vz, ax, ay, az]
    """
    x, y, z, vx, vy, vz = state

    # 到地球和月球的位置
    rx = x + mu
    r_earth = np.sqrt(rx**2 + y**2 + z**2)
    r_moon = np.sqrt((x + mu - 1)**2 + y**2 + z**2)

    # 加速度
    ax = 2*vy + x - (1 - mu)*rx/r_earth**3 - mu*(x + mu - 1)/r_moon**3
    ay = -2*vx + y - (1 - mu)*y/r_earth**3 - mu*y/r_moon**3
    az = -(1 - mu)*z/r_earth**3 - mu*z/r_moon**3

    return np.array([vx, vy, vz, ax, ay, az])


def integrate_trajectory(initial_state: np.ndarray,
                       transfer_time: float,
                       mu: float = MU,
                       dt: float = DT,
                       method: str = 'euler') -> Tuple[np.ndarray, np.ndarray]:
    """
    前向积分转移轨迹。

    Parameters:
        initial_state: [x, y, z, vx, vy, vz]
        transfer_time: 积分时间 (TU)
        mu: 质量比
        dt: 积分步长
        method: 'euler' 或 'rk4'

    Returns:
        states: shape (n_steps, 6)
        times: shape (n_steps,)
    """
    n_steps = int(transfer_time / dt) + 1
    states = np.zeros((n_steps, 6))
    times = np.zeros(n_steps)

    states[0] = np.asarray(initial_state, dtype=np.float64)
    times[0] = 0.0

    for i in range(1, n_steps):
        if method == 'rk4':
            # RK4积分
            k1 = cr3bp_dynamics(states[i-1], mu)
            k2 = cr3bp_dynamics(states[i-1] + 0.5*dt*k1, mu)
            k3 = cr3bp_dynamics(states[i-1] + 0.5*dt*k2, mu)
            k4 = cr3bp_dynamics(states[i-1] + dt*k3, mu)
            states[i] = states[i-1] + (dt/6.0)*(k1 + 2*k2 + 2*k3 + k4)
        else:
            # 欧拉积分
            dstate = cr3bp_dynamics(states[i-1], mu)
            states[i] = states[i-1] + dstate * dt

        times[i] = times[i-1] + dt

    return states, times


# =============================================================================
# 速度计算
# =============================================================================

def compute_tangential_normal(pos: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    计算位置处的切向和法向单位向量。

    对于xy平面轨道:
        - tangential: 垂直于位置矢量 (逆时针方向)
        - normal: +z方向

    Returns:
        tangential: 切向单位向量
        normal: 法向单位向量
    """
    # 径向方向
    r = np.linalg.norm(pos[:2])
    if r < 1e-10:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])

    # 切向: 垂直于xy平面内的位置矢量
    tangential = np.array([-pos[1], pos[0], 0.0]) / r

    # 法向: +z方向
    normal = np.array([0.0, 0.0, 1.0])

    return tangential, normal


def compute_departure_velocity(orbit_state: np.ndarray,
                               alpha: float,
                               beta: float = 0.0) -> np.ndarray:
    """
    计算出发点扰动速度。

    速度 = 原始速度 + (α-1)*v_tang + β*v_normal

    Parameters:
        orbit_state: [x, y, z, vx, vy, vz]
        alpha: 切向速度比例
        beta: 法向速度比例

    Returns:
        扰动后速度 [vx, vy, vz]
    """
    pos = orbit_state[:3]
    vel = orbit_state[3:]

    tangential, normal = compute_tangential_normal(pos)

    # 分解速度
    v_tang = np.dot(vel, tangential)
    v_norm = np.dot(vel, normal)

    # 构建新速度
    new_vel = vel.copy()
    new_vel += (alpha - 1.0) * v_tang * tangential
    new_vel += beta * v_norm * normal

    return new_vel


# =============================================================================
# 轨道相关计算
# =============================================================================

def sample_departure_points(orbit: OrbitData, n_points: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    从轨道等时间间隔采样出发点。

    Parameters:
        orbit: 轨道数据
        n_points: 采样点数

    Returns:
        states: shape (n_points, 6)
        times: shape (n_points,)
    """
    times = np.linspace(0, orbit.period, n_points, endpoint=False)

    # 等间隔采样
    indices = np.linspace(0, len(orbit.states) - 1, n_points, dtype=int)
    departure_states = orbit.states[indices]

    return departure_states, times


def compute_min_distance_vectorized(trajectory_states: np.ndarray,
                                   orbit_states: np.ndarray) -> Tuple[float, int, int]:
    """
    向量化计算轨迹到轨道的最小距离。

    Parameters:
        trajectory_states: shape (n_traj, 6)
        orbit_states: shape (n_orbit, 6)

    Returns:
        min_distance: 最小距离
        traj_idx: 轨迹上最小距离点索引
        orbit_idx: 轨道上最小距离点索引
    """
    traj_pos = trajectory_states[:, :3]
    orbit_pos = orbit_states[:, :3]

    # 广播计算距离矩阵: shape (n_traj, n_orbit)
    diff = traj_pos[:, np.newaxis, :] - orbit_pos[np.newaxis, :, :]
    distances = np.sqrt(np.sum(diff**2, axis=2))

    # 找最小值
    flat_idx = np.argmin(distances)
    n_orbit = len(orbit_pos)
    traj_idx = flat_idx // n_orbit
    orbit_idx = flat_idx % n_orbit

    return distances[traj_idx, orbit_idx], traj_idx, orbit_idx


def compute_point_to_orbit_min_distance(point: np.ndarray, orbit_states: np.ndarray) -> float:
    """
    计算点到轨道的最小距离。
    """
    pos = point[:3]
    orbit_pos = orbit_states[:, :3]
    distances = np.linalg.norm(orbit_pos - pos, axis=1)
    return np.min(distances)


def check_collision(trajectory_states: np.ndarray,
                   mu: float = MU,
                   earth_radius: float = EARTH_RADIUS,
                   moon_radius: float = MOON_RADIUS) -> Tuple[bool, Optional[str], int]:
    """
    检测轨迹是否与地球或月球碰撞。

    Returns:
        collision: 是否碰撞
        body: 'earth' 或 'moon' 或 None
        idx: 碰撞点索引或-1
    """
    positions = trajectory_states[:, :3]

    earth_center = np.array([-mu, 0.0, 0.0])
    moon_center = np.array([1.0 - mu, 0.0, 0.0])

    dist_earth = np.linalg.norm(positions - earth_center, axis=1)
    dist_moon = np.linalg.norm(positions - moon_center, axis=1)

    earth_hits = np.where(dist_earth < earth_radius)[0]
    moon_hits = np.where(dist_moon < moon_radius)[0]

    if len(earth_hits) > 0:
        return True, 'earth', earth_hits[0]
    if len(moon_hits) > 0:
        return True, 'moon', moon_hits[0]

    return False, None, -1


# =============================================================================
# 局部最小值检测
# =============================================================================

def detect_local_minimum(trajectory_states: np.ndarray,
                         orbit_states: np.ndarray) -> Tuple[bool, float, int]:
    """
    检测轨迹到轨道距离的局部最小值。

    局部最小值表示轨迹"最接近"目标轨道的点，
    即使没有相交，也可作为候选解。

    Returns:
        has_local_min: 是否有局部最小值
        min_distance: 最小距离
        min_idx: 最小距离索引
    """
    # 计算每一步的距离
    n_traj = len(trajectory_states)
    distances = np.array([
        compute_point_to_orbit_min_distance(trajectory_states[i], orbit_states)
        for i in range(n_traj)
    ])

    # 找局部最小: d[i-1] > d[i] < d[i+1]
    local_mins = []
    for i in range(1, n_traj - 1):
        if distances[i] < distances[i-1] and distances[i] < distances[i+1]:
            local_mins.append((i, distances[i]))

    if local_mins:
        best = min(local_mins, key=lambda x: x[1])
        return True, best[1], best[0]

    return False, np.min(distances), np.argmin(distances)


# =============================================================================
# 网格搜索主函数
# =============================================================================

def grid_search(orbit_departure: OrbitData,
               orbit_arrival: OrbitData,
               config: TransferSearchConfig,
               verbose: bool = True,
               early_stop: Optional[int] = None) -> List[SearchResult]:
    """
    网格搜索主函数。

    Parameters:
        orbit_departure: 出发点轨道 (DRO)
        orbit_arrival: 目标轨道 (RO)
        config: 搜索配置
        verbose: 是否打印详细信息
        early_stop: 找到多少个可行解后停止 (None表示不限制)

    Returns:
        搜索结果列表
    """
    if verbose:
        print("=" * 70)
        print("DRO-RO 转移轨道网格搜索")
        print("=" * 70)
        print(f"\n搜索配置:")
        print(f"  出发点数量: {config.n_departure}")
        print(f"  α范围: [{config.alpha_min:.2f}, {config.alpha_max:.2f}], n={config.n_alpha}")
        print(f"  β范围: [{config.beta_min:.2f}, {config.beta_max:.2f}], n={config.n_beta}")
        print(f"  最大转移时间: {config.max_transfer_time:.1f} TU")
        print(f"  积分步长: {config.dt}")
        print(f"  相交阈值: {config.intersection_threshold:.6f}")
        print(f"  候选解阈值: {config.min_distance_threshold:.6f}")
        print(f"  碰撞半径: 地球={config.earth_radius:.4f}, 月球={config.moon_radius:.4f}")

        total_combinations = config.n_departure * config.n_alpha * config.n_beta
        print(f"\n总候选解数量: {config.n_departure} × {config.n_alpha} × {config.n_beta} = {total_combinations}")
        print("-" * 70)

    # 采样出发点
    departure_states, departure_times = sample_departure_points(orbit_departure, config.n_departure)

    # 预分配结果存储
    results: List[SearchResult] = []

    # 统计
    total_evaluated = 0
    total_collision = 0
    min_distances = []  # 用于统计

    # 搜索循环
    for dep_idx, (dep_state, dep_time) in enumerate(zip(departure_states, departure_times)):

        for alpha in config.alpha_grid:
            for beta in config.beta_grid:
                total_evaluated += 1

                # 1. 计算扰动速度
                v_new = compute_departure_velocity(dep_state, alpha, beta)

                # 2. 构初始状态并积分
                initial_state = np.concatenate([dep_state[:3], v_new])

                try:
                    traj_states, traj_times = integrate_trajectory(
                        initial_state,
                        config.max_transfer_time,
                        mu=MU,
                        dt=config.dt,
                        method=INTEGRATOR
                    )
                except Exception as e:
                    if verbose and total_evaluated == 1:
                        print(f"  积分错误: {e}")
                    continue

                # 3. 计算最小距离
                min_dist, _, _ = compute_min_distance_vectorized(traj_states, orbit_arrival.states)
                min_distances.append(min_dist)

                # 4. 碰撞检测
                collision, body, _ = check_collision(
                    traj_states, MU, config.earth_radius, config.moon_radius
                )
                if collision:
                    total_collision += 1

                # 5. 筛选可行解
                is_intersection = min_dist < config.intersection_threshold

                if not collision and (is_intersection or min_dist < config.min_distance_threshold):
                    result = SearchResult(
                        departure_idx=dep_idx,
                        departure_time=dep_time,
                        alpha=alpha,
                        beta=beta,
                        min_distance=min_dist,
                        intersection_found=is_intersection,
                        collision_found=False,
                        collision_body=None,
                        trajectory=traj_states if len(results) < 10 else None  # 只保存前10个轨迹
                    )
                    results.append(result)

                    if verbose and len(results) <= 5:
                        print(f"  可行解 #{len(results)}: "
                              f"dep_idx={dep_idx}, α={alpha:.4f}, β={beta:.4f}, "
                              f"min_dist={min_dist:.6f}, intersection={is_intersection}")

                # 早停检查
                if early_stop is not None and len(results) >= early_stop:
                    break

            if early_stop is not None and len(results) >= early_stop:
                break

        # 进度报告
        if verbose and (dep_idx + 1) % 20 == 0:
            progress = 100 * (dep_idx + 1) / config.n_departure
            print(f"  进度: {dep_idx+1}/{config.n_departure} ({progress:.1f}%) "
                  f"- 已评估:{total_evaluated} 碰撞:{total_collision} 可行:{len(results)}")

        if early_stop is not None and len(results) >= early_stop:
            if verbose:
                print(f"\n  达到早停条件 ({early_stop} 个可行解)，停止搜索")
            break

    # 统计报告
    if verbose:
        print("-" * 70)
        print(f"\n搜索完成统计:")
        print(f"  总评估候选解: {total_evaluated}")
        print(f"  碰撞数量: {total_collision} ({100*total_collision/total_evaluated:.1f}%)")
        print(f"  找到可行解: {len(results)}")

        if min_distances:
            print(f"\n最小距离统计:")
            print(f"  最小值: {np.min(min_distances):.6f}")
            print(f"  最大值: {np.max(min_distances):.6f}")
            print(f"  平均值: {np.mean(min_distances):.6f}")
            print(f"  中位数: {np.median(min_distances):.6f}")

    return results


# =============================================================================
# 调试函数
# =============================================================================

def debug_test(orbit_departure: OrbitData, orbit_arrival: OrbitData):
    """
    运行调试测试，验证各模块功能。
    """
    print("\n" + "=" * 70)
    print("调试测试")
    print("=" * 70)

    # 1. 测试轨道数据
    print("\n[1] 轨道数据检查:")
    print(f"  DRO: {len(orbit_departure.states)} 状态点, 周期={orbit_departure.period:.4f} TU")
    print(f"  RO: {len(orbit_arrival.states)} 状态点, 周期={orbit_arrival.period:.4f} TU")
    print(f"  DRO状态范围: x=[{orbit_departure.states[:,0].min():.3f}, {orbit_departure.states[:,0].max():.3f}]")
    print(f"  RO状态范围: x=[{orbit_arrival.states[:,0].min():.3f}, {orbit_arrival.states[:,0].max():.3f}]")

    # 2. 测试出发点采样
    print("\n[2] 出发点采样测试 (n=5):")
    dep_states, dep_times = sample_departure_points(orbit_departure, 5)
    for i, (t, s) in enumerate(zip(dep_times, dep_states)):
        r = np.linalg.norm(s[:3])
        v = np.linalg.norm(s[3:])
        print(f"  [{i}] t={t:.4f} TU, pos=({s[0]:.4f}, {s[1]:.4f}, {s[2]:.4f}), |r|={r:.4f}, |v|={v:.4f}")

    # 3. 测试速度计算
    print("\n[3] 速度扰动测试:")
    state = dep_states[0]
    print(f"  原始速度: ({state[3]:.6f}, {state[4]:.6f}, {state[5]:.6f}), |v|={np.linalg.norm(state[3:]):.6f}")

    for alpha in [0.5, 1.0, 1.5, 2.0]:
        v_new = compute_departure_velocity(state, alpha, beta=0.0)
        print(f"  α={alpha:.1f}: |v|={np.linalg.norm(v_new):.6f}")

    # 4. 测试前向积分
    print("\n[4] 前向积分测试 (T=1.0 TU):")
    v_new = compute_departure_velocity(state, alpha=1.0, beta=0.0)
    initial_state = np.concatenate([state[:3], v_new])

    traj_states, traj_times = integrate_trajectory(initial_state, 1.0, mu=MU, dt=DT, method='rk4')

    print(f"  积分步数: {len(traj_states)}")
    print(f"  起点: ({traj_states[0,0]:.4f}, {traj_states[0,1]:.4f}, {traj_states[0,2]:.4f})")
    print(f"  终点: ({traj_states[-1,0]:.4f}, {traj_states[-1,1]:.4f}, {traj_states[-1,2]:.4f})")

    # 5. 测试最小距离计算
    print("\n[5] 最小距离测试:")
    min_dist, _, _ = compute_min_distance_vectorized(traj_states, orbit_arrival.states)
    print(f"  轨迹->RO 最小距离: {min_dist:.6f}")

    # 6. 测试碰撞检测
    print("\n[6] 碰撞检测测试:")
    collision, body, _ = check_collision(traj_states, MU)
    print(f"  碰撞: {collision}, 天体: {body}")

    # 7. 测试局部最小值检测
    print("\n[7] 局部最小值检测:")
    has_min, min_dist, idx = detect_local_minimum(traj_states, orbit_arrival.states)
    print(f"  局部最小值: {has_min}, min_dist={min_dist:.6f}, idx={idx}")

    print("\n" + "=" * 70)
    print("调试测试完成")
    print("=" * 70)


# =============================================================================
# 主程序
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='DRO-RO 网格搜索')
    parser.add_argument('--debug', action='store_true', help='运行调试测试')
    parser.add_argument('--dro', type=str, default=DRO_FILE, help='DRO轨道文件')
    parser.add_argument('--ro', type=str, default=RO_FILE, help='RO轨道文件')
    parser.add_argument('--output', type=str, default=None, help='结果输出文件')
    parser.add_argument('--early-stop', type=int, default=None, help='找到多少个解后停止')

    args = parser.parse_args()

    print("=" * 70)
    print("DRO-RO 转移轨道网格搜索")
    print("=" * 70)

    # 加载轨道数据
    print(f"\n加载轨道数据...")
    print(f"  DRO: {args.dro}")
    print(f"  RO: {args.ro}")

    if not Path(args.dro).exists():
        print(f"\n错误: DRO文件不存在: {args.dro}")
        print("请修改 DRO_FILE 或使用 --dro 参数指定文件路径")
        sys.exit(1)

    if not Path(args.ro).exists():
        print(f"\n错误: RO文件不存在: {args.ro}")
        print("请修改 RO_FILE 或使用 --ro 参数指定文件路径")
        sys.exit(1)

    try:
        orbit_departure = OrbitData.from_json(args.dro)
        orbit_arrival = OrbitData.from_json(args.ro)
        print(f"\n加载成功!")
        print(f"  DRO: {len(orbit_departure.states)} 点, 周期={orbit_departure.period:.4f} TU")
        print(f"  RO: {len(orbit_arrival.states)} 点, 周期={orbit_arrival.period:.4f} TU")
    except Exception as e:
        print(f"\n加载错误: {e}")
        sys.exit(1)

    # 调试模式
    if args.debug:
        debug_test(orbit_departure, orbit_arrival)
        return

    # 创建搜索配置
    config = TransferSearchConfig()

    # 执行搜索
    results = grid_search(
        orbit_departure,
        orbit_arrival,
        config,
        verbose=True,
        early_stop=args.early_stop
    )

    # 保存结果
    if results:
        output_file = args.output
        if output_file is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"search_results_{timestamp}.json"

        # 转换为可序列化格式
        results_dict = []
        for r in results:
            result_item = {
                'departure_idx': r.departure_idx,
                'departure_time': r.departure_time,
                'alpha': r.alpha,
                'beta': r.beta,
                'min_distance': r.min_distance,
                'intersection_found': r.intersection_found,
                'collision_found': r.collision_found,
            }
            if r.trajectory is not None:
                result_item['trajectory'] = r.trajectory.tolist()
            results_dict.append(result_item)

        with open(output_file, 'w') as f:
            json.dump(results_dict, f, indent=2)

        print(f"\n结果已保存: {output_file}")
        print(f"共 {len(results)} 个可行解")

        # 显示前5个最佳解
        results_sorted = sorted(results, key=lambda x: x.min_distance)[:5]
        print(f"\n前5个最佳可行解 (按min_distance排序):")
        for i, r in enumerate(results_sorted):
            print(f"  {i+1}. dep_idx={r.departure_idx}, α={r.alpha:.4f}, β={r.beta:.4f}, "
                  f"min_dist={r.min_distance:.6f}, intersection={r.intersection_found}")
    else:
        print("\n" + "=" * 70)
        print("警告: 未找到任何可行解!")
        print("=" * 70)
        print("\n建议检查:")
        print("  1. 轨道数据是否正确 (使用 --debug 检查)")
        print("  2. 搜索参数范围是否合适")
        print("  3. 阈值设置是否过严")
        print("  4. 积分参数是否正确")
        print("\n可调整的参数:")
        print(f"  - MIN_DISTANCE_THRESHOLD = {MIN_DISTANCE_THRESHOLD} (当前)")
        print(f"  - INTERSECTION_THRESHOLD = {INTERSECTION_THRESHOLD} (当前)")
        print(f"  - MAX_TRANSFER_TIME = {MAX_TRANSFER_TIME} (当前)")


if __name__ == "__main__":
    main()
