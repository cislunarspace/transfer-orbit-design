# -*- coding: utf-8 -*-
import numpy as np
import copy

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from Dynamics.CR3BP_Dynamics import CR3BP_Propagation_42


def Compute_Monodromy_Matrix(SV0, tf, N):
    """
    计算单值矩阵

    输入
    ----------
    SV0 : 轨道初值

    tf : 周期


    输出
    -------
    CR3BP_Monodromy_Matrix: 单值矩阵

    """
    # 将该轨道初值放在圆型限制性三体模型中进行数值积分，积分时间为tf
    CR3BP_t, CR3BP_State, CR3BP_SV, CR3BP_STM = CR3BP_Propagation_42(SV0, tf, N)

    # 获取积分终点的状态转移矩阵,即单值矩阵
    CR3BP_Monodromy_Matrix = CR3BP_STM[-1, :, :]

    return CR3BP_Monodromy_Matrix


def Compute_Stability_Index(CR3BP_Monodromy_Matrix):
    # 计算alpha,beta
    alpha = 2 - np.trace(CR3BP_Monodromy_Matrix)
    beta = (alpha**2 - (np.trace(CR3BP_Monodromy_Matrix)) ** 2) / 2 + 1

    # 计算p,q
    p = (alpha + (alpha**2 - 4 * beta + 8) ** 0.5) / 2
    q = (alpha - (alpha**2 - 4 * beta + 8) ** 0.5) / 2

    # 计算特征值
    # lam = np.zeros(6)
    # lam[0] = (-p + (p**2 - 4)**0.5)/2
    # lam[1] = 1/lam[0]
    # lam[2] = (-q + (q**2 - 4)**0.5)/2
    # lam[3] = 1/lam[2]
    # lam[4] = 1
    # lam[5] = 1
    eignvalue, eignvector = np.linalg.eig(CR3BP_Monodromy_Matrix)
    lam_max_nu = np.max(np.abs(np.real(eignvalue)))
    nu = 1 / 2 * (lam_max_nu + 1 / lam_max_nu)

    lam_max_L = np.max(np.abs(eignvalue))
    L = np.log(lam_max_L)

    return nu, L

if __name__ == "__main__":
    SV0 = [0.00526294904293785, 0, 0, 0, 10.587955203878211, 0]
    tf = 6.307578859418398
    SV0 = [0.005304, 0.0, 0.0, 0.0, 10.57532651775366, 0.0]
    tf = 6.307573675369461
    SV0 = [0.005262948596948918, 0.0, 0.0, 0.0, 10.58795534132045, 0.0]
    tf = 6.307578859473798
    SV0 = [0.005262948596927151, 0.0, 0.0, 0.0, 10.587955341327497, 0.0]
    tf = 6.3075788594746935
    N = 1000
    M = Compute_Monodromy_Matrix(SV0, tf, N)
    nu, L = Compute_Stability_Index(M)
    print(M)
    print(L)
    print(nu)
