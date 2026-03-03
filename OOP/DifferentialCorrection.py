import numpy as np
import matplotlib.pyplot as plt
from scipy import integrate


class DifferentialCorrection:
    """微分修正算法

    属性：
    - dynamics: CR3BP_Dynamics对象
    - target_conditions: 目标约束条件
    - free_variables: 自由变量
    - tolerance: 收敛容差
    - max_iterations: 最大迭代次数
    - convergence_history: 收敛历史

    方法：
    - __init__(dynamics, target, free_vars): 初始化修正器
    - setup_2D_symmetric_x_fixed_x0(): 配置2D对称X固定X0
    - setup_2D_symmetric_x_fixed_t(): 配置2D对称X固定周期
    - setup_3D_symmetric_x_fixed_x0(): 配置3D对称X固定X0
    - setup_3D_symmetric_xz_fixed_x0(): 配置3D对称XZ固定X0
    - setup_3D_symmetric_xz_fixed_z0(): 配置3D对称XZ固定Z0
    - compute_state_transition_matrix(initial_state, t): 计算STM
    - compute_constraint_vector(state): 计算约束向量
    - compute_correction_matrix(): 计算修正矩阵
    - iterate_correction(initial_guess): 迭代修正
    - check_convergence(): 检查收敛性
    - plot_convergence_history(): 绘制收敛历史
    """

    # 类属性
    DEFAULT_TOLERANCE = 1e-12  # 默认收敛容差
    DEFAULT_MAX_ITERATIONS = 50  # 默认最大迭代次数
    DEFAULT_DAMPING_FACTOR = 1.0  # 默认阻尼因子
    VALID_SETUP_TYPES = [
        "2D_symmetric_x_fixed_x0",
        "2D_symmetric_x_fixed_t",
        "3D_symmetric_x_fixed_x0",
        "3D_symmetric_xz_fixed_x0",
        "3D_symmetric_xz_fixed_z0",
    ]

    def __init__(self, dynamics, target, free_vars):
        """初始化修正器

        参数：
        - dynamics: CR3BP_Dynamics对象
        - target: 目标约束条件字典
        - free_vars: 自由变量列表
        """
        # 核心对象
        self.dynamics = dynamics  # 动力学系统
        self.target_conditions = target  # 目标约束条件
        self.free_variables = free_vars  # 自由变量

        # 收敛控制参数
        self.tolerance = self.DEFAULT_TOLERANCE  # 收敛容差
        self.max_iterations = self.DEFAULT_MAX_ITERATIONS  # 最大迭代次数
        self.damping_factor = self.DEFAULT_DAMPING_FACTOR  # 阻尼因子
        self.use_adaptive_damping = True  # 是否使用自适应阻尼
        self.min_damping = 0.1  # 最小阻尼因子
        self.max_damping = 2.0  # 最大阻尼因子

        # 收敛历史记录
        self.convergence_history = []  # 收敛历史列表
        self.error_history = []  # 误差历史
        self.correction_history = []  # 修正量历史
        self.iteration_count = 0  # 当前迭代次数
        self.converged = False  # 是否已收敛

        # 当前状态
        self.current_state = None  # 当前状态向量
        self.current_time = None  # 当前时间
        self.current_constraints = None  # 当前约束值
        self.current_error = None  # 当前误差

        # 初始猜测
        self.initial_guess = None  # 初始猜测
        self.final_solution = None  # 最终解
        self.solution_time = None  # 解对应的时间

        # 雅可比矩阵和修正矩阵
        self.jacobian_matrix = None  # 雅可比矩阵
        self.correction_matrix = None  # 修正矩阵
        self.pseudoinverse_matrix = None  # 伪逆矩阵
        self.sensitivity_matrix = None  # 灵敏度矩阵

        # 约束设置
        self.constraint_indices = []  # 约束索引
        self.constraint_weights = {}  # 约束权重
        self.constraint_types = {}  # 约束类型
        self.free_variable_indices = []  # 自由变量索引

        # 配置类型
        self.setup_type = None  # 当前配置类型
        self.symmetry_condition = None  # 对称条件
        self.fixed_parameters = {}  # 固定参数

        # 数值微分设置
        self.use_analytic_stm = True  # 是否使用解析STM
        self.finite_difference_step = 1e-7  # 有限差分步长
        self.finite_difference_method = "central"  # 差分方法

        # 迭代控制
        self.stagnation_limit = 1e-14  # 停滞限制
        self.divergence_limit = 1e10  # 发散限制
        self.step_size_limit = 1.0  # 步长限制

        # 收敛历史详情
        self.history_details = {
            "iterations": [],  # 迭代次数
            "errors": [],  # 误差
            "corrections": [],  # 修正量
            "states": [],  # 状态历史
            "times": [],  # 时间历史
            "jacobians": [],  # 雅可比矩阵历史
            "damping_factors": [],  # 阻尼因子历史
        }

        # 性能统计
        self.performance_stats = {
            "total_time": 0.0,  # 总耗时
            "stm_evaluations": 0,  # STM评估次数
            "constraint_evaluations": 0,  # 约束评估次数
            "jacobian_evaluations": 0,  # 雅可比评估次数
        }

        # 终止条件
        self.termination_reason = None  # 终止原因
        self.success = False  # 是否成功

        # 验证输入
        self._validate_inputs()

    def _validate_inputs(self):
        """验证输入参数"""
        if not isinstance(self.target_conditions, dict):
            raise ValueError("目标约束条件必须是字典类型")
        if not isinstance(self.free_variables, (list, tuple)):
            raise ValueError("自由变量必须是列表或元组")

    def setup_2D_symmetric_x_fixed_x0(self, x0):
        """配置平面问题中固定初始x坐标的对称周期轨道搜索

        在平面圆形限制性三体问题（PCRTBP）模型中，动力学方程关于会合坐标系的x轴具有对称性。
        利用这一性质，周期轨道的搜索可以简化为寻找合适的初始条件：
        从x轴上一点垂直出发（y=0, x_dot=0），经过半周期T/2后再次垂直穿越x轴（y=0, x_dot=0）。

        本函数针对这种对称性设置微分修正问题，固定初始x坐标x0，将初始y方向速度y_dot0
        和半周期T/2作为自由变量进行调整，以满足终点处的垂直穿越条件。

        参数:
            x0 (float): 固定的初始x坐标，轨道从点(x0, 0)垂直出发

        返回:
            self: 返回配置好的微分修正器实例

        配置说明:
            - 自由变量: [y_dot0, T_half] - 初始y方向速度和半周期时间
            - 目标约束: [y(T/2)=0, x_dot(T/2)=0] - 终点处再次垂直穿越x轴
            - 状态向量索引: [1, 3] 分别对应y坐标和x方向速度

        应用场景:
            此配置对应于Broucke(1968)等经典文献中寻找对称周期轨道的基本方法，
            可用于生成围绕平动点或主天体的各类周期轨道家族。

        参考文献：
            [1] Broucke R A. Periodic orbits in the restricted three body problem with Earth-moon masses[R]. 1968.
        """
        # 设置配置类型
        self.setup_type = "2D_symmetric_x_fixed_x0"
        self.symmetry_condition = "x_axis"
        self.fixed_parameters = {"x0": x0}

        # 定义自由变量
        # 在2D对称x轴的情况下，从x轴垂直出发的初始条件为: [x0, 0, 0, y_dot]
        # 自由变量是初始y方向速度 y_dot 和飞行时间 T/2
        self.free_variables = ["y_dot0", "T_half"]
        self.free_variable_indices = [
            3,
            4,
        ]  # 状态向量中索引3是y_dot，索引4是时间（作为变量）

        # 定义目标约束条件
        # 对于对称x轴的周期轨道，在半周期处应满足：y(T/2)=0, x_dot(T/2)=0
        # 即轨道再次垂直穿越x轴
        self.target_conditions = {
            "y": 0.0,  # 终点y坐标为0
            "x_dot": 0.0,  # 终点x方向速度为0
        }

        # 设置约束索引
        # 状态向量为 [x, y, z, x_dot, y_dot, z_dot]
        self.constraint_indices = [1, 3]  # y和x_dot在状态向量中的索引

        # 设置约束权重（可选，用于加权最小二乘）
        self.constraint_weights = {"y": 1.0, "x_dot": 1.0}

        # 设置约束类型
        self.constraint_types = {"y": "equality", "x_dot": "equality"}

        # 更新固定参数到目标条件中（可选）
        self.fixed_parameters.update({"x0": x0})

        # 重置收敛历史
        self.convergence_history = []
        self.error_history = []

        print(
            f"2D对称x轴配置完成：固定x0={x0}，自由变量={self.free_variables}，目标约束={list(self.target_conditions.keys())}"
        )

        return self

    def setup_2D_symmetric_x_fixed_t(self):
        """配置2D对称X固定周期"""
        print(1)

    def setup_3D_symmetric_x_fixed_x0(self):
        """配置3D对称X固定X0"""
        print(1)

    def setup_3D_symmetric_xz_fixed_x0(self):
        """配置3D对称XZ固定X0"""
        print(1)

    def setup_3D_symmetric_xz_fixed_z0(self):
        """配置3D对称XZ固定Z0"""
        print(1)

    def compute_constraint_vector(self, state):
        """计算约束向量"""
        print(1)

    def compute_correction_matrix(self):
        """计算修正矩阵"""
        print(1)

    def iterate_correction(self, initial_guess):
        """迭代修正主算法

        通过迭代调整自由变量，使终点状态满足目标约束条件，从而找到精确的周期轨道。

        参数:
            initial_guess (Orbit): 初始猜测轨道，包含初始状态和时间信息

        返回:
            Orbit: 修正后的精确周期轨道

        算法步骤:
            1. 从初始猜测出发，积分到当前估计的半周期时间
            2. 计算终点状态与目标约束的误差
            3. 如果误差小于容差，收敛成功
            4. 否则，使用有限差分法计算状态转移矩阵，构建雅可比矩阵
            5. 求解线性系统得到自由变量的修正量
            6. 更新自由变量（初始y_dot和半周期时间）
            7. 重复直到收敛或达到最大迭代次数
        """
        # 保存初始猜测
        self.initial_guess = initial_guess
        self.iteration_count = 0
        self.converged = False

        # 从初始猜测中提取初始状态和时间
        current_state = initial_guess.states[
            0
        ].copy()  # 初始状态 [x, y, z, x_dot, y_dot, z_dot]
        current_time = initial_guess.period / 2  # 初始猜测的半周期时间 T_half

        print(f"\n{'=' * 60}")
        print(f"开始微分修正迭代...")
        print(f"{'=' * 60}")
        print(
            f"初始状态: x={current_state[0]:.6f}, y={current_state[1]:.6f}, z={current_state[2]:.6f}"
        )
        print(
            f"         x_dot={current_state[3]:.6f}, y_dot={current_state[4]:.6f}, z_dot={current_state[5]:.6f}"
        )
        print(f"初始半周期: T/2={current_time:.6f}")
        print(f"{'=' * 60}")

        # 迭代循环
        for iteration in range(self.max_iterations):
            self.iteration_count = iteration + 1

            # 1. 积分当前轨道到半周期时间（仅6维状态）
            try:
                # 使用6维传播获取终点状态
                t_span = (0, current_time)
                t_eval = np.linspace(0, current_time, 1000)  # 内部积分点

                # 直接调用solve_ivp进行6维状态积分
                output = integrate.solve_ivp(
                    self.dynamics.CR3BP_Dynamics,  # 6维动力学方程
                    t_span,
                    current_state,
                    method="RK45",
                    t_eval=t_eval,
                    rtol=1e-6,
                    atol=1e-6,
                )

                if not output.success:
                    print(f"  积分失败: {output.message}")
                    self.termination_reason = f"积分失败: {output.message}"
                    return None

                # 获取终点状态
                final_state = output.y[:, -1]

                self.performance_stats["stm_evaluations"] += 1

            except Exception as e:
                print(f"  积分失败: {e}")
                self.termination_reason = f"积分失败: {e}"
                return None

            # 2. 计算当前终点状态的约束值
            current_constraints = []
            target_values = []

            for i, constraint_idx in enumerate(self.constraint_indices):
                # 约束值来自终点状态
                constraint_value = final_state[constraint_idx]
                current_constraints.append(constraint_value)

                # 目标值从target_conditions获取
                if constraint_idx == 1:  # y坐标
                    target_values.append(self.target_conditions["y"])
                elif constraint_idx == 3:  # x_dot
                    target_values.append(self.target_conditions["x_dot"])
                # 可根据需要添加其他约束

            current_constraints = np.array(current_constraints)
            target_values = np.array(target_values)

            # 计算误差向量
            error_vector = current_constraints - target_values
            current_error = np.linalg.norm(error_vector)

            # 保存历史
            self.error_history.append(current_error)
            self.convergence_history.append(
                {
                    "iteration": iteration,
                    "error": current_error,
                    "state": current_state.copy(),
                    "time": current_time,
                    "constraints": current_constraints.copy(),
                    "final_state": final_state.copy(),
                }
            )

            # 3. 检查收敛
            if current_error < self.tolerance:
                self.converged = True
                self.termination_reason = "收敛成功：误差小于容差"
                print(
                    f"\n✓ 迭代 {iteration + 1} 收敛成功！最终误差: {current_error:.2e}"
                )
                break

            # 4. 检查发散
            if current_error > self.divergence_limit:
                self.termination_reason = "发散：误差超过限制"
                print(f"\n✗ 警告：迭代发散，误差 = {current_error:.2e}")
                break

            # 5. 使用有限差分法计算状态转移矩阵和雅可比矩阵
            n_constraints = len(self.constraint_indices)
            n_variables = len(self.free_variable_indices)
            self.jacobian_matrix = np.zeros((n_constraints, n_variables))

            # 有限差分步长
            eps = self.finite_difference_step

            # 对每个自由变量计算敏感性
            for j, var_idx in enumerate(self.free_variable_indices):
                if var_idx < 6:  # 对初始状态的敏感性
                    # 创建扰动的初始状态
                    state_perturbed = current_state.copy()

                    # 正向扰动
                    state_perturbed[var_idx] += eps
                    output_pert_fwd = integrate.solve_ivp(
                        self.dynamics.CR3BP_Dynamics,
                        t_span,
                        state_perturbed,
                        method="DOP853",
                        t_eval=[current_time],  # 只积分到终点时间
                        rtol=1e-12,
                        atol=1e-12,
                    )
                    final_pert_fwd = output_pert_fwd.y[:, -1]

                    # 负向扰动
                    state_perturbed[var_idx] -= 2 * eps
                    output_pert_bwd = integrate.solve_ivp(
                        self.dynamics.CR3BP_Dynamics,
                        t_span,
                        state_perturbed,
                        method="DOP853",
                        t_eval=[current_time],
                        rtol=1e-12,
                        atol=1e-12,
                    )
                    final_pert_bwd = output_pert_bwd.y[:, -1]

                    # 中心差分计算 ∂(终点状态)/∂(初始状态)
                    sensitivity = (final_pert_fwd - final_pert_bwd) / (2 * eps)

                    # 提取所需约束的敏感性
                    for i, constraint_idx in enumerate(self.constraint_indices):
                        self.jacobian_matrix[i, j] = sensitivity[constraint_idx]

                elif var_idx == 6:  # 对时间的敏感性
                    # 对时间的有限差分
                    time_perturbed = current_time + eps
                    output_time_fwd = integrate.solve_ivp(
                        self.dynamics.CR3BP_Dynamics,
                        (0, time_perturbed),
                        current_state,
                        method="DOP853",
                        t_eval=[time_perturbed],
                        rtol=1e-12,
                        atol=1e-12,
                    )
                    final_time_fwd = output_time_fwd.y[:, -1]

                    time_perturbed = current_time - eps
                    output_time_bwd = integrate.solve_ivp(
                        self.dynamics.CR3BP_Dynamics,
                        (0, time_perturbed),
                        current_state,
                        method="DOP853",
                        t_eval=[time_perturbed],
                        rtol=1e-12,
                        atol=1e-12,
                    )
                    final_time_bwd = output_time_bwd.y[:, -1]

                    # 中心差分计算 ∂(终点状态)/∂(时间)
                    sensitivity_time = (final_time_fwd - final_time_bwd) / (2 * eps)

                    for i, constraint_idx in enumerate(self.constraint_indices):
                        self.jacobian_matrix[i, j] = sensitivity_time[constraint_idx]

            self.performance_stats["jacobian_evaluations"] += 1

            # 6. 计算修正量 (求解线性系统 J * Δ = -error_vector)
            try:
                # 使用伪逆求解，处理可能的奇异矩阵
                self.pseudoinverse_matrix = np.linalg.pinv(self.jacobian_matrix)
                correction = -self.pseudoinverse_matrix @ error_vector
            except np.linalg.LinAlgError:
                # 如果矩阵奇异，使用最小二乘
                correction = -np.linalg.lstsq(
                    self.jacobian_matrix, error_vector, rcond=None
                )[0]

            # 应用阻尼因子
            correction *= self.damping_factor

            # 检查步长是否过大
            correction_norm = np.linalg.norm(correction)
            if correction_norm > self.step_size_limit:
                correction = correction * (self.step_size_limit / correction_norm)
                print(f"  步长限制：修正量缩放至 {self.step_size_limit}")

            self.correction_history.append(correction_norm)

            # 7. 更新自由变量
            for j, var_idx in enumerate(self.free_variable_indices):
                if var_idx < 6:  # 更新状态变量
                    current_state[var_idx] += correction[j]
                elif var_idx == 6:  # 更新时间变量
                    current_time += correction[j]

            # 确保时间正数
            if current_time <= 0:
                current_time = 1e-6
                print("  警告：时间调整为正值")

            # 8. 自适应阻尼调整（可选）
            if self.use_adaptive_damping and iteration > 0:
                if correction_norm < self.stagnation_limit:
                    # 停滞时增加阻尼
                    self.damping_factor = min(
                        self.damping_factor * 1.5, self.max_damping
                    )
                elif correction_norm > 1.0:
                    # 发散时减小阻尼
                    self.damping_factor = max(
                        self.damping_factor * 0.5, self.min_damping
                    )

            # 打印迭代信息
            print(f"\n迭代 {iteration + 1}:")
            print(f"  误差范数 = {current_error:.2e}")
            print(
                f"  约束值: {dict(zip([f'c{i}' for i in self.constraint_indices], current_constraints))}"
            )
            print(f"  修正量: Δ{self.free_variables} = {correction}")
            print(f"  新状态: x={current_state[0]:.6f}, y_dot={current_state[4]:.6f}")
            print(f"  新半周期: T/2={current_time:.6f}")

            # 检查停滞
            if correction_norm < self.stagnation_limit:
                self.termination_reason = "停滞：修正量过小"
                print(f"  停滞：修正量 = {correction_norm:.2e}")
                break

        # 迭代结束，处理结果
        if self.converged:
            self.success = True
            self.final_solution = current_state.copy()
            self.solution_time = current_time

            # 构建最终轨道
            # 积分完整周期 (2 * T_half) 获得完整的周期轨道
            full_period = 2 * current_time
            n_points = 1000

            # 使用CR3BP_Propagation进行完整周期积分
            CR3BP_t, CR3BP_SV = self.dynamics.CR3BP_Propagation(
                current_state, full_period, n_points
            )

            # 创建轨道对象
            from OOP.Orbit import Orbit

            corrected_orbit = Orbit(
                states=CR3BP_SV.T, times=CR3BP_t  # 转置为 (n_points, 6) 格式
            )

            print(f"\n{'=' * 60}")
            print(f"✓ 微分修正成功完成")
            print(f"{'=' * 60}")
            print(f"  最终周期: T = {full_period:.6f}")
            print(f"  最终误差: {current_error:.2e}")
            # print(f"  最终Jacobi常数: {self.dynamics.compute_jacobi_constant(current_state):.6f}")
            print(f"{'=' * 60}")

            return corrected_orbit
        else:
            print(f"\n✗ 微分修正失败: {self.termination_reason}")
            return None

        # 迭代结束，处理结果
        if self.converged:
            self.success = True
            self.final_solution = current_state.copy()
            self.solution_time = current_time

            # 构建最终轨道
            # 积分完整周期 (2 * T_half) 获得完整的周期轨道
            full_period = 2 * current_time
            n_points = 1000

            # 使用CR3BP_Propagation进行完整周期积分
            CR3BP_t, CR3BP_SV = self.dynamics.CR3BP_Propagation(
                current_state, full_period, n_points
            )

            # 创建轨道对象
            from OOP.Orbit import Orbit

            corrected_orbit = Orbit(
                states=CR3BP_SV.T, times=CR3BP_t  # 转置为 (n_points, 6) 格式
            )

            print(f"\n{'=' * 60}")
            print(f"✓ 微分修正成功完成")
            print(f"{'=' * 60}")
            print(f"  最终周期: T = {full_period:.6f}")
            print(f"  最终误差: {current_error:.2e}")
            print(
                f"  最终Jacobi常数: {self.dynamics.compute_jacobi_constant(current_state):.6f}"
            )
            print(f"{'=' * 60}")

            return corrected_orbit
        else:
            print(f"\n✗ 微分修正失败: {self.termination_reason}")
            return None

    def check_convergence(self):
        """检查收敛性"""
        print(1)

    def plot_convergence_history(self):
        """绘制收敛历史"""
        print(1)
