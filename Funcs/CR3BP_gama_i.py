# 文件名：CR3BP_gama_i.py
# 编写人：陈昱桔
# 开发时间：2023/10/31 8:48
# 功能：

"""
求各平动点距离最近天体的距离gamma_i
init_libp：
输入：平动点，求解精度，mu
输出：gamma_i

polynomial_li：
输入：mu，平动点，gamma_i初始猜测值
输出：欧拉方程，欧拉方程的一阶导数

rtnewton：实现Newton迭代法
输出：修正后的gamma_i
"""


def init_libp(number, libration_point_precision, mu):
    rh = (mu / 3.0) ** (1.0 / 3.0)
    if number == 1:
        gamma_i = rh - 1 / 3.0 * rh**2 - 1 / 9 * rh**3  # initial guess
        gamma_i = rtnewton(gamma_i, libration_point_precision, mu, number)
        return gamma_i
    if number == 2:
        gamma_i = rh + 1 / 3.0 * rh**2 - 1 / 9 * rh**3
        gamma_i = rtnewton(gamma_i, libration_point_precision, mu, number)
        return gamma_i
    if number == 3:
        gamma_i = 7 / 12.0 * mu + 237**2 / 12**4 * mu**3
        gamma_i = rtnewton(gamma_i, libration_point_precision, mu, number)
        libp_gamma_i = 1 - gamma_i
        return libp_gamma_i
    if number == 4:
        # gamma_i: distance to the closest primary
        libp_gamma_i = 1
        return libp_gamma_i
    if number == 5:
        # gamma_i: distance to the closest primary
        libp_gamma_i = 1
        return libp_gamma_i
    return 0


def polynomial_li(mu_p, number, y):
    """Provides the function value and its first derivative for the Newton-Raphson method.

    f corresponds to the equation satisfied by the
    Li-m2 distance for the L1/L2 cases and by 1-(Li-m1 distance) for the L3 case.

    """
    # Initialisation
    f = df = None

    if number == 1:
        f = (
            y**5
            - ((3.0 - mu_p) * y**4)
            + ((3 - 2 * mu_p) * y**3)
            - (mu_p * y**2)
            + (2 * mu_p * y - mu_p)
        )
        df = (
            (5 * y**4)
            - (4 * (3.0 - mu_p) * y**3)
            + (3 * (3 - 2 * mu_p) * (y**2))
            - (2 * mu_p * y)
            + (2 * mu_p)
        )
    elif number == 2:
        f = (
            y**5
            + (3.0 - mu_p) * y**4
            + (3 - 2 * mu_p) * y**3
            - mu_p * y**2
            - 2 * mu_p * y
            - mu_p
        )
        df = (
            5 * y**4
            + 4 * (3.0 - mu_p) * y**3
            + 3 * (3 - 2 * mu_p) * y**2
            - 2 * mu_p * y
            - 2 * mu_p
        )
    elif number == 3:
        f = (
            y**5
            + (7 + mu_p) * y**4
            + (19 + 6 * mu_p) * y**3
            - (24 + 13 * mu_p) * y**2
            + (12 + 14 * mu_p) * y
            - 7 * mu_p
        )
        df = (
            5 * y**4
            + 4 * (7 + mu_p) * y**3
            + 3 * (19 + 6 * mu_p) * y**2
            - 2 * (24 + 13 * mu_p) * y
            + (12 + 14 * mu_p)
        )
    return f, df


def rtnewton(y, precision_gg, mu_p, number):
    """Using the Newton-Raphson method, find the root of a function known to lie
    close to y (in our case is gamma_i). The root rtnewt will be refined until its accuracy
    is known within ± precision_gg. polynomial_li is a function that returns both the
    function value and the first derivative of the function at the point gg_var."""

    gg_var = y
    while True:
        f00, df0 = polynomial_li(mu_p, number, gg_var)

        if abs(f00) < precision_gg:
            break

        gg_var = gg_var - f00 / df0
    return gg_var


if __name__ == "__main__":
    a = init_libp(3, 0.000001, 0.0121505856)
    print(a)
