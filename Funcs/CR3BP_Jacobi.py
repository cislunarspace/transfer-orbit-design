# 文件名：CR3BP_Jacobi.py
# 编写人：陈昱桔
# 开发时间：2023/10/26 9:38
# 功能：
"""
求解等效势能和Jacobi积分
"""

mu = 0.0121505856


def u_bar(state, mu):
    """
    :param state: 位置矢量
    :return: 等效势能
    """
    x_var, y_var, z_var = state
    mu1 = 1 - mu
    mu2 = mu
    # where r1 and r2 are expressed in rotating coordinates
    r1_var = ((x_var + mu2) ** 2 + y_var**2 + z_var**2) ** (1 / 2)
    r2_var = ((x_var - mu1) ** 2 + y_var**2 + z_var**2) ** (1 / 2)
    aug_pot = (
        -1 / 2 * (x_var**2 + y_var**2) - mu1 / r1_var - mu2 / r2_var - 1 / 2 * mu1 * mu2
    )
    return aug_pot


def jacobi(state, mu):
    """
    :param state: 位置、速度矢量
    :return: Jacobi积分
    """
    if len(state) == 3:  # if only position is given, velocity is supposed null
        jacobi_cst = -2 * u_bar(state, mu)
    elif len(state) == 6:
        jacobi_cst = -2 * u_bar(state[0:3], mu) - (
            state[3] ** 2 + state[4] ** 2 + state[5] ** 2
        )
    else:
        raise Exception("State dimension wrong. State dimensions must be 3 or 6")
    return jacobi_cst


if __name__ == "__main__":
    print("hello")
