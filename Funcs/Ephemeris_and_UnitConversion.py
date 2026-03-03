# -*- coding: utf-8 -*-
# Ephemeris_and_UnitConversion.py
import csv

import numpy as np
import spiceypy as spice
from scipy.io import savemat
spice.furnsh('/home/ouyangjiahong/codes/CRTBP_code/Spice/Kernel/metakernel/EarthMoon.mk')

def getTime(utc):
    # 将UTC转换为星历时间
    # 修改：处理单个字符串和字符串列表两种情况
    if isinstance(utc, str):
        et = spice.str2et(utc)
    elif isinstance(utc, list):
        et = np.array([spice.str2et(t) for t in utc])
    else:
        raise TypeError("utc必须是字符串或字符串列表")
    return et

def getTimeSeries(utc0,t):
    # 将轨道传播时间转为星历时间
    # 输入为初始时刻UTC、真实单位下的轨道传播时间序列
    et0 = spice.str2et(utc0)
    et = et0 + t
    return et


def Ephemeris(observer, target, frame, et):
    # 获取某时刻第二主天体相对于第一主天体的位置速度矢量
    # 输入星历时间et为时间序列
    # 修改：确保et是数组
    if np.isscalar(et):
        et = np.array([et])

    # 修改：正确处理spkezr的返回
    if len(et) == 1:
        State, LightTime = spice.spkezr(target, float(et[0]), frame, 'None', observer)
        State = np.array([State])
    else:
        results = []
        for et_i in et:
            State_i, LightTime = spice.spkezr(target, float(et_i), frame, 'None', observer)
            results.append(State_i)
        State = np.array(results)

    r = State[:, 0:3]
    v = State[:, 3:6]
    return r, v

def Normalization_to_Normal(primary1,primary2,et0,t_Normalization,r_Normalization,v_Normalization):
    GM_Primary1 = spice.bodvrd(primary1, 'GM', 1)[1]
    GM_Primary2 = spice.bodvrd(primary2, 'GM', 1)[1]

    # 获取真实单位下的时间序列
    et = np.array([])  # 真实星历时间序列
    et_last = et0  # 上一步星历时间
    t_Normalization_last = t_Normalization[0]  # 上一步归一化时间
    l_star_i = 384403.9
    t_star_i = (l_star_i ** 3 / (GM_Primary1 + GM_Primary2)) ** 0.5
    l_star = l_star_i
    t_star = t_star_i
    r_True = r_Normalization.reshape((np.size(et)),1,3)*l_star
    v_True = 0
    return et, r_True, v_True

def Normalization_to_True(primary1,primary2,et0,t_Normalization,r_Normalization,v_Normalization):
    # 将归一化单位下的时间序列、位置、速度转换为真实单位
    # 输入为两主天体名称，初始时刻et0(数组），归一化时间序列t,以及归一化单位下的位置速度矢量
    
    # 确定系统相关常数
    GM_Primary1 = spice.bodvrd(primary1,'GM', 1)[1]
    GM_Primary2 = spice.bodvrd(primary2,'GM', 1)[1]
    
    # 获取真实单位下的时间序列
    et = np.array([])   # 真实星历时间序列
    et_last = et0    # 上一步星历时间
    t_Normalization_last = t_Normalization[0]   # 上一步归一化时间
    
    for i in range(0,np.size(t_Normalization)):
        [r_Primary2_i,v_Primary2_i] = Ephemeris(primary1, primary2, 'J2000', et_last)
        l_star_i = np.linalg.norm(r_Primary2_i,ord=None,axis=1)
        t_star_i = (l_star_i**3/(GM_Primary1+GM_Primary2))**0.5
        et_i = et_last+t_star_i*(t_Normalization[i]-t_Normalization_last)
        et = np.concatenate((et,et_i))
        et_last = et_i
        t_Normalization_last = t_Normalization[i]
        
    # 获取某时刻第二主天体相对于第一主天体惯性系的位置速度矢量
    [r_Primary2,v_Primary2] = Ephemeris(primary1, primary2, 'J2000', et)
    
    # 归一化比例
    l_star = np.linalg.norm(r_Primary2,ord=None,axis=1)
    t_star = (l_star**3/(GM_Primary1+GM_Primary2))**0.5
    v_star = l_star/t_star
    
    # 获取真实单位下的位置速度矢量
    r_True = r_Normalization.reshape((np.size(et)),1,3) * l_star.reshape((np.size(et)),1,1)
    v_True = v_Normalization.reshape((np.size(et)),1,3) * v_star.reshape((np.size(et)),1,1)
    
    # 返回真实单位下的星历时间序列以及位置速度矢量
    return et, r_True, v_True

def True_to_Normalization(primary1,primary2,t_Normalization0,et,r_True,v_True):
    # 将真实单位下的时间序列、位置、速度转换为归一化单位
    # 输入为两主天体名称，初始时刻et0(数组），真实时间序列t,以及归一化单位下的位置速度矢量
    
    # 确定系统相关常数
    GM_Primary1 = spice.bodvrd(primary1,'GM', 1)[1]
    GM_Primary2 = spice.bodvrd(primary2,'GM', 1)[1]
    
    # 获取归一化单位下的时间序列
    t_Normalization = np.array([])   # 归一化时间序列
    t_Normalization_last = t_Normalization0 # 上一步归一化时间
    et_last = et[0]   # 上一步星历时间
    
    for i in range(0,np.size(et)):
        [r_Primary2_i,v_Primary2_i] = Ephemeris(primary1, primary2, 'J2000', np.array([et_last]))
        l_star_i = np.linalg.norm(r_Primary2_i,ord=None,axis=1)
        t_star_i = (l_star_i**3/(GM_Primary1+GM_Primary2))**0.5
        t_Normalization_i = t_Normalization_last+(et[i]-et_last)/t_star_i
        t_Normalization = np.concatenate((t_Normalization,t_Normalization_i))
        t_Normalization_last = t_Normalization_i
        et_last = et[i]
    
    # 获取某时刻第二主天体相对于第一主天体惯性系的位置速度矢量
    [r_Primary2,v_Primary2] = Ephemeris(primary1, primary2, 'J2000', et)
    
    # 归一化比例
    l_star = np.linalg.norm(r_Primary2,ord=None,axis=1)
    t_star = (l_star**3/(GM_Primary1+GM_Primary2))**0.5
    v_star = l_star/t_star
    
    # 获取真实单位下的位置速度矢量
    r_Normalization = r_True.reshape((np.size(et)),1,3) / l_star.reshape((np.size(et)),1,1)
    v_Normalization = v_True.reshape((np.size(et)),1,3) / v_star.reshape((np.size(et)),1,1)
    
    # 返回真实单位下的星历时间序列以及位置速度矢量
    return t_Normalization, r_Normalization, v_Normalization

if __name__ == "__main__":
    # 获取epochs
    utc0 = '01 Jan 2025 00:00:00.000'  # 改为字符串而不是列表
    et0 = getTime(utc0)
    et = np.zeros(525961)  # 改为np.zeros而不是np.empty
    for i in range(525961):
        et[i] = et0 + i * 60  # 直接计算，避免修改et0
    pic, _, _ = spice.tpictr('2025-01-01-00-00-00.0000000')
    epochs = spice.timout(et, pic)
    #epoches = np.reshape(epochs,(525961,1))
    ppp = np.vstack((epochs,et)).T
    csv_file = open('epoches1.csv', 'w', newline='')
    csv_writer = csv.writer(csv_file)
    for data in ppp:
        csv_writer.writerow(data)
    csv_file.close()

    # utc0 = '01 Jan 2028 00:00:00.000'
    # et0 = getTime(utc0)
    # et=np.empty(44641)
    # et = np.zeros(525961)  # 改为np.zeros而不是np.empty
    # for i in range(525961):
    #     et[i] = et0 + i * 60  # 直接计算，避免修改et0
    # moonstate = np.array(spice.spkezr('Moon', et, 'J2000', 'NONE', 'Earth')[0])
    # a = moonstate[:,0:3]
    # file_name = 'Moon.mat'
    # savemat(file_name,{'data':a})
