import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp
from mpl_toolkits.mplot3d import Axes3D

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # 或者 ['Microsoft YaHei']、['KaiTi']等
plt.rcParams['axes.unicode_minus'] = False    # 解决负号显示问题

# ============================================================
# 1. CRTBP模型下的DRO轨道计算（平面轨道）
# ============================================================

class CRTBP_DRO:
    """圆形限制性三体问题下的DRO轨道计算类"""

    def __init__(self, mu=0.012155099):  # 地球-月球系统质量比
        """
        初始化CRTBP系统

        参数:
        mu: 质量比 = m2/(m1+m2)，地球-月球系统约为1/82.27
        """
        self.mu = mu
        self.m1 = 1.0 - mu  # 地球（较大天体）
        self.m2 = mu  # 月球（较小天体）

        # 主天体位置（在旋转坐标系中）
        self.x1 = -mu  # 地球位置
        self.x2 = 1.0 - mu  # 月球位置

    def r1_r2(self, state):
        """
        计算到两个主天体的距离

        参数:
        state: [x, y, z, vx, vy, vz]
        """
        x, y, z = state[0], state[1], state[2]

        # 到地球的距离
        r1 = np.sqrt((x - self.x1) ** 2 + y ** 2 + z ** 2)
        # 到月球的距离
        r2 = np.sqrt((x - self.x2) ** 2 + y ** 2 + z ** 2)

        return r1, r2

    def equations_2d(self, t, state):
        """
        平面CRTBP运动方程（二维）

        参数:
        t: 时间
        state: [x, y, vx, vy]

        返回:
        dstate/dt: [vx, vy, ax, ay]
        """
        x, y, vx, vy = state

        # 计算距离
        r1 = np.sqrt((x - self.x1) ** 2 + y ** 2)
        r2 = np.sqrt((x - self.x2) ** 2 + y ** 2)

        # 防止除以零
        r1 = max(r1, 1e-10)
        r2 = max(r2, 1e-10)

        # 势函数导数
        Omega_x = x - (1 - self.mu) * (x - self.x1) / r1 ** 3 - self.mu * (x - self.x2) / r2 ** 3
        Omega_y = y - (1 - self.mu) * y / r1 ** 3 - self.mu * y / r2 ** 3

        # 运动方程（含科里奥利力和离心力）
        ax = 2 * vy + Omega_x
        ay = -2 * vx + Omega_y

        return [vx, vy, ax, ay]

    def equations_3d(self, t, state):
        """
        三维CRTBP运动方程

        参数:
        t: 时间
        state: [x, y, z, vx, vy, vz]
        """
        x, y, z, vx, vy, vz = state

        # 计算距离
        r1 = np.sqrt((x - self.x1) ** 2 + y ** 2 + z ** 2)
        r2 = np.sqrt((x - self.x2) ** 2 + y ** 2 + z ** 2)

        # 防止除以零
        r1 = max(r1, 1e-10)
        r2 = max(r2, 1e-10)

        # 势函数导数
        Omega_x = x - (1 - self.mu) * (x - self.x1) / r1 ** 3 - self.mu * (x - self.x2) / r2 ** 3
        Omega_y = y - (1 - self.mu) * y / r1 ** 3 - self.mu * y / r2 ** 3
        Omega_z = - (1 - self.mu) * z / r1 ** 3 - self.mu * z / r2 ** 3

        # 运动方程
        ax = 2 * vy + Omega_x
        ay = -2 * vx + Omega_y
        az = Omega_z

        return [vx, vy, vz, ax, ay, az]

    def jacobi_constant(self, state):
        """
        计算Jacobi常数

        参数:
        state: [x, y, z, vx, vy, vz]
        """
        if len(state) == 4:  # 二维情况
            x, y, vx, vy = state
            z, vz = 0.0, 0.0
        else:
            x, y, z, vx, vy, vz = state

        # 计算距离
        r1 = np.sqrt((x - self.x1) ** 2 + y ** 2 + z ** 2)
        r2 = np.sqrt((x - self.x2) ** 2 + y ** 2 + z ** 2)

        # 速度平方
        v2 = vx ** 2 + vy ** 2 + vz ** 2

        # 有效势
        U = (1 - self.mu) / r1 + self.mu / r2

        # Jacobi常数 C = 2U + (x^2 + y^2) - v^2
        C = 2 * U + (x ** 2 + y ** 2) - v2

        return C

    def find_dro_initial_condition(self, x0_range=None, target_period=None):
        """
        寻找DRO轨道的初始条件

        基于Broucke(1968)表7中的数据

        返回:
        初始状态 [x0, 0, 0, 0, y0_dot, 0] 对于二维轨道
        """
        if x0_range is None:
            # 根据Broucke表7，DRO的x0范围大约在0.99-2.1之间
            x0_range = np.linspace(1.0, 2.0, 20)

        # Broucke表7中的示例数据（Family F）
        # 这些是已知的DRO初始条件
        known_ics = [
            (0.988193899, -8.667382311, 1.256849114),  # 轨道1
            (0.990407944, -3.586276255, 0.212458154),  # 轨道5
            (1.000000006, -2.411504377, 0.431695485),  # 轨道47
            (1.099999978, -2.098386951, 0.600010492),  # 轨道160
            (1.299999991, -2.189502868, 0.760180560),  # 轨道169
            (1.599999953, -2.395033752, 0.955489101),  # 轨道183
            (2.001001321, -2.709762699, 1.166711985),  # 轨道193
        ]

        # 返回一个代表性的初始条件
        # 例如：选择轨道169的初始条件
        x0 = 1.299999991
        y0_dot = -2.189502868

        return np.array([x0, 0.0, 0.0, 0.0, y0_dot, 0.0])


# ============================================================
# 2. DRO轨道计算与可视化
# ============================================================

def compute_dro_trajectory(mu=0.012155099, initial_state=None,
                           T=10.0, n_points=10000, dim=2):
    """
    计算DRO轨道

    参数:
    mu: 质量比
    initial_state: 初始状态
    T: 积分时间
    n_points: 输出点数
    dim: 维度（2或3）

    返回:
    t, states
    """
    crtbp = CRTBP_DRO(mu)

    if initial_state is None:
        # 使用默认的DRO初始条件（基于Broucke表7）
        if dim == 2:
            # 二维DRO初始条件
            # 选择x0=1.3附近的DRO轨道
            x0 = 1.299999991
            y0_dot = -2.189502868
            initial_state = [x0, 0.0, 0.0, y0_dot]
        else:
            # 三维DRO（带小倾角）
            x0 = 1.299999991
            y0_dot = -2.189502868
            z0 = 0.1  # 小z方向偏移
            vz0 = 0.05  # 小z方向速度
            initial_state = [x0, 0.0, z0, 0.0, y0_dot, vz0]

    # 时间数组
    t_span = (0, T)
    t_eval = np.linspace(0, T, n_points)

    # 选择方程
    if dim == 2:
        equations = crtbp.equations_2d
    else:
        equations = crtbp.equations_3d

    # 数值积分
    sol = solve_ivp(equations, t_span, initial_state,
                    t_eval=t_eval, method='DOP853',
                    rtol=1e-12, atol=1e-12)

    return sol.t, sol.y


def plot_dro_trajectory(t, states, mu=0.012155099, title="DRO轨道 (CRTBP)"):
    """
    绘制DRO轨道

    参数:
    t: 时间数组
    states: 状态数组 [x, y, z, vx, vy, vz] 或 [x, y, vx, vy]
    """
    crtbp = CRTBP_DRO(mu)

    # 判断维度
    if states.shape[0] == 4:  # 二维
        x, y = states[0], states[1]
        z = np.zeros_like(x)
        dim = 2
    else:  # 三维
        x, y, z = states[0], states[1], states[2]
        dim = 3

    # 计算Jacobi常数（用于验证精度）
    jacobi = []
    for i in range(states.shape[1]):
        if dim == 2:
            state_i = [states[0, i], states[1, i], states[2, i], states[3, i]]
        else:
            state_i = states[:, i]
        jacobi.append(crtbp.jacobi_constant(state_i))
    jacobi = np.array(jacobi)

    # 绘图
    if dim == 2:
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # 轨道图
        ax = axes[0, 0]
        ax.plot(x, y, 'b-', linewidth=1, label='DRO轨道')
        # 标记主天体
        ax.plot(crtbp.x1, 0, 'ro', markersize=8, label=f'地球 (m1={1 - mu:.4f})')
        ax.plot(crtbp.x2, 0, 'go', markersize=6, label=f'月球 (m2={mu:.4f})')
        ax.set_xlabel('x (归一化单位)')
        ax.set_ylabel('y (归一化单位)')
        ax.set_title(title)
        ax.axis('equal')
        ax.grid(True, alpha=0.3)
        ax.legend()

        # 时间历程
        ax = axes[0, 1]
        ax.plot(t, x, 'r-', label='x(t)')
        ax.plot(t, y, 'b-', label='y(t)')
        ax.set_xlabel('时间 (归一化单位)')
        ax.set_ylabel('位置')
        ax.set_title('位置随时间变化')
        ax.grid(True, alpha=0.3)
        ax.legend()

        # 速度
        vx, vy = states[2], states[3]
        ax = axes[1, 0]
        ax.plot(t, vx, 'r--', label='vx(t)')
        ax.plot(t, vy, 'b--', label='vy(t)')
        ax.set_xlabel('时间 (归一化单位)')
        ax.set_ylabel('速度')
        ax.set_title('速度随时间变化')
        ax.grid(True, alpha=0.3)
        ax.legend()

        # Jacobi常数（守恒量验证）
        ax = axes[1, 1]
        ax.plot(t, jacobi, 'k-', linewidth=1)
        ax.set_xlabel('时间 (归一化单位)')
        ax.set_ylabel('Jacobi常数 C')
        ax.set_title(f'Jacobi常数 (变化: {jacobi.max() - jacobi.min():.2e})')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

    else:  # 三维
        fig = plt.figure(figsize=(15, 10))

        # 三维轨道
        ax1 = fig.add_subplot(221, projection='3d')
        ax1.plot(x, y, z, 'b-', linewidth=1)
        ax1.scatter([crtbp.x1], [0], [0], color='red', s=100, label='地球')
        ax1.scatter([crtbp.x2], [0], [0], color='green', s=80, label='月球')
        ax1.set_xlabel('x')
        ax1.set_ylabel('y')
        ax1.set_zlabel('z')
        ax1.set_title(title)
        ax1.legend()

        # 投影到xy平面
        ax2 = fig.add_subplot(222)
        ax2.plot(x, y, 'b-')
        ax2.plot(crtbp.x1, 0, 'ro', markersize=8)
        ax2.plot(crtbp.x2, 0, 'go', markersize=6)
        ax2.set_xlabel('x')
        ax2.set_ylabel('y')
        ax2.set_title('xy平面投影')
        ax2.axis('equal')
        ax2.grid(True, alpha=0.3)

        # 时间历程
        ax3 = fig.add_subplot(223)
        ax3.plot(t, x, 'r-', label='x')
        ax3.plot(t, y, 'g-', label='y')
        ax3.plot(t, z, 'b-', label='z')
        ax3.set_xlabel('时间')
        ax3.set_ylabel('位置')
        ax3.set_title('位置随时间变化')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Jacobi常数
        ax4 = fig.add_subplot(224)
        ax4.plot(t, jacobi, 'k-')
        ax4.set_xlabel('时间')
        ax4.set_ylabel('Jacobi常数 C')
        ax4.set_title(f'Jacobi常数 (变化: {jacobi.max() - jacobi.min():.2e})')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

    plt.show()

    return fig


# ============================================================
# 3. 轨道族系分析
# ============================================================

def plot_dro_family():
    """
    绘制DRO轨道族系（基于Broucke表7的数据）
    """
    # 从Broucke表7中选择代表性轨道
    family_data = [
        (0.988193899, -8.667382311, "Orbit 1"),
        (0.990407944, -3.586276255, "Orbit 5"),
        (1.000000006, -2.411504377, "Orbit 47"),
        (1.099999978, -2.098386951, "Orbit 160"),
        (1.299999991, -2.189502868, "Orbit 169"),
        (1.599999953, -2.395033752, "Orbit 183"),
        (2.001001321, -2.709762699, "Orbit 193"),
    ]

    crtbp = CRTBP_DRO()
    plt.figure(figsize=(10, 8))

    for x0, y0_dot, label in family_data:
        # 计算轨道
        init_state = [x0, 0.0, 0.0, y0_dot]
        t, states = compute_dro_trajectory(
            initial_state=init_state, T=2 * np.pi * 2, n_points=2000, dim=2)
        x, y = states[0], states[1]

        # 绘制
        plt.plot(x, y, linewidth=1, label=label)

    # 标记主天体
    plt.plot(crtbp.x1, 0, 'ro', markersize=8, label='地球')
    plt.plot(crtbp.x2, 0, 'go', markersize=6, label='月球')

    plt.xlabel('x (归一化单位)')
    plt.ylabel('y (归一化单位)')
    plt.title('DRO轨道族系 (Family F, Broucke 1968)')
    plt.axis('equal')
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper right', fontsize=8)
    plt.show()


# ============================================================
# 4. 星历模型转换
# ============================================================

class EphemerisDRO:
    """星历模型下的DRO轨道计算类"""

    def __init__(self, mu=0.012155099):
        """
        初始化星历模型转换

        参数:
        mu: 质量比
        """
        self.crtbp = CRTBP_DRO(mu)

        # 物理常数（地球-月球系统）
        self.DU = 384400.0  # 距离单位: km (地月平均距离)
        self.TU = 375190.26  # 时间单位: seconds (使GM=1的时间单位)
        self.mu_earth = 398600.4418  # 地球引力常数 km^3/s^2
        self.mu_moon = 4902.8000  # 月球引力常数 km^3/s^2

    def crtbp_to_physical(self, state_crtbp, t_crtbp):
        """
        将CRTBP状态转换为物理单位（地球质心惯性系）

        参数:
        state_crtbp: CRTBP状态 [x, y, z, vx, vy, vz] (归一化单位)
        t_crtbp: CRTBP时间 (归一化单位)

        返回:
        state_phys: 物理状态 [X, Y, Z, VX, VY, VZ] (km, km/s)
        t_phys: 物理时间 (seconds)
        """
        x, y, z, vx, vy, vz = state_crtbp
        tau = t_crtbp  # 归一化时间

        # 主天体在旋转系中的位置
        x1 = self.crtbp.x1
        x2 = self.crtbp.x2

        # 地球和月球在旋转系中的位置
        r1_rot = np.array([x1, 0.0, 0.0])
        r2_rot = np.array([x2, 0.0, 0.0])
        r_sat_rot = np.array([x, y, z])

        # 旋转矩阵（从旋转系到惯性系）
        # 在时间tau，旋转角为tau
        cos_t = np.cos(tau)
        sin_t = np.sin(tau)

        R_rot_to_inertial = np.array([
            [cos_t, -sin_t, 0.0],
            [sin_t, cos_t, 0.0],
            [0.0, 0.0, 1.0]
        ])

        # 旋转系中的速度包含两部分：旋转系中的相对速度 + 由于旋转引起的速度
        omega = np.array([0.0, 0.0, 1.0])  # 旋转角速度（归一化单位）

        # 惯性系中的位置
        r_sat_inertial = R_rot_to_inertial @ r_sat_rot

        # 惯性系中的速度 = R*(v_rel) + R_dot * r
        # R_dot = omega × R
        v_rel = np.array([vx, vy, vz])
        v_inertial = R_rot_to_inertial @ v_rel + np.cross(omega, r_sat_inertial)

        # 转换为物理单位
        r_phys = r_sat_inertial * self.DU
        v_phys = v_inertial * (self.DU / self.TU)
        t_phys = tau * self.TU

        # 转换为地球质心坐标系
        # 在惯性系中，地球位置为：-mu * [cos(tau), sin(tau), 0]
        earth_pos_inertial = -self.crtbp.mu * np.array([cos_t, sin_t, 0.0])
        earth_vel_inertial = -self.crtbp.mu * np.array([-sin_t, cos_t, 0.0])

        # 卫星相对于地球的位置
        r_rel_earth = r_phys - earth_pos_inertial * self.DU
        v_rel_earth = v_phys - earth_vel_inertial * (self.DU / self.TU)

        return r_rel_earth, v_rel_earth, t_phys

    def compute_ephemeris_dro(self, initial_state_crtbp, T_crtbp, n_points=10000):
        """
        计算星历模型下的DRO轨道

        参数:
        initial_state_crtbp: CRTBP初始状态（归一化单位）
        T_crtbp: 积分时间（归一化单位）
        n_points: 输出点数

        返回:
        positions: 位置数组 (km)
        times: 时间数组 (seconds)
        """
        # 首先在CRTBP中积分
        t_crtbp, states_crtbp = compute_dro_trajectory(
            initial_state=initial_state_crtbp, T=T_crtbp,
            n_points=n_points, dim=3 if len(initial_state_crtbp) == 6 else 2)

        # 转换为物理单位
        positions = []
        times = []

        for i in range(len(t_crtbp)):
            state_i = states_crtbp[:, i]
            r, v, t = self.crtbp_to_physical(state_i, t_crtbp[i])
            positions.append(r)
            times.append(t)

        return np.array(positions), np.array(times)

    def plot_ephemeris_dro(self, positions, times, title="DRO轨道 (星历模型)"):
        """
        绘制星历模型下的DRO轨道
        """
        fig = plt.figure(figsize=(15, 5))

        # 3D轨道
        ax1 = fig.add_subplot(131, projection='3d')
        ax1.plot(positions[:, 0], positions[:, 1], positions[:, 2], 'b-', linewidth=1)
        ax1.scatter([0], [0], [0], color='red', s=100, label='地球')
        ax1.set_xlabel('X (km)')
        ax1.set_ylabel('Y (km)')
        ax1.set_zlabel('Z (km)')
        ax1.set_title('三维轨道')
        ax1.legend()

        # XY平面投影
        ax2 = fig.add_subplot(132)
        ax2.plot(positions[:, 0], positions[:, 1], 'b-', linewidth=1)
        ax2.scatter(0, 0, color='red', s=100, label='地球')
        ax2.set_xlabel('X (km)')
        ax2.set_ylabel('Y (km)')
        ax2.set_title('XY平面投影')
        ax2.axis('equal')
        ax2.grid(True, alpha=0.3)
        ax2.legend()

        # 距离地球的变化
        ax3 = fig.add_subplot(133)
        r_earth = np.linalg.norm(positions, axis=1)
        ax3.plot(times / 3600, r_earth, 'k-', linewidth=1)  # 转换为小时
        ax3.set_xlabel('时间 (hours)')
        ax3.set_ylabel('地心距离 (km)')
        ax3.set_title('地心距离变化')
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

        return fig


# ============================================================
# 主程序：演示DRO轨道计算
# ============================================================

def main():
    """主程序：演示DRO轨道计算"""

    print("=" * 60)
    print("DRO轨道计算程序 (基于Broucke 1968)")
    print("=" * 60)

    # 1. CRTBP模型下的平面DRO轨道
    print("\n1. 计算CRTBP模型下的平面DRO轨道...")

    # 使用Broucke表7中的初始条件（Family F, Orbit 169）
    x0 = 1.299999991
    y0_dot = -2.189502868
    init_state_2d = [x0, 0.0, 0.0, y0_dot]

    print(f"   初始条件: x0 = {x0:.6f}, y0_dot = {y0_dot:.6f}")

    # 计算轨道
    t, states = compute_dro_trajectory(
        initial_state=init_state_2d, T=2 * np.pi * 3, n_points=5000, dim=2)

    # 绘制
    plot_dro_trajectory(t, states, title="平面DRO轨道 (CRTBP模型)")

    # 2. DRO轨道族系
    print("\n2. 绘制DRO轨道族系...")
    plot_dro_family()

    # 3. 三维DRO轨道
    print("\n3. 计算三维DRO轨道（带小倾角）...")

    # 给初始条件添加小z方向分量
    init_state_3d = [x0, 0.0, 0.05, 0.0, y0_dot, 0.02]

    t_3d, states_3d = compute_dro_trajectory(
        initial_state=init_state_3d, T=2 * np.pi * 3, n_points=5000, dim=3)

    plot_dro_trajectory(t_3d, states_3d, title="三维DRO轨道 (CRTBP模型)")

    # 4. 星历模型转换
    print("\n4. 将DRO轨道转换到星历模型...")

    ephemeris = EphemerisDRO()

    # 使用相同的初始条件
    positions, times = ephemeris.compute_ephemeris_dro(
        init_state_3d, T_crtbp=2 * np.pi * 3, n_points=5000)

    ephemeris.plot_ephemeris_dro(positions, times)

    print(f"\n   轨道持续时间: {times[-1] / 3600:.2f} 小时")
    print(f"   最大地心距离: {np.max(np.linalg.norm(positions, axis=1)):.0f} km")
    print(f"   最小地心距离: {np.min(np.linalg.norm(positions, axis=1)):.0f} km")

    print("\n" + "=" * 60)
    print("计算完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()