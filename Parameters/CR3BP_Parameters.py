# -*- coding: utf-8 -*-
# CR3BP_Parameters.py
import spiceypy as spice

spice.furnsh("../Spice/EarthMoon.mk")


def get_CR3BP_EM_Constants():
    """确定圆型限制性三体模型下地月系统相关常数"""

    # 获取两大天体质量（单位：km^3/s^2）
    GM_Primary1 = spice.bodvrd("Earth", "GM", 1)[1][0]  # Earth
    GM_Primary2 = spice.bodvrd("Moon", "GM", 1)[1][0]  # Moon

    # 月球-地月系无量纲质量
    mu = GM_Primary2 / (GM_Primary1 + GM_Primary2)

    return mu


if __name__ == "__main__":
    print(get_CR3BP_EM_Constants())
    print("hello")
