import copy

import numpy as np

from Dynamics.CR3BP_Dynamics import CR3BP_Propagation_42, CR3BP_Dynamics


def CR3BP_Newton_Differential_Correction_3D_Symmetric_XZ_Correct_All(
    SV0_initial, tf_initial, tol, N, maxiter
):
    """
    定义微分修正方法，利用牛顿迭代法修正关于xz平面对称的周期轨道初值，同时修正x0,z0,y0_dot和周期T（适用于Halo轨道，Vertical轨道）
        输入为待修正的轨道位置速度向量初值与周期的猜测值，容差，完整周期的离散点个数，最大迭代次数。
        输出为修正后的轨道位置速度向量初值与周期。
        轨道未修正初值取为 SV0 = [x0  0  z0  0  y0_dot  0],待修正周期为tf，
        积分tf/2后，若轨道状态第一次回到xz平面(即y=0)，且x_dot=0,z_dot=0则得到轨道的一半，计算完毕；
        否则对初值SV0和周期T进行修正。
    """

    # 定义修正变量为x0, z0, y0_dot, tf_half,将待修正的位置速度初值和轨道周期的一半代入
    SV0 = copy.deepcopy(SV0_initial)
    tf = tf_initial
    tf_half = 0.5 * tf

    X_Variable = np.empty(4)

    X_Variable[0] = SV0[0]
    X_Variable[1] = SV0[2]
    X_Variable[2] = SV0[4]
    X_Variable[3] = tf_half

    # 迭代次数
    count = 0

    while True:
        print("当前迭代次数" + str(count))
        if count > maxiter:
            print("达到最大迭代次数")
            break
        print("当前修正变量" + str(X_Variable))

        # 将（迭代后的）变量赋值给位置速度向量初值和半周期（积分时间）
        SV0[0] = X_Variable[0]
        SV0[2] = X_Variable[1]
        SV0[4] = X_Variable[2]
        tf_half = X_Variable[3]

        # 将该轨道初值放在圆型限制性三体模型中进行数值积分，积分时间为tf_half
        CR3BP_t, CR3BP_State, CR3BP_SV, CR3BP_STM = CR3BP_Propagation_42(
            SV0, tf_half, N
        )

        # 获取积分终点的位置速度向量和状态转移矩阵
        CR3BP_t = CR3BP_t[-1]
        CR3BP_SV = CR3BP_SV[:, -1]
        CR3BP_STM = CR3BP_STM[-1, :, :]

        # 求解积分终点状态向量一阶导
        CR3BP_dot_SV = CR3BP_Dynamics(CR3BP_t, CR3BP_SV)

        # 定义约束条件向量为积分终点的y, x_dot, z_dot
        X_Constraint = np.empty(3)

        X_Constraint[0] = CR3BP_SV[1]
        X_Constraint[1] = CR3BP_SV[3]
        X_Constraint[2] = CR3BP_SV[5]

        print("当前约束变量" + str(X_Constraint))

        # 定义微分校正系数矩阵, dF = [[phi_21, phi_23, phi_25, y_dot],[phi_41, phi_43, phi_45, x_ddot],[phi_61, phi_63, phi_65, z_ddot]]
        dX_Constraint = np.empty((3, 4))

        dX_Constraint[0, 0] = CR3BP_STM[1, 0]
        dX_Constraint[0, 1] = CR3BP_STM[1, 2]
        dX_Constraint[0, 2] = CR3BP_STM[1, 4]
        dX_Constraint[0, 3] = CR3BP_dot_SV[1]

        dX_Constraint[1, 0] = CR3BP_STM[3, 0]
        dX_Constraint[1, 1] = CR3BP_STM[3, 2]
        dX_Constraint[1, 2] = CR3BP_STM[3, 4]
        dX_Constraint[1, 3] = CR3BP_dot_SV[3]

        dX_Constraint[2, 0] = CR3BP_STM[5, 0]
        dX_Constraint[2, 1] = CR3BP_STM[5, 2]
        dX_Constraint[2, 2] = CR3BP_STM[5, 4]
        dX_Constraint[2, 3] = CR3BP_dot_SV[5]

        dX_Constraint = np.matmul(
            dX_Constraint.T, np.linalg.inv(np.matmul(dX_Constraint, dX_Constraint.T))
        )

        # 定义变量x0, z0, y0_dot, tf_half的修正量
        delta_X_Variable = np.matmul(dX_Constraint, X_Constraint)

        # 修正后的变量
        X_Variable_New = X_Variable - delta_X_Variable

        # 判断此时的约束向量是否满足条件,若满足条件则退出循环
        if np.linalg.norm(X_Constraint - np.zeros(3)) < tol:
            print(str(count) + "次迭代后完成微分修正")
            break
        # else:
        #     continue

        X_Variable = X_Variable_New

        count += 1

    # 将修正后的变量重新赋值给位置速度向量以及半周期
    SV0[0] = X_Variable[0]
    SV0[2] = X_Variable[1]
    SV0[4] = X_Variable[2]
    SV0_corrected = SV0
    tf_half_corrected = X_Variable[3]
    tf_corrected = 2 * tf_half_corrected

    print("修正后的轨道初值为" + str(SV0_corrected))
    print("修正后的轨道周期为" + str(tf_corrected))

    return SV0_corrected, tf_corrected
