import numpy as np
from scipy import integrate
from scipy.integrate import solve_ivp


class CR3BP_Dynamics:
    """CR3BP动力学方程

    本类封装了CR3BP的动力学模型，提供状态传播、状态转移矩阵计算、Jacobi常数计算等核心功能。
    支持6维状态向量（位置+速度）和42维增广状态向量（状态+状态转移矩阵）的数值积分。

    主要功能：
        - 运动方程定义与数值积分
        - 状态转移矩阵(STM)的计算与传播
        - Jacobi常数的实时监控与守恒性检验
        - 截面穿越检测（用于Poincaré映射和周期轨道搜索）

    属性：
        system (CR3BP_System): CR3BP系统对象，包含质量参数μ等系统常数
        equations_of_motion (callable): 6维运动方程函数
        equations_with_stm (callable): 42维增广状态方程函数（包含STM）
        integrator (str): 数值积分器类型（默认'RK45'）
        rtol (float): 相对积分容差
        atol (float): 绝对积分容差
        max_step (float): 最大积分步长
        last_trajectory (array): 最近一次积分的轨迹 [t, y]
        last_stm (array): 最近一次积分的状态转移矩阵
        cross_section_tolerance (float): 截面检测容差
        last_crossing (tuple): 上次穿过截面的点和时间
        jacobi_history (list): Jacobi常数历史记录
        jacobi_error (float): Jacobi常数误差（用于精度检验）
        initialized (bool): 初始化完成标志

    方法：
        __init__(system): 初始化动力学对象
        CR3BP_Omega3_First_Partials(t, SV): 计算等效势能的一阶偏导
        CR3BP_Omega3_Second_Partials(t, SV): 计算等效势能的二阶偏导（Hessian矩阵）
        CR3BP_Dynamics(t, SV): 6维状态向量的运动方程
        get_CR3BP_A(t, SV): 获取Jacobi矩阵A(t)（用于STM计算）
        get_CR3BP_dot_STM(t, SV, STM): 计算状态转移矩阵的一阶导
        CR3BP_Dynamics_42(t, State): 42维增广状态向量的运动方程
        CR3BP_Propagation(SV0, tf, N): 6维状态传播（直接积分）
        CR3BP_Propagation_42(SV0, tf, N): 42维增广状态传播（包含STM）
        compute_acceleration(state, mu): 计算给定状态下的加速度
        compute_state_transition_matrix(state, t): 计算状态转移矩阵
        integrate_trajectory(initial_state, t_span, t_eval): 通用轨迹积分接口
        compute_jacobi_constant(state): 实时计算Jacobi常数
        check_cross_section(state, plane, value): 检查是否穿过指定截面
    """

    # 类属性
    DEFAULT_TOLERANCE = 1e-12  # 默认积分容差
    DEFAULT_MAX_STEP = 0.01  # 默认最大步长
    STM_DIMENSION = 42  # 状态转移矩阵维度 (6x6 + 6状态)

    def __init__(self, system):
        """初始化动力学

        参数：
        - system: CR3BP_System对象
        """
        # 关联的CR3BP系统
        self.system = system

        # 运动方程（将在计算时生成）
        self.equations_of_motion = None  # 运动方程函数
        self.equations_with_stm = None  # 包含STM的运动方程函数

        # 积分器设置
        self.integrator = "RK45"  # 默认积分器
        self.rtol = self.DEFAULT_TOLERANCE  # 相对容差
        self.atol = self.DEFAULT_TOLERANCE  # 绝对容差
        self.max_step = self.DEFAULT_MAX_STEP  # 最大步长

        # 缓存最近的积分结果
        self.last_trajectory = None  # 最近的轨迹 [t, y]
        self.last_stm = None  # 最近的状态转移矩阵

        # 截面检测设置
        self.cross_section_tolerance = 1e-8  # 截面检测容差
        self.last_crossing = None  # 上次穿过截面的点和时间

        # 能量监控
        self.jacobi_history = []  # Jacobi常数历史
        self.jacobi_error = 0.0  # Jacobi常数误差

        # 计算标志
        self.initialized = True  # 初始化完成

    def CR3BP_Omega3_First_Partials(self, t, SV):
        """
        求圆型限制性三体模型等效势能对x,y,z一阶偏导
            输入为时间，位置速度向量。
            输出为等效势能一阶偏导组成的3*1向量dOmega3
        """

        # 确定系统相关常数
        mu = self.system.mu

        # 航天器位置
        x = SV[0]
        y = SV[1]
        z = SV[2]

        # 定义航天器与两大天体之间的距离r1,r2,r3
        r1 = ((x + mu) ** 2 + y**2 + z**2) ** 0.5
        r2 = ((1.0 - x - mu) ** 2 + y**2 + z**2) ** 0.5

        # 定义圆型限制性三体模型等效势能
        Omega3 = (
            0.5 * (x**2 + y**2 + z**2)
            + (1.0 - mu) / r1
            + mu / r2
            + 0.5 * mu * (1.0 - mu)
        )

        # 定义圆型限制性三体模型等效势能对x,y,z的偏导
        dOmega3_dx = x - (1.0 - mu) / r1**3 * (mu + x) + mu / r2**3 * (1.0 - mu - x)
        dOmega3_dy = y * (1.0 - (1.0 - mu) / r1**3 - mu / r2**3)
        dOmega3_dz = -z * ((1.0 - mu) / r1**3 + mu / r2**3)

        dOmega3 = np.empty(3)

        dOmega3[0] = dOmega3_dx
        dOmega3[1] = dOmega3_dy
        dOmega3[2] = dOmega3_dz

        return dOmega3

    def CR3BP_Omega3_Second_Partials(self, t, SV):
        """
        求圆型限制性三体模型等效势能对x,y,z二阶偏导（Hessian矩阵）
            输入为时间，位置速度向量。
            输出为等效势能二阶偏导组成的3*3Hessian矩阵ddOmega3。
        """

        # 确定系统相关常数
        mu = self.system.mu

        # 航天器位置
        x = SV[0]
        y = SV[1]
        z = SV[2]

        # 定义航天器与两大天体之间的距离r1,r2,r3
        r1 = ((x + mu) ** 2 + y**2 + z**2) ** 0.5
        r2 = ((1.0 - x - mu) ** 2 + y**2 + z**2) ** 0.5

        # 定义圆型限制性三体模型等效势能对x,y,z的二阶偏导,返回Hessian矩阵

        ddOmega3_dxx = (
            1.0
            + 3.0 * (1.0 - mu) * (x + mu) ** 2 / r1**5
            + 3.0 * mu * (1.0 - mu - x) ** 2 / r2**5
            - (1.0 - mu) / r1**3
            - mu / r2**3
        )
        ddOmega3_dxy = (
            3.0 * (1.0 - mu) * (x + mu) * y / r1**5
            - 3.0 * mu * (1.0 - mu - x) * y / r2**5
        )
        ddOmega3_dxz = (
            3.0 * (1.0 - mu) * (x + mu) * z / r1**5
            - 3.0 * mu * (1.0 - mu - x) * z / r2**5
        )

        ddOmega3_dyx = ddOmega3_dxy
        ddOmega3_dyy = (
            1.0
            + 3.0 * (1.0 - mu) * y**2 / r1**5
            + 3.0 * mu * y**2 / r2**5
            - (1.0 - mu) / r1**3
            - mu / r2**3
        )
        ddOmega3_dyz = 3.0 * (1.0 - mu) * y * z / r1**5 + 3.0 * mu * y * z / r2**5

        ddOmega3_dzx = ddOmega3_dxz
        ddOmega3_dzy = ddOmega3_dyz
        ddOmega3_dzz = (
            3.0 * (1.0 - mu) * z**2 / r1**5
            + 3.0 * mu * z**2 / r2**5
            - (1.0 - mu) / r1**3
            - mu / r2**3
        )

        ddOmega3 = np.empty((3, 3))

        ddOmega3[0, 0] = ddOmega3_dxx
        ddOmega3[0, 1] = ddOmega3_dxy
        ddOmega3[0, 2] = ddOmega3_dxz

        ddOmega3[1, 0] = ddOmega3_dyx
        ddOmega3[1, 1] = ddOmega3_dyy
        ddOmega3[1, 2] = ddOmega3_dyz

        ddOmega3[2, 0] = ddOmega3_dzx
        ddOmega3[2, 1] = ddOmega3_dzy
        ddOmega3[2, 2] = ddOmega3_dzz

        return ddOmega3

    def CR3BP_Dynamics(self, t, SV):
        """
        定义圆型限制性三体问题模型下航天器动力学方程
            输入为时间，位置速度向量。
            输出为位置速度向量对时间一阶导组成的6*1向量CR3BP_dot_SV。
        """

        # 获取圆型限制性三体问题模型等效势能一阶导
        dOmega3 = self.CR3BP_Omega3_First_Partials(t, SV)

        # 航天器速度
        vx = SV[3]
        vy = SV[4]
        vz = SV[5]

        # 定义dot_SV
        dot_x = vx
        dot_y = vy
        dot_z = vz
        dot_vx = 2.0 * dot_y + dOmega3[0]
        dot_vy = -2.0 * dot_x + dOmega3[1]
        dot_vz = dOmega3[2]

        CR3BP_dot_SV = np.empty(6)

        CR3BP_dot_SV[0] = dot_x
        CR3BP_dot_SV[1] = dot_y
        CR3BP_dot_SV[2] = dot_z
        CR3BP_dot_SV[3] = dot_vx
        CR3BP_dot_SV[4] = dot_vy
        CR3BP_dot_SV[5] = dot_vz

        # 返回状态向量一阶导，即速度、加速度
        return CR3BP_dot_SV

    def get_CR3BP_A(self, t, SV):
        """
        获取Jacobi矩阵A(t)
            输入为时间，位置速度向量。
            输出为Jacobi矩阵CR3BP_A。
        """

        # 定义0矩阵
        O = np.zeros((3, 3))

        # 定义I矩阵
        I = np.eye(3)

        # 定义K矩阵
        K = np.array(([0, 2.0, 0], [-2.0, 0, 0], [0, 0, 0]))

        # 定义Hessian矩阵，由等效势能Omega3对相空间变量的二阶偏导组成
        ddOmega3 = self.CR3BP_Omega3_Second_Partials(t, SV)

        # Jacobi矩阵A(t)
        CR3BP_A = np.empty((6, 6))

        CR3BP_A[0:3, 0:3] = O
        CR3BP_A[0:3, 3:6] = I
        CR3BP_A[3:6, 0:3] = ddOmega3
        CR3BP_A[3:6, 3:6] = K

        return CR3BP_A

    def get_CR3BP_dot_STM(self, t, SV, CR3BP_STM):
        """
        定义状态转移矩阵一阶导
            输入为时间，位置速度向量。
            输出为状态转移矩阵对时间一阶导CR3BP_dot_STM。
        """

        # 获取Jacobi矩阵
        CR3BP_A = self.get_CR3BP_A(t, SV)

        # 状态转移矩阵一阶导
        CR3BP_dot_STM = np.matmul(CR3BP_A, CR3BP_STM)

        return CR3BP_dot_STM

    def CR3BP_Dynamics_42(self, t, State):
        """
        定义圆型限制性三体问题模型下航天器42维状态向量动力学方程
            输入为时间，42维状态向量。
            输出为42维状态向量对时间的一阶导CR3BP_dot_State。
            42维状态向量前6项为航天器位置速度向量，后36项为状态转移矩阵。
        """

        # 当前位置速度向量
        CR3BP_SV = State[0:6]
        # 位置速度一阶导
        CR3BP_dot_SV = self.CR3BP_Dynamics(t, CR3BP_SV)

        # 当前状态转移矩阵
        CR3BP_phi = State[6:42].reshape((6, 6))
        # 状态转移矩阵一阶导
        CR3BP_dot_phi = self.get_CR3BP_dot_STM(t, CR3BP_SV, CR3BP_phi)

        # 42维状态向量一阶导
        CR3BP_dot_State = np.concatenate((CR3BP_dot_SV, CR3BP_dot_phi.reshape(36)))

        return CR3BP_dot_State

    def CR3BP_Propagation(self, SV0, tf, N):
        """
        圆型限制性三体问题模型下航天器轨道传播
            输入为初始位置速度向量，积分时间，时间节点数量。
            输出为各节点的对应时刻与位置速度向量CR3BP_t, CR3BP_SV。
            直接积分。
        """

        # 定义时间序列
        CR3BP_t = np.linspace(0, tf, N)

        # 数值积分
        output = integrate.solve_ivp(
            self.CR3BP_Dynamics,
            [CR3BP_t[0], CR3BP_t[-1]],
            SV0,
            method="DOP853",
            t_eval=CR3BP_t,
            rtol=10e-18,
            atol=10e-18,
        )

        CR3BP_SV = output.y

        return CR3BP_t, CR3BP_SV

    def CR3BP_Propagation_42(self, SV0, tf, N):
        """
        圆型限制性三体问题模型下航天器42维状态向量轨道传播
            输入为初始位置速度向量，积分时间，时间节点数量。
            输出为各节点的对应时刻，42维状态向量，位置速度向量与状态转移矩阵CR3BP_t, CR3BP_State, CR3BP_SV, CR3BP_STM。
            状态向量为42维，前6项为位置、速度向量，后36项为状态转移矩阵元素。
            直接积分。
        """

        # 定义时间序列
        CR3BP_t = np.linspace(0, tf, N)

        # 初始状态转移矩阵
        phi_0 = np.eye(6)

        # 初始状态矩阵
        State_0 = np.concatenate((SV0, phi_0.reshape(36)))

        # 数值积分
        output = integrate.solve_ivp(
            self.CR3BP_Dynamics_42,
            [CR3BP_t[0], CR3BP_t[-1]],
            State_0,
            method="DOP853",
            t_eval=CR3BP_t,
            rtol=10e-10,
            atol=10e-10,
        )

        # 获取状态向量
        CR3BP_State = output.y
        CR3BP_State = CR3BP_State.reshape(42, (np.size(CR3BP_t)), order="F")
        CR3BP_SV = CR3BP_State[0:6, :]
        CR3BP_STM = (
            np.transpose(CR3BP_State[6:42, :])
            .reshape((np.size(CR3BP_t)), 36, 1, order="F")
            .reshape((np.size(CR3BP_t)), 6, 6, order="C")
        )

        return CR3BP_t, CR3BP_State, CR3BP_SV, CR3BP_STM

    def compute_acceleration(self, state, mu):
        """计算加速度"""
        print(1)

    def compute_state_transition_matrix(self, state, t):
        """计算状态转移矩阵"""

        print(1)

    def integrate_trajectory(self, initial_state, t_span, t_eval):
        """积分轨迹"""
        print(1)

    def compute_jacobi_constant(self, state):
        """实时计算Jacobi常数"""
        print(1)

    def check_cross_section(self, state, plane, value):
        """检查是否穿过指定截面"""
        print(1)
