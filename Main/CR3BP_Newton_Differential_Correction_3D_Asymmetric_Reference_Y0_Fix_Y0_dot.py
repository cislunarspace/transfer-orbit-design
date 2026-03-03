import copy

import numpy as np

from Dynamics.CR3BP_Dynamics import CR3BP_Propagation_42, CR3BP_Dynamics


def CR3BP_Newton_Differential_Correction_3D_Asymmetric_Reference_Y0_Fix_Y0_dot(
    SV0_initial, tf_initial, tol, N, maxiter
):
    """
    定义非对称微分修正方法，利用牛顿迭代法修正周期轨道初值，固定y0_dot，修正x0,y0和x0_dot（适用于L4,L5点vertical轨道）
          输入为待修正的轨道位置速度向量初值与周期的猜测值，容差，完整周期的离散点个数，最大迭代次数。
          输出为修正后的轨道位置速度向量初值与周期。
          轨道未修正初值取为 SV0 = [x0  y0  z0  x0_dot  y0_dot z0_dot],（各项均不为0），待修正周期为tf。
          修正量形式为 delta_SV0 = [delta_x0  0  delta_z0  delta_x0_dot  delta_y0_dot  delta_z0_dot]
    """

    # 定义修正变量为x0, z0, x0_dot, y0_dot, z0_dot,tf, 将待修正的位置速度初值和轨道周期代入
    SV0 = copy.deepcopy(SV0_initial)
    tf = tf_initial

    X_Variable = np.empty(5)

    X_Variable[0] = SV0[0]
    X_Variable[1] = SV0[2]
    X_Variable[2] = SV0[3]
    X_Variable[3] = SV0[4]
    X_Variable[4] = SV0[5]

    # 迭代次数
    count = 0

    while True:
        print("当前迭代次数" + str(count))
        if count > maxiter:
            print("达到最大迭代次数")
            break
        print("当前修正变量" + str(X_Variable))

        # 将（迭代后的）变量赋值给位置速度向量初值和周期（积分时间）
        SV0[0] = X_Variable[0]
        SV0[2] = X_Variable[1]
        SV0[3] = X_Variable[2]
        SV0[4] = X_Variable[3]
        SV0[5] = X_Variable[4]

        # 将该轨道初值放在圆型限制性三体模型中进行数值积分，积分时间为tf
        CR3BP_t, CR3BP_State, CR3BP_SV, CR3BP_STM = CR3BP_Propagation_42(SV0, tf, N)

        # 获取积分终点的位置速度向量和状态转移矩阵
        CR3BP_t = CR3BP_t[-1]
        CR3BP_SV = CR3BP_SV[:, -1]
        CR3BP_STM = CR3BP_STM[-1, :, :]

        # 求解积分终点状态向量一阶导
        CR3BP_dot_SV = CR3BP_Dynamics.CR3BP_Dynamics(CR3BP_t, CR3BP_SV)

        # 定义约束条件向量为积分终点的delta_x,delta_z,delta_x_dot,delta_y_dot,delta_z_dot
        X_Constraint = np.empty(4)

        X_Constraint[0] = CR3BP_SV[0] - SV0[0]
        X_Constraint[1] = CR3BP_SV[2] - SV0[2]
        X_Constraint[2] = CR3BP_SV[3] - SV0[3]
        X_Constraint[3] = CR3BP_SV[5] - SV0[5]

        print("当前约束变量" + str(X_Constraint))

        # 计算Q矩阵
        # 调整后的状态转移矩阵（x,z,x_dot,z_dot对除y0的其他元素的偏导）
        CR3BP_STM_1 = np.delete(CR3BP_STM, [1, 4], axis=0)
        CR3BP_STM_1 = np.delete(CR3BP_STM_1, 1, axis=1)
        CR3BP_STM_2 = CR3BP_STM[1, :]
        CR3BP_STM_2 = np.delete(CR3BP_STM_2, 1)

        # 调整后的状态向量一阶导,第一部分为y_dot, 第二部分为x_dot,z_dot,x_ddot,y_ddot, z_ddot
        CR3BP_dot_SV_1 = CR3BP_dot_SV[1]
        CR3BP_dot_SV_2 = np.delete(CR3BP_dot_SV, [1, 4])
        Q = CR3BP_STM_1 - 1 / CR3BP_dot_SV_1 * np.outer(CR3BP_dot_SV_2, CR3BP_STM_2.T)

        # 定义微分校正系数矩阵
        dX_Constraint = Q

        dX_Constraint[0, 0] = Q[0, 0] - 1
        dX_Constraint[1, 1] = Q[1, 1] - 1
        dX_Constraint[2, 2] = Q[2, 2] - 1
        dX_Constraint[3, 4] = Q[3, 4] - 1

        dX_Constraint = np.matmul(
            dX_Constraint.T, np.linalg.inv(np.matmul(dX_Constraint, dX_Constraint.T))
        )

        # 定义变量x0, z0, x0_dot, y0_dot, z0_dot的修正量
        delta_X_Variable = np.matmul(dX_Constraint, X_Constraint)

        # 修正后的变量
        X_Variable_New = X_Variable - delta_X_Variable

        # 判断此时的约束向量是否满足条件,若满足条件则退出循环
        if np.linalg.norm(X_Constraint - np.zeros(4)) < tol:
            print(str(count) + "次迭代后完成微分修正")
            break

        X_Variable = X_Variable_New

        count += 1

    # 将修正后的变量重新赋值给位置速度向量以及周期
    SV0[0] = X_Variable[0]
    SV0[2] = X_Variable[1]
    SV0[3] = X_Variable[2]
    SV0[4] = X_Variable[3]
    SV0[5] = X_Variable[4]
    SV0_corrected = SV0
    # 未对周期tf进行修正，仍为初始猜测值
    tf_corrected = tf_initial

    print("修正后的轨道初值为" + str(SV0_corrected))
    print("修正后的轨道周期为" + str(tf_corrected))

    return SV0_corrected, tf_corrected
