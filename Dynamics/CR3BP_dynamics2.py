# 文件名：CR3BP_dynamics2.py
# 编写人：陈昱桔
# 开发时间：2023/10/26 14:45
# 功能：
"""
给出CR3BP下的动力学方程
u_bar为等效势能U的一阶偏导数
u_bar2为等效势能下的二阶偏导数
"""

import numpy as np

mu = 0.0121505856


def u_bar_first_partials(state, mu):
    """
    Parameters
    ----------
    state : 归一化矢量， 状态矢量
    mu : CR3BP mass parameter.

    Returns
    -------
    u_bar : ndarray 等效势能的一阶偏导
    """

    r_13 = (
        (state[0] + mu) * (state[0] + mu) + state[1] * state[1] + state[2] * state[2]
    ) ** (-1.5)  # 1/r1^3
    r_23 = (
        ((state[0] - 1.0 + mu) * (state[0] - 1.0 + mu))
        + state[1] * state[1]
        + state[2] * state[2]
    ) ** (-1.5)  # 1/r2^3

    u_bar = np.empty(3)  # preallocate array to store the partials

    u_bar[0] = (
        -mu * (state[0] - 1.0 + mu) * r_23
        - (1.0 - mu) * (state[0] + mu) * r_13
        + state[0]
    )
    u_bar[1] = -mu * state[1] * r_23 - (1.0 - mu) * state[1] * r_13 + state[1]
    u_bar[2] = -mu * state[2] * r_23 - (1.0 - mu) * state[2] * r_13

    return u_bar


def u_bar_second_partials(state, mu):
    """
    Parameters
    ----------
    state : 归一化单位， 状态矢量
    mu : CR3BP mass parameter.

    Returns
    -------
    u_bar2 : ndarray
        Second partial derivatives of the augmented potential as 3x3 Numpy array with
        ``u_bar2[i, j] = d_u_bar[i]/d_state[j]``.

    """

    r_12 = (
        (state[0] + mu) * (state[0] + mu) + state[1] * state[1] + state[2] * state[2]
    )  # r1^2
    r_22 = (
        ((state[0] - 1.0 + mu) * (state[0] - 1.0 + mu))
        + state[1] * state[1]
        + state[2] * state[2]
    )  # r2^2

    r_13 = r_12 ** (-1.5)  # 1/r1^3
    r_23 = r_22 ** (-1.5)  # 1/r2^3
    r_15 = r_12 ** (-2.5)  # 1/r1^5
    r_25 = r_22 ** (-2.5)  # 1/r2^5

    u_bar2 = np.empty((3, 3))

    u_bar2[0, 0] = (
        1.0
        - mu * r_23
        - (1.0 - mu) * r_13
        + 3.0 * mu * (state[0] - 1.0 + mu) * (state[0] - 1.0 + mu) * r_25
        + 3.0 * (state[0] + mu) * (state[0] + mu) * (1.0 - mu) * r_15
    )

    u_bar2[0, 1] = (
        3.0 * state[1] * (mu + state[0]) * (1.0 - mu) * r_15
        - 3.0 * mu * state[1] * (-state[0] + 1.0 - mu) * r_25
    )

    u_bar2[0, 2] = (
        3.0 * state[2] * (mu + state[0]) * (1.0 - mu) * r_15
        - 3.0 * mu * state[2] * (-state[0] + 1.0 - mu) * r_25
    )

    u_bar2[1, 0] = u_bar2[0, 1]

    u_bar2[1, 1] = (
        -mu * r_23
        - (1.0 - mu) * r_13
        + 3.0 * state[1] * state[1] * (1.0 - mu) * r_15
        + 3.0 * mu * state[1] ** 2 * r_25
        + 1.0
    )

    u_bar2[1, 2] = (
        3.0 * state[1] * state[2] * (1.0 - mu) * r_15
        + 3.0 * mu * state[1] * state[2] * r_25
    )

    u_bar2[2, 0] = u_bar2[0, 2]
    u_bar2[2, 1] = u_bar2[1, 2]

    u_bar2[2, 2] = (
        -mu * r_23
        - (1.0 - mu) * r_13
        + 3.0 * state[2] ** 2 * (1.0 - mu) * r_15
        + 3.0 * mu * state[2] ** 2 * r_25
    )

    return u_bar2


def eqm_6_synodic(t, state, mu):
    """6维状态矢量的导数 1*6

    Parameters
    ----------
        Time, required for integrators.
    state : iterable
        Orbit's state.
    mu : float
        CR3BP mass parameter.

    Returns
    -------
    dot_state : ndarray
        Set of 6 first-order ODEs of the 6-dim state.

    """

    u_bar = u_bar_first_partials(state, mu)

    dot_state = np.empty(6)  # preallocate array for state derivatives
    dot_state[0] = state[3]
    dot_state[1] = state[4]
    dot_state[2] = state[5]
    dot_state[3] = 2.0 * state[4] - u_bar[0]
    dot_state[4] = -2.0 * state[3] - u_bar[1]
    dot_state[5] = -u_bar[2]

    return dot_state


def cr3bp_eom(t, stateSTM, mu):
    """
    stateSTM = 42 element array; the first 6 elements contain the
        non-dimensionalized, rotating position and velocity; the remaining
        elements are the state transition matrix.
    mu = mass ratio of the two primaries
    """
    # intermediate variables
    x = stateSTM[0]
    y = stateSTM[1]
    z = stateSTM[2]
    vx = stateSTM[3]
    vy = stateSTM[4]
    vz = stateSTM[5]

    # range between s/c and each primary
    r1 = np.sqrt((x + mu) ** 2 + y**2 + z**2)
    r2 = np.sqrt((x - 1 + mu) ** 2 + y**2 + z**2)

    # integrate spacecraft
    ax = 2 * vy + x - (1 - mu) * (x + mu) / r1**3 - mu * (x - 1 + mu) / r2**3
    ay = -2 * vx + y - (1 - mu) * y / r1**3 - mu * y / r2**3
    az = -(1 - mu) * z / r1**3 - mu * z / r2**3

    # build A matrix
    Uxx = (
        1
        - (1 - mu) / r1**3
        - mu / r2**3
        + (3 * (1 - mu) * (x + mu) ** 2) / r1**5
        + (3 * mu * (1 - mu - x) ** 2) / r2**5
    )
    Uyy = (
        1
        - (1 - mu) / r1**3
        - mu / r2**3
        + (3 * (1 - mu) * y**2) / r1**5
        + (3 * mu * y**2) / r2**5
    )
    Uzz = (
        -(1 - mu) / r1**3
        - mu / r2**3
        + (3 * (1 - mu) * z**2) / r1**5
        + (3 * mu * z**2) / r2**5
    )
    Uxy = (3 * (1 - mu) * (x + mu) * y) / r1**5 + (3 * mu * (x - 1 + mu) * y) / r2**5
    Uyx = Uxy
    Uxz = (3 * (1 - mu) * (x + mu) * z) / r1**5 + (3 * mu * (x - 1 + mu) * z) / r2**5
    Uzx = Uxz
    Uyz = (3 * (1 - mu) * y * z) / r1**5 + 3 * mu * y * z / r2**5
    Uzy = Uyz
    A = np.zeros((6, 6))
    A[0:3, 3:6] = np.eye(3)
    A[3:6, 0:3] = np.array([[Uxx, Uxy, Uxz], [Uyx, Uyy, Uyz], [Uzx, Uzy, Uzz]])
    A[3:6, 3:6] = np.array([[0.0, 2.0, 0.0], [-2.0, 0.0, 0.0], [0.0, 0.0, 0.0]])

    # integrate STM
    STM = np.reshape(stateSTM[6:], (6, 6))
    STMdot = np.zeros((6, 6))
    STMdot = np.dot(A, STM)

    # output
    stateSTMdot = np.concatenate(
        (np.array([vx, vy, vz, ax, ay, az]), STMdot.reshape(36)), axis=0
    )

    return stateSTMdot


if __name__ == "__main__":
    print("hello")
