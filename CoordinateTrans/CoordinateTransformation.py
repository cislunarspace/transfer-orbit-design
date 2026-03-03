# -*- coding: utf-8 -*-
# CoordinateTransformation.py
from Funcs.Ephemeris_and_UnitConversion import *
from RotationMatrix import *  # RotationX,RotationY,RotationZ

spice.kclear()
spice.furnsh("/home/ouyangjiahong/codes/CRTBP_code/Spice/Kernel/metakernel/EarthMoon.mk")


# 会合系转惯性系旋转矩阵
def rot_mat_synodic_to_inertial(R12, V12, mu, et):

    # 定义两矢量坐标系
    norm_R12 = np.linalg.norm(R12, ord=None, axis=1).reshape((np.size(et), 1))
    cross_R12_V12 = np.cross(R12, V12, axisa=1, axisb=1)
    norm_cross_R12_V12 = np.linalg.norm(cross_R12_V12, ord=None, axis=1).reshape(
        (np.size(et), 1)
    )

    # 旋转系到惯性系的旋转矩阵
    x_caret = R12 / norm_R12
    z_caret = cross_R12_V12 / norm_cross_R12_V12
    y_caret = np.cross(z_caret, x_caret, axisa=1, axisb=1)
    rot_mat_S_I = np.empty((np.size(et), 3, 3))

    rot_mat_S_I[:, 0] = x_caret
    rot_mat_S_I[:, 1] = y_caret
    rot_mat_S_I[:, 2] = z_caret
    rot_mat_S_I = np.transpose(rot_mat_S_I, axes=[0, 2, 1])

    # 会合系瞬时角速度 rad/s
    Om = norm_cross_R12_V12 / norm_R12**2
    Om_vector = np.empty((np.size(et), 3, 1))
    Om_vector[:, 0, 0] = 0
    Om_vector[:, 1, 0] = 0
    Om_vector[:, 2, 0] = Om[:, 0]

    # 旋转系到惯性系旋转矩阵对时间一阶导
    d_rot_mat_S_I = np.empty((np.size(et), 3, 3))

    d_rot_mat_S_I[:, 0, 0] = (
        Om * rot_mat_S_I[:, 0, 1].reshape((np.size(et), 1))
    ).reshape((np.size(et)), 1, 1)[:, 0, 0]
    d_rot_mat_S_I[:, 0, 1] = -(
        Om * rot_mat_S_I[:, 0, 0].reshape((np.size(et), 1))
    ).reshape((np.size(et)), 1, 1)[:, 0, 0]
    d_rot_mat_S_I[:, 0, 2] = 0

    d_rot_mat_S_I[:, 1, 0] = (
        Om * rot_mat_S_I[:, 1, 1].reshape((np.size(et), 1))
    ).reshape((np.size(et)), 1, 1)[:, 0, 0]
    d_rot_mat_S_I[:, 1, 1] = -(
        Om * rot_mat_S_I[:, 1, 0].reshape((np.size(et), 1))
    ).reshape((np.size(et)), 1, 1)[:, 0, 0]
    d_rot_mat_S_I[:, 1, 2] = 0

    d_rot_mat_S_I[:, 2, 0] = (
        Om * rot_mat_S_I[:, 2, 1].reshape((np.size(et), 1))
    ).reshape((np.size(et)), 1, 1)[:, 0, 0]
    d_rot_mat_S_I[:, 2, 1] = -(
        Om * rot_mat_S_I[:, 2, 0].reshape((np.size(et), 1))
    ).reshape((np.size(et)), 1, 1)[:, 0, 0]
    d_rot_mat_S_I[:, 2, 2] = 0

    # 完整旋转矩阵
    Full_rot_mat_S_I = np.empty((np.size(et), 6, 6))
    Full_rot_mat_S_I[:, 0:3, 0:3] = rot_mat_S_I
    Full_rot_mat_S_I[:, 0:3, 3:6] = np.zeros((np.size(et), 3, 3))
    Full_rot_mat_S_I[:, 3:6, 0:3] = d_rot_mat_S_I
    Full_rot_mat_S_I[:, 3:6, 3:6] = rot_mat_S_I

    # 返回旋转矩阵、两天体瞬时距离，系统瞬时旋转角速度
    return Full_rot_mat_S_I, norm_R12, Om_vector

# 地惯系转地心J2000
def GCRS_to_J2000(r_GCRS, v_GCRS):

    xi_0 = -16.617  # -16.617+-0.01 mas
    eta_0 = -6.819  # -6.819+-0.01 mas
    dalpha_0 = -14.6  # -14.6+-0.05 mas

    # 单位变换
    Xi_0 = np.deg2rad(xi_0 / 3600000)
    Eta_0 = np.deg2rad(eta_0 / 3600000)
    Dalpha_0 = np.deg2rad(dalpha_0 / 3600000)

    # 常值旋转矩阵
    Rx = RotationX(-Eta_0)
    Ry = RotationY(Xi_0)
    Rz = RotationZ(Dalpha_0)
    B = Rx * Ry * Rz

    # 坐标转换
    r_J2000 = B * r_GCRS
    v_J2000 = B * v_GCRS

    return r_J2000, v_J2000


# 地心J2000转地惯系
def J2000_to_GCRS(r_J2000, v_J2000):

    xi_0 = -16.617  # -16.617+-0.01 mas
    eta_0 = -6.819  # -6.819+-0.01 mas
    dalpha_0 = -14.6  # -14.6+-0.05 mas

    # 单位变换
    Xi_0 = np.deg2rad(xi_0 / 3600000)
    Eta_0 = np.deg2rad(eta_0 / 3600000)
    Dalpha_0 = np.deg2rad(dalpha_0 / 3600000)

    # 常值旋转矩阵
    Rx = RotationX(Eta_0)
    Ry = RotationY(-Xi_0)
    Rz = RotationZ(-Dalpha_0)
    B_T = Rz * Ry * Rx

    # 坐标转换
    r_GCRS = B_T * r_J2000
    v_GCRS = B_T * v_J2000

    return r_GCRS, v_GCRS


# 地惯系转地固系
def GCRS_to_ITRF(r_GCRS, v_GCRS, et):

    # # 获得星历时间
    # et = spice.str2et(utc)

    # 获得转换矩阵
    TransMatrix = spice.sxform("J2000", "IAU_Earth", et)

    # 状态向量
    state_GCRS = [r_GCRS, v_GCRS]

    # 矩阵相乘
    state_ITRF = spice.mxvg(TransMatrix, state_GCRS)

    r_ITRF = state_ITRF[:, 0:3]
    v_ITRF = state_ITRF[:, 3:6]

    return r_ITRF, v_ITRF


# 地固系转地惯系
def ITRF_to_GCRS(r_ITRF, v_ITRF, et):

    # # 获得星历时间
    # et = spice.str2et(utc)

    # 获得转换矩阵
    TransMatrix = spice.sxform("IAU_Earth", "J2000", et)

    # 状态向量
    state_ITRF = [r_ITRF, v_ITRF]

    # 矩阵相乘
    state_GCRS = TransMatrix * state_ITRF

    r_GCRS = state_GCRS[:, 0:3]
    v_GCRS = state_GCRS[:, 3:6]

    return r_GCRS, v_GCRS


# 地惯系转ICRF
def GCRS_to_ICRF(r_GCRS, v_GCRS, et):

    # 获取某时刻地球相对太阳系质心的位置速度矢量
    [et, r_Earth_SC, v_Earth_SC] = Ephemeris("Sun", "Earth", "J2000", et)

    # 将原点平移至太阳系质心
    r_ICRF = r_GCRS + r_Earth_SC
    v_ICRF = v_GCRS + v_Earth_SC

    return r_ICRF, v_ICRF


# ICRF转地惯系
def ICRF_to_GCRS(r_ICRF, v_ICRF, et):

    # 获取某时刻地球相对太阳系质心的位置速度矢量
    [et, r_Earth_SC, v_Earth_SC] = Ephemeris("Sun", "Earth", "J2000", et)

    # 将原点平移至太阳系质心
    r_GCRS = r_ICRF - r_Earth_SC
    v_GCRS = v_ICRF - v_Earth_SC

    return r_GCRS, v_GCRS


# 地惯系转月惯系
def GCRS_to_MI(r_GCRS, v_GCRS, et):

    # 获取某时刻月球位置速度矢量
    [et, r_Moon_EC, v_Moon_EC] = Ephemeris("Earth", "Moon", "J2000", et)

    # 将原点平移至月心
    r_MI = r_GCRS - r_Moon_EC
    v_MI = v_GCRS - v_Moon_EC

    return r_MI, v_MI


# 月惯系转地惯系
def MI_to_GCRS(r_MI, v_MI, et):

    # 获取某时刻月球位置速度矢量
    [et, r_Moon_EC, v_Moon_EC] = Ephemeris("Earth", "Moon", "J2000", et)

    # 将原点平移至月心
    r_GCRS = r_MI + r_Moon_EC
    v_GCRS = v_MI + v_Moon_EC

    return r_GCRS, v_GCRS


# 地月会合系转地惯系
def EMR_to_GCRS(r_EMR, v_EMR, et):
    # 修改：确保et是数值数组
    if isinstance(et[0], str):  # 如果是UTC字符串
        et = getTime(et)

    # 确定地月系统相关常数
    GM_Earth = spice.bodvrd("Earth", "GM", 1)[1]
    GM_Moon = spice.bodvrd("Moon", "GM", 1)[1]
    mu = GM_Moon / (GM_Earth + GM_Moon)[0]

    # 获取某时刻月球位置速度矢量
    [r_Moon_EC, v_Moon_EC] = Ephemeris("Earth", "Moon", "J2000", et)

    # 获取旋转矩阵、地月系统瞬时距离、瞬时旋转角速度
    Full_rot_mat_S_I, norm_r_Moon_EC, Om_vector = rot_mat_synodic_to_inertial(
        r_Moon_EC, v_Moon_EC, mu, et
    )

    # 地心、月心相对地月质心坐标系下的瞬时距离
    r_Earth_BC = norm_r_Moon_EC * mu  # 地心至地月系统质心真实距离km
    r_Moon_BC = norm_r_Moon_EC * (1 - mu)  # 地心至地月系统质心真实距离km

    # 定义地月会合系下航天器状态向量
    State_EMR = np.empty((np.size(et), 1, 6))
    State_EMR[:, 0, 0:3] = r_EMR
    State_EMR[:, 0, 3:6] = v_EMR
    State_EMR = State_EMR.reshape((np.size(et), 6, 1))

    # 地球相对于地月会合坐标系的位置、速度矢量
    r_Earth_BC = r_Earth_BC.reshape((np.size(et), 1, 1))
    R_Earth_BC = np.empty((np.size(et), 3, 1))
    R_Earth_BC[:, 0, 0] = -r_Earth_BC[:, 0, 0]
    R_Earth_BC[:, 1, 0] = 0
    R_Earth_BC[:, 2, 0] = 0
    V_Earth_BC = np.cross(-Om_vector, R_Earth_BC, axisa=1, axisb=1).reshape(
        (np.size(et), 3, 1)
    )

    # 将地月会合坐标系质心平移至地心

    State_ECR_R = State_EMR[:, 0:3, 0].reshape((np.size(et), 3, 1)) - R_Earth_BC
    State_ECR_V = State_EMR[:, 3:6, 0].reshape((np.size(et), 3, 1)) - V_Earth_BC
    State_ECR = np.concatenate((State_ECR_R, State_ECR_V), axis=1)

    # 旋转至地心惯性系
    State_GCRS = np.matmul(Full_rot_mat_S_I, State_ECR)

    r_GCRS = State_GCRS[:, 0:3, 0]
    v_GCRS = State_GCRS[:, 3:6, 0]

    r_GCRS = r_GCRS.reshape((np.size(et), 3))
    v_GCRS = v_GCRS.reshape((np.size(et), 3))

    return r_GCRS, v_GCRS


# 地惯系转地月会合系
def GCRS_to_EMR(r_GCRS, v_GCRS, et):
    # 修改：确保et是数值数组
    if isinstance(et[0], str):  # 如果是UTC字符串
        et = getTime(et)

    # 确定地月系统相关常数
    GM_Earth = spice.bodvrd("Earth", "GM", 1)[1]
    GM_Moon = spice.bodvrd("Moon", "GM", 1)[1]
    mu = GM_Moon / (GM_Earth + GM_Moon)[0]

    # 获取某时刻月球位置速度矢量
    [r_Moon_EC, v_Moon_EC] = Ephemeris("Earth", "Moon", "J2000", et)

    # 获取旋转矩阵、地月系统瞬时距离、瞬时旋转角速度
    Full_rot_mat_S_I, norm_r_Moon_EC, Om_vector = rot_mat_synodic_to_inertial(
        r_Moon_EC, v_Moon_EC, mu, et
    )

    # 地心、月心相对地月质心坐标系下的瞬时距离
    r_Earth_BC = norm_r_Moon_EC * mu  # 地心至地月系统质心真实距离km
    r_Moon_BC = norm_r_Moon_EC * (1 - mu)  # 地心至地月系统质心真实距离km

    # 定义地惯系下航天器状态向量
    State_GCRS = np.empty((np.size(et), 1, 6))
    State_GCRS[:, 0, 0:3] = r_GCRS
    State_GCRS[:, 0, 3:6] = v_GCRS
    State_GCRS = State_GCRS.reshape((np.size(et), 6, 1))

    # 旋转至地心会合坐标系
    State_ECR = np.linalg.solve(Full_rot_mat_S_I, State_GCRS)

    # 地月系统质心相对于地球的位置、速度矢量
    r_Earth_BC = r_Earth_BC.reshape((np.size(et), 1, 1))
    R_BC_Earth = np.empty((np.size(et), 3, 1))
    R_BC_Earth[:, 0, 0] = r_Earth_BC[:, 0, 0]
    R_BC_Earth[:, 1, 0] = 0
    R_BC_Earth[:, 2, 0] = 0
    V_BC_Earth = np.cross(-Om_vector, R_BC_Earth, axisa=1, axisb=1).reshape(
        (np.size(et), 3, 1)
    )

    # 平移至地月质心
    State_EMR_R = State_ECR[:, 0:3, 0].reshape((np.size(et), 3, 1)) - R_BC_Earth
    State_EMR_V = State_ECR[:, 3:6, 0].reshape((np.size(et), 3, 1)) - V_BC_Earth
    State_EMR = np.concatenate((State_EMR_R, State_EMR_V), axis=1)

    r_EMR = State_EMR[:, 0:3, 0]
    v_EMR = State_EMR[:, 3:6, 0]

    return r_EMR, v_EMR


# 地月会合系转月心惯性系
def EMR_to_MI(r_EMR, v_EMR, et):

    # 将会合系下的位置速度矢量转移至地心惯性系
    r_GCRS, v_GCRS = EMR_to_GCRS(r_EMR, v_EMR, et)

    # 平移至月心
    r_MI, v_MI = GCRS_to_MI(r_GCRS, v_GCRS, et)

    return r_MI, v_MI


# 月心惯性系转地月会合系
def MI_to_EMR(r_MI, v_MI, et):

    # 平移至地球质心
    r_GCRS, v_GCRS = MI_to_GCRS(r_MI, v_MI, et)

    # 转移至地月会合坐标系
    r_EMR, v_EMR = GCRS_to_EMR(r_GCRS, v_GCRS, et)

    return r_EMR, v_EMR

if __name__ == "__main__":
    # 测试
    utc = ['01 Jan 2028 00:11:09.168']
    et = getTime(utc)
    r_EMR = [359622.6502754249, 0, 0]
    v_EMR = [0, 0.469725, 0]
    r_GCRS, v_GCRS = EMR_to_GCRS(r_EMR, v_EMR,et)
    X_GCRS = np.concatenate((r_GCRS,v_GCRS),axis=1)
    print(r_GCRS)
    print(v_GCRS)


    utc = ['01 Jan 2025 00:00:00.000','02 Jan 2025 00:00:00.000']
    r_GCRS = np.array([[105191834906.9699, -47973262639.33333, 101134600819.1729],[105191834906.9699, -47973262639.33333, 101134600819.1729]])
    v_GCRS = np.array([[-16516.89234682873, 254265.786803117, 137792.6412136556],[-16516.89234682873, 254265.786803117, 137792.6412136556]])
    r_EMR, v_EMR = GCRS_to_EMR(r_GCRS, v_GCRS, utc)
    print(r_EMR)
    print(v_EMR)


    utc = ['01 Jan 2025 00:00:00.000','02 Jan 2025 00:00:00.000']
    r_EMR = np.array([[58474488700.00002, 87576237100.00002, 111830675000],[58474488700.00002, 87576237100.00002, 111830675000]])
    v_EMR = np.array([[0.9554907300043851, 0.8312989600235596, 0.6575268000160577],[0.9554907300043851, 0.8312989600235596, 0.6575268000160577]])
    r_MI, v_MI = EMR_to_MI(r_EMR, v_EMR, utc)
    print(r_MI)
    print(v_MI)

    utc = ['01 Jan 2025 00:00:00.000','02 Jan 2025 00:00:00.000']
    r_MI = np.array([[105191607084.1139, -47972996882.92648, 101134744965.5356],[105191607084.1139, -47972996882.92648, 101134744965.5356]])
    v_MI = np.array([[-16517.70368481344, 254265.2118708625, 137792.3301597261],[-16517.70368481344, 254265.2118708625, 137792.3301597261]])
    r_EMR, v_EMR = MI_to_EMR(r_MI, v_MI, utc)
    print(r_EMR)
    print(v_EMR)

    utc = ['01 Jan 2025 00:00:00.000','02 Jan 2025 00:00:00.000']
    r_GCRS = np.array([[103714428500.92839, -69695568040.31377, 89335371846.69431],[103714428500.92839, -69695568040.31377, 89335371846.69431]])
    v_GCRS = np.array([[50741.14337391643, 50741.14337391643, 133644.7304307124],[50741.14337391643, 50741.14337391643, 133644.7304307124]])
    r_MI, v_MI = GCRS_to_MI(r_GCRS, v_GCRS, utc)
    print(r_MI)
    print(v_MI)

    spice.kclear()
