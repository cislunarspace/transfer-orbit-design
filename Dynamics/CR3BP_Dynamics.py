# CR3BP_Dynamics.py

import numpy as np
from scipy import integrate

from Parameters.CR3BP_Parameters import get_CR3BP_EM_Constants


def CR3BP_Omega3_First_Partials(t, SV):
    """
    求圆型限制性三体模型等效势能对x,y,z一阶偏导
        输入为时间，位置速度向量。
        输出为等效势能一阶偏导组成的3*1向量dOmega3
    """

    # 确定系统相关常数
    mu = get_CR3BP_EM_Constants()

    # 航天器位置
    x = SV[0]
    y = SV[1]
    z = SV[2]

    # 定义航天器与两大天体之间的距离r1,r2,r3
    r1 = ((x + mu) ** 2 + y**2 + z**2) ** 0.5
    r2 = ((1.0 - x - mu) ** 2 + y**2 + z**2) ** 0.5

    # 定义圆型限制性三体模型等效势能
    Omega3 = (
        0.5 * (x**2 + y**2 + z**2) + (1.0 - mu) / r1 + mu / r2 + 0.5 * mu * (1.0 - mu)
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


def CR3BP_Omega3_Second_Partials(t, SV):
    """
    求圆型限制性三体模型等效势能对x,y,z二阶偏导（Hessian矩阵）
        输入为时间，位置速度向量。
        输出为等效势能二阶偏导组成的3*3Hessian矩阵ddOmega3。
    """

    # 确定系统相关常数
    mu = get_CR3BP_EM_Constants()

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
        3.0 * (1.0 - mu) * (x + mu) * y / r1**5 - 3.0 * mu * (1.0 - mu - x) * y / r2**5
    )
    ddOmega3_dxz = (
        3.0 * (1.0 - mu) * (x + mu) * z / r1**5 - 3.0 * mu * (1.0 - mu - x) * z / r2**5
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


def CR3BP_Dynamics(t, SV):
    """
    定义圆型限制性三体问题模型下航天器动力学方程
        输入为时间，位置速度向量。
        输出为位置速度向量对时间一阶导组成的6*1向量CR3BP_dot_SV。
    """

    # 获取圆型限制性三体问题模型等效势能一阶导
    dOmega3 = CR3BP_Omega3_First_Partials(t, SV)

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


def get_CR3BP_A(t, SV):
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
    ddOmega3 = CR3BP_Omega3_Second_Partials(t, SV)

    # Jacobi矩阵A(t)
    CR3BP_A = np.empty((6, 6))

    CR3BP_A[0:3, 0:3] = O
    CR3BP_A[0:3, 3:6] = I
    CR3BP_A[3:6, 0:3] = ddOmega3
    CR3BP_A[3:6, 3:6] = K

    return CR3BP_A


def get_CR3BP_dot_STM(t, SV, CR3BP_STM):
    """
    定义状态转移矩阵一阶导
        输入为时间，位置速度向量。
        输出为状态转移矩阵对时间一阶导CR3BP_dot_STM。
    """

    # 获取Jacobi矩阵
    CR3BP_A = get_CR3BP_A(t, SV)

    # 状态转移矩阵一阶导
    CR3BP_dot_STM = np.matmul(CR3BP_A, CR3BP_STM)

    return CR3BP_dot_STM


def CR3BP_Dynamics_42(t, State):
    """
    定义圆型限制性三体问题模型下航天器42维状态向量动力学方程
        输入为时间，42维状态向量。
        输出为42维状态向量对时间的一阶导CR3BP_dot_State。
        42维状态向量前6项为航天器位置速度向量，后36项为状态转移矩阵。
    """

    # 当前位置速度向量
    CR3BP_SV = State[0:6]
    # 位置速度一阶导
    CR3BP_dot_SV = CR3BP_Dynamics(t, CR3BP_SV)

    # 当前状态转移矩阵
    CR3BP_phi = State[6:42].reshape((6, 6))
    # 状态转移矩阵一阶导
    CR3BP_dot_phi = get_CR3BP_dot_STM(t, CR3BP_SV, CR3BP_phi)

    # 42维状态向量一阶导
    CR3BP_dot_State = np.concatenate((CR3BP_dot_SV, CR3BP_dot_phi.reshape(36)))

    return CR3BP_dot_State


def CR3BP_Propagation(SV0, tf, N):
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
        CR3BP_Dynamics,
        [CR3BP_t[0], CR3BP_t[-1]],
        SV0,
        method="DOP853",
        t_eval=CR3BP_t,
        rtol=10e-18,
        atol=10e-18,
    )

    CR3BP_SV = output.y

    return CR3BP_t, CR3BP_SV


def CR3BP_Propagation_42(SV0, tf, N):
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
        CR3BP_Dynamics_42,
        [CR3BP_t[0], CR3BP_t[-1]],
        State_0,
        method="DOP853",
        t_eval=CR3BP_t,
        rtol=10e-18,
        atol=10e-18,
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


if __name__ == "__main__":
    SV0 = [0.766448755485714, 0, 0, 0, 0.573665890385585, 0]
    tf = 3.928904348489625
    SV0 = [0.005304, 0, 0, 0, 10.58802, 0]
    tf = 6.307498
    tol = 1e-6
    N = 10000
    t = np.linspace(0, tf, N)

    tf_half = 0.5 * tf
    CR3BP_t, CR3BP_State, CR3BP_SV, CR3BP_STM = CR3BP_Propagation_42(SV0, tf_half, N)
