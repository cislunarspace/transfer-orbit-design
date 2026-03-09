# 文件名：CR3BP_get_libration_point.py
# 编写人：陈昱桔
# 开发时间：2023/10/23 14:44
# 功能：

""""""

import numpy as np

from Funcs.CR3BP_Jacobi import jacobi

mu = 0.0121505856


def libration_points(mu):
    """
    求解5个平动点位置，以及对应的Jacobi积分
    output:3*5矩阵，每列对应一个平动点，分别为x，y,Jacobi积分
    """
    tol = 1e-12
    x, y, C = [], [], []

    # L1
    xold = 0.99
    error = 1
    while error > tol:
        f = xold - (1 - mu) / (mu + xold) ** 2 + mu / (xold - 1 + mu) ** 2
        fprime = (
            1
            + 2 * (1 - mu) * (mu + xold) / (mu + xold) ** 4
            - 2 * mu * (xold - 1 + mu) / (xold - 1 + mu) ** 4
        )
        xnew = xold - f / fprime
        error = abs(xnew - xold)
        xold = xnew
    x.append(xold)
    y.append(0.0)
    C.append(jacobi([x[0], y[0], 0.0, 0.0, 0.0, 0.0], mu))

    # L2
    xold = 1.01
    error = 1
    while error > tol:
        f = xold - (1 - mu) / (mu + xold) ** 2 - mu / (xold - 1 + mu) ** 2
        fprime = (
            1
            + 2 * (1 - mu) * (mu + xold) / (mu + xold) ** 4
            + 2 * mu * (xold - 1 + mu) / (xold - 1 + mu) ** 4
        )
        xnew = xold - f / fprime
        error = abs(xnew - xold)
        xold = xnew
    x.append(xold)
    y.append(0.0)
    C.append(jacobi([x[1], y[1], 0.0, 0.0, 0.0, 0.0], mu))

    # L3
    xold = -1
    error = 1
    while error > tol:
        f = xold + (1 - mu) / (mu + xold) ** 2 + mu / (xold - 1 + mu) ** 2
        fprime = (
            1
            - 2 * (1 - mu) * (mu + xold) / (mu + xold) ** 4
            - 2 * mu * (xold - 1 + mu) / (xold - 1 + mu) ** 4
        )
        xnew = xold - f / fprime
        error = abs(xnew - xold)
        xold = xnew
    x.append(xold)
    y.append(0.0)
    C.append(jacobi([x[2], y[2], 0.0, 0.0, 0.0, 0.0], mu))

    # L4
    x.append(0.5 - mu)
    y.append(np.sqrt(3) / 2)
    C.append(jacobi([x[3], y[3], 0.0, 0.0, 0.0, 0.0], mu))

    # L5
    x.append(0.5 - mu)
    y.append(np.sqrt(3) / 2)
    C.append(jacobi([x[4], y[4], 0.0, 0.0, 0.0, 0.0], mu))

    x = np.array([x])
    y = np.array([y])
    C = np.array([C])
    state = np.concatenate((x, y, C), axis=0)

    return state


if __name__ == "__main__":
    print("hello")
