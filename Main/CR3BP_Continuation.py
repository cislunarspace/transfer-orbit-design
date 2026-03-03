# -*- coding: utf-8 -*-
"""
CR3BP_Continuation.py

通过微分修正与单参数延拓方法，生成圆型限制性三体问题（CR3BP）中的平面周期轨道族（如Lyapunov、DRO）。
支持以 x0 或 周期 T 为延拓参数，并可分析轨道族的稳定性特性。
"""

import copy
import numpy as np
import matplotlib.pyplot as plt

from CR3BP_DifferentialCorrection import CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_X0
from Main.CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_T import \
    CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_T
from Funcs.CR3BP_Stability import Compute_Monodromy_Matrix, Compute_Stability_Index
from Dynamics.CR3BP_Dynamics import CR3BP_Propagation


def CR3BP_Single_Parameter_Continuation_2D_X0(
        SV0_original, tf_original, beta, N_plus, N_minus
):
    """
    以 x0 为延拓参数，生成平面周期轨道族。

    参数:
        SV0_original : 原始周期轨道初值 [x0, 0, 0, 0, y0_dot, 0]
        tf_original  : 原始轨道周期
        beta         : 延拓步长（建议 ~1e-4）
        N_plus       : 正向延拓轨道数量（x0 增大方向）
        N_minus      : 负向延拓轨道数量（x0 减小方向）

    返回:
        SV0_Family_plus, tf_Family_plus     : 正向延拓部分
        SV0_Family_minus, tf_Family_minus   : 负向延拓部分
        SV0_Family, tf_Family               : 完整轨道族（含原始轨道）
    """
    # 初始化正向和负向延拓的当前状态
    SV0_plus = copy.deepcopy(SV0_original)
    tf_plus = tf_original
    SV0_minus = copy.deepcopy(SV0_original)
    tf_minus = tf_original

    # 存储轨道族
    SV0_Family_plus = np.empty(0)
    SV0_Family_minus = np.empty(0)
    tf_Family_plus = np.empty(N_plus)
    tf_Family_minus = np.empty(N_minus)

    # 微分修正参数
    tol = 1e-9
    N = 2000
    maxiter = 300

    # 正向延拓：x0 ← x0 + beta
    for i in range(N_plus):
        print(f"修正正向第 {i + 1} 条轨道")
        SV0_plus[0] += beta
        SV0_i, tf_i = CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_X0(
            SV0_plus, tf_plus, tol, N, maxiter
        )
        SV0_Family_plus = np.concatenate((SV0_Family_plus, SV0_i))
        tf_Family_plus[i] = tf_i
        SV0_plus, tf_plus = SV0_i, tf_i

    SV0_Family_plus = SV0_Family_plus.reshape(6, N_plus, order="F")

    # 负向延拓：x0 ← x0 - beta
    for j in range(N_minus):
        print(f"修正负向第 {j + 1} 条轨道")
        SV0_minus[0] -= beta
        SV0_j, tf_j = CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_X0(
            SV0_minus, tf_minus, tol, N, maxiter
        )
        SV0_Family_minus = np.concatenate((SV0_j, SV0_Family_minus))
        tf_Family_minus[-(j + 1)] = tf_j
        SV0_minus, tf_minus = SV0_j, tf_j

    SV0_Family_minus = SV0_Family_minus.reshape(6, N_minus, order="F")

    # 合并完整轨道族
    total_num = N_minus + N_plus + 1
    SV0_Family = np.empty((6, total_num))
    tf_Family = np.empty(total_num)

    SV0_Family[:, :N_minus] = SV0_Family_minus
    SV0_Family[:, N_minus] = SV0_original
    SV0_Family[:, N_minus + 1:] = SV0_Family_plus

    tf_Family[:N_minus] = tf_Family_minus
    tf_Family[N_minus] = tf_original
    tf_Family[N_minus + 1:] = tf_Family_plus

    return (
        SV0_Family_plus,
        tf_Family_plus,
        SV0_Family_minus,
        tf_Family_minus,
        SV0_Family,
        tf_Family,
    )


def CR3BP_Single_Parameter_Continuation_2D_T(
        SV0_original, tf_original, beta, N_plus, N_minus
):
    """
    以周期 T 为延拓参数，生成平面周期轨道族。

    参数:
        SV0_original : 原始周期轨道初值 [x0, 0, 0, 0, y0_dot, 0]
        tf_original  : 原始轨道周期
        beta         : 延拓步长（建议 ~1e-4）
        N_plus       : 正向延拓轨道数量（T 增大方向）
        N_minus      : 负向延拓轨道数量（T 减小方向）

    返回:
        SV0_Family_plus, tf_Family_plus     : 正向延拓部分
        SV0_Family_minus, tf_Family_minus   : 负向延拓部分
        SV0_Family, tf_Family               : 完整轨道族（含原始轨道）
    """
    # 初始化
    SV0_plus = copy.deepcopy(SV0_original)
    tf_plus = tf_original
    SV0_minus = copy.deepcopy(SV0_original)
    tf_minus = tf_original

    SV0_Family_plus = np.empty(0)
    SV0_Family_minus = np.empty(0)
    tf_Family_plus = np.empty(N_plus)
    tf_Family_minus = np.empty(N_minus)

    # 微分修正参数
    tol = 1e-9
    N = 10000
    maxiter = 300

    # 正向延拓：T ← T + beta
    for i in range(N_plus):
        print(f"修正正向第 {i + 1} 条轨道")
        tf_plus += beta
        SV0_i, tf_i = CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_T(
            SV0_plus, tf_plus, tol, N, maxiter
        )
        SV0_Family_plus = np.concatenate((SV0_Family_plus, SV0_i))
        tf_Family_plus[i] = tf_i
        SV0_plus, tf_plus = SV0_i, tf_i

    SV0_Family_plus = SV0_Family_plus.reshape(6, N_plus, order="F")

    # 负向延拓：T ← T - beta
    for j in range(N_minus):
        print(f"修正负向第 {j + 1} 条轨道")
        tf_minus -= beta
        SV0_j, tf_j = CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_T(
            SV0_minus, tf_minus, tol, N, maxiter
        )
        SV0_Family_minus = np.concatenate((SV0_j, SV0_Family_minus))
        tf_Family_minus[-(j + 1)] = tf_j
        SV0_minus, tf_minus = SV0_j, tf_j

    SV0_Family_minus = SV0_Family_minus.reshape(6, N_minus, order="F")

    # 合并完整轨道族
    total_num = N_minus + N_plus + 1
    SV0_Family = np.empty((6, total_num))
    tf_Family = np.empty(total_num)

    SV0_Family[:, :N_minus] = SV0_Family_minus
    SV0_Family[:, N_minus] = SV0_original
    SV0_Family[:, N_minus + 1:] = SV0_Family_plus

    tf_Family[:N_minus] = tf_Family_minus
    tf_Family[N_minus] = tf_original
    tf_Family[N_minus + 1:] = tf_Family_plus

    return (
        SV0_Family_plus,
        tf_Family_plus,
        SV0_Family_minus,
        tf_Family_minus,
        SV0_Family,
        tf_Family,
    )


if __name__ == "__main__":
    # 初始猜测（最后一组生效）
    SV0_initial = [0.81789987042275, 0, 0, 0, 0.50589349644, 0]
    tf_initial = 2.963654

    # 获取高精度原始周期轨道
    tol = 1e-8
    N = 10000
    maxiter = 300
    SV0_original, tf_original = CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_T(
        SV0_initial, tf_initial, tol, N, maxiter
    )

    # 延拓参数
    beta = 0.000260143
    N_plus = 100
    N_minus = 100

    # 执行以 x0 为参数的延拓
    (
        SV0_Family_plus,
        tf_Family_plus,
        SV0_Family_minus,
        tf_Family_minus,
        SV0_Family,
        tf_Family,
    ) = CR3BP_Single_Parameter_Continuation_2D_X0(
        SV0_original, tf_original, beta, N_plus, N_minus
    )

    # 整合周期列表
    period_list = tf_Family_minus.tolist() + tf_Family_plus.tolist()
    T_all = np.array(period_list)

    # 积分所有轨道用于稳定性分析
    results = []
    default_time_steps = 1000

    # 负向轨道
    for j in range(N_minus):
        _, SV_minus_j = CR3BP_Propagation(
            SV0_Family_minus[:, j], tf_Family_minus[j], 2 * default_time_steps
        )
        results.append(SV_minus_j.T)

    # 正向轨道
    for i in range(N_plus):
        _, SV_plus_i = CR3BP_Propagation(
            SV0_Family_plus[:, i], tf_Family_plus[i], 2 * default_time_steps
        )
        results.append(SV_plus_i.T)

    # 计算稳定性指标
    nu_list = []
    L_list = []
    for i in range(len(results)):
        monodromy = Compute_Monodromy_Matrix(results[i][0, :], T_all[i], N)
        nu_i, L_i = Compute_Stability_Index(monodromy)
        nu_list.append(nu_i)
        L_list.append(L_i)

    # 提取 x0 值
    x0_list = [results[i][0, 0] for i in range(len(results))]

    # 绘制稳定性随 x0 的变化
    plt.figure(1)
    plt.plot(x0_list, nu_list, 'b-')
    plt.xlabel(r"$x_0$")
    plt.ylabel(r"$\nu$ (Stability Index)")
    plt.grid(True)

    plt.figure(2)
    plt.plot(x0_list, L_list, 'r-')
    plt.xlabel(r"$x_0$")
    plt.ylabel(r"$L$ (Multiplier Magnitude)")
    plt.grid(True)

    # 3D 轨道族可视化
    fig = plt.figure(3)
    ax = fig.add_subplot(111, projection='3d')

    # 原始轨道
    _, SV_original = CR3BP_Propagation(SV0_original, tf_original, 2 * N)
    ax.plot(SV_original[0, :], SV_original[1, :], SV_original[2, :], color='red', linewidth=2, label='Reference')

    # 正向轨道
    for i in range(N_plus):
        _, SV_plus_i = CR3BP_Propagation(SV0_Family_plus[:, i], tf_Family_plus[i], 2 * N)
        ax.plot(SV_plus_i[0, :], SV_plus_i[1, :], SV_plus_i[2, :], color='blue', linewidth=0.8)

    # 负向轨道
    for j in range(N_minus):
        _, SV_minus_j = CR3BP_Propagation(SV0_Family_minus[:, j], tf_Family_minus[j], 2 * N)
        ax.plot(SV_minus_j[0, :], SV_minus_j[1, :], SV_minus_j[2, :], color='blue', linewidth=0.8)

    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    ax.set_title('Periodic Orbit Family in CR3BP')
    ax.legend()
    plt.show()