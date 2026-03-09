# -*- coding: utf-8 -*-
"""
CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_X0.py

利用牛顿微分修正法，计算圆型限制性三体问题（CR3BP）中关于x轴对称的二维周期轨道。
适用于Lyapunov轨道、DRO等具有x轴对称性的平面周期轨道。

轨道初值形式固定为：[x0, 0, 0, 0, y0_dot, 0]，即从x轴上出发，y=0, z=0, x_dot=0, z_dot=0。
通过修正y0_dot和轨道周期T，使得积分半个周期后满足：y = 0 且 x_dot = 0，
从而保证轨道闭合且关于x轴对称。
"""

import copy
import numpy as np

from Dynamics.CR3BP_Dynamics import CR3BP_Propagation_42, CR3BP_Dynamics


def CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_X0(
    SV0_initial, tf_initial, tol, N, maxiter
):
    """
    使用牛顿微分修正法求解x轴对称的二维周期轨道。

    参数:
        SV0_initial : 初始状态向量 [x, y, z, x_dot, y_dot, z_dot]，其中 y=z=x_dot=z_dot=0
        tf_initial  : 初始猜测的轨道周期
        tol         : 收敛容差（约束残差的范数）
        N           : 积分时的时间步数（用于数值传播）
        maxiter     : 最大迭代次数

    返回:
        SV0_corrected : 修正后的初始状态向量
        tf_corrected  : 修正后的轨道周期
    """
    # 深拷贝初始状态，避免修改原始输入
    SV0 = copy.deepcopy(SV0_initial)
    tf_half = 0.5 * tf_initial

    # 待修正变量：[y0_dot, tf_half]
    X_Variable = np.array([SV0[4], tf_half])

    count = 0
    while True:
        print("当前迭代次数: " + str(count))
        if count > maxiter:
            print("达到最大迭代次数，未收敛。")
            break

        print("当前修正变量 (y0_dot, tf_half): " + str(X_Variable))

        # 更新待修正变量
        SV0[4] = X_Variable[0]
        tf_half = X_Variable[1]

        # 在CR3BP中积分半个周期，同时获取状态转移矩阵（STM）
        CR3BP_t, _, CR3BP_SV, CR3BP_STM = CR3BP_Propagation_42(SV0, tf_half, N)

        # 提取积分终点的状态和STM
        final_state = CR3BP_SV[:, -1]
        final_STM = CR3BP_STM[-1, :, :]

        # 计算终点处的状态导数（即加速度和速度导数）
        state_derivative = CR3BP_Dynamics(CR3BP_t[-1], final_state)

        # 定义约束条件：y = 0, x_dot = 0
        constraint = np.array([final_state[1], final_state[3]])
        print("当前约束残差 (y, x_dot): " + str(constraint))

        # 检查是否满足收敛条件
        if np.linalg.norm(constraint) < tol:
            print(f"{count}次迭代后完成微分修正，满足容差要求。")
            break

        # 构建雅可比矩阵 d(constraint)/d(variables)
        # 变量顺序：[y0_dot, tf_half]
        # STM[i, j] 表示终点第i个状态对初值第j个分量的偏导
        J = np.empty((2, 2))
        J[0, 0] = final_STM[1, 4]  # ∂y/∂(y0_dot)
        J[0, 1] = state_derivative[1]  # ∂y/∂t = y_dot
        J[1, 0] = final_STM[3, 4]  # ∂(x_dot)/∂(y0_dot)
        J[1, 1] = state_derivative[3]  # ∂(x_dot)/∂t = x_ddot

        # 求解牛顿修正量：J * delta = constraint  =>  delta = J^{-1} * constraint
        try:
            delta = np.linalg.solve(J, constraint)
        except np.linalg.LinAlgError:
            print("雅可比矩阵奇异，无法求解修正量。")
            break

        # 牛顿更新：X_new = X_old - J^{-1} * F
        X_Variable = X_Variable - delta
        count += 1

    # 构造最终结果
    SV0[4] = X_Variable[0]
    SV0_corrected = SV0
    tf_corrected = 2.0 * X_Variable[1]

    print("修正后的轨道初值为: " + str(SV0_corrected))
    print("修正后的轨道周期为: " + str(tf_corrected))

    return SV0_corrected, tf_corrected
