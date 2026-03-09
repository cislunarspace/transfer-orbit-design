# -*- coding: utf-8 -*-
"""
CR3BP/CR3BP_DifferentialCorrection.py

主程序：使用微分修正法计算圆型限制性三体问题（CR3BP）中的二维周期轨道（如DRO），
并可视化轨道及拼接点。适用于地月系统，采用归一化单位。
"""

import random
import numpy as np
from matplotlib import pyplot as plt

from Dynamics.CR3BP_Dynamics import CR3BP_Propagation
from Funcs.CR3BP_get_libration_points import libration_points
from Main.CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_X0 import (
    CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_X0,
)
from Parameters.CR3BP_Parameters import get_CR3BP_EM_Constants


if __name__ == "__main__":
    # 初始猜测值（最后一组生效，用于DRO轨道）
    SV0_initial = [0.79188556619742, 0, 0, 0, 0.5368198361, 0]
    tf_initial = 3.4725358862

    # 微分修正参数
    tol = 5e-14  # 收敛容差
    N = 10000  # 积分步数（用于微分修正内部传播）
    maxiter = 300  # 最大迭代次数
    N_Patch = 3  # 拼接点数量（包括起点和终点）

    # 执行微分修正，获得高精度周期轨道初值和周期
    SV0_corrected, tf_corrected = (
        CR3BP_Newton_Differential_Correction_2D_Symmetric_X_Fixed_X0(
            SV0_initial, tf_initial, tol, N, maxiter
        )
    )

    # 完整积分一个周期用于绘图（积分半周期后对称延拓，此处直接积分全周期以验证闭合性）
    CR3BP_t, CR3BP_SV = CR3BP_Propagation(SV0_corrected, tf_corrected, 2 * N)

    # 在 [0, tf_corrected] 内生成 N_Patch 个拼接点（首尾固定，中间随机）
    CR3BP_t_Patch = np.zeros(N_Patch)
    CR3BP_t_Patch[0] = 0.0
    CR3BP_t_Patch[-1] = tf_corrected

    if N_Patch > 2:
        # 生成 N_Patch - 2 个 (0,1) 之间的随机数并排序
        random_fractions = sorted(random.random() for _ in range(N_Patch - 2))
        for i in range(N_Patch - 2):
            CR3BP_t_Patch[i + 1] = tf_corrected * random_fractions[i]

    # 存储各拼接点处的状态向量
    CR3BP_SV_Patch = np.array([SV0_corrected]).T  # 起点状态

    # 从起点依次积分到每个拼接点，记录状态
    for i in range(1, N_Patch):
        _, CR3BP_SV_seg = CR3BP_Propagation(SV0_corrected, CR3BP_t_Patch[i], 1000)
        state_at_patch = CR3BP_SV_seg[:, -1].reshape(-1, 1)
        CR3BP_SV_Patch = np.concatenate((CR3BP_SV_Patch, state_at_patch), axis=1)

    # 验证轨道闭合性（应接近零）
    print("dx (x_end - x_start):", np.abs(CR3BP_SV[0, -1] - CR3BP_SV[0, 0]))
    print("dvy (vy_end - vy_start):", np.abs(CR3BP_SV[4, -1] - CR3BP_SV[4, 0]))

    # 获取地月系统参数
    mu = get_CR3BP_EM_Constants()
    earth = [-mu, 0.0, 0.0]
    moon = [1 - mu, 0.0, 0.0]

    # 计算拉格朗日点位置
    l_position = libration_points(mu)
    l1 = [l_position[0][0], l_position[1][0], 0.0]
    l2 = [l_position[0][1], l_position[1][1], 0.0]  # 修正：原代码误用 l_position[1][2]
    # l3 未在图中使用，可忽略

    # 绘图
    plt.figure(figsize=(8, 6))
    plt.plot(
        CR3BP_SV[0, :], CR3BP_SV[1, :], color="r", label="Periodic Orbit (e.g., DRO)"
    )
    plt.xlabel("x (normalized)")
    plt.ylabel("y (normalized)")

    # 绘制拼接点
    for i in range(N_Patch):
        plt.scatter(CR3BP_SV_Patch[0, i], CR3BP_SV_Patch[1, i], color="g", s=30)
    plt.scatter(
        CR3BP_SV_Patch[0, 0], CR3BP_SV_Patch[1, 0], color="g", label="Patch Points"
    )

    # 标注天体和拉格朗日点
    plt.text(earth[0], earth[1] - 0.04, "Earth")
    plt.text(moon[0], moon[1] + 0.02, "Moon")
    plt.text(l1[0], l1[1] - 0.04, "L1")
    plt.text(l2[0], l2[1] - 0.04, "L2")

    plt.scatter(earth[0], earth[1], color="b", label="Earth", s=100)
    plt.scatter(moon[0], moon[1], color="y", label="Moon", s=80)
    plt.scatter(l1[0], l1[1], color="black", label="L1", zorder=2, s=40)
    plt.scatter(l2[0], l2[1], color="black", label="L2", zorder=2, s=40)

    plt.axis("equal")
    plt.title("Periodic Orbit in Synodic Frame (Earth-Moon CR3BP)")
    plt.legend(loc="best")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.show()
