# -*- coding: utf-8 -*-

# 定义旋转矩阵，包括基本旋转矩阵以及惯性系与会合系之间的旋转矩阵
import numpy as np
import spiceypy as spice
spice.furnsh('/home/ouyangjiahong/codes/CRTBP_code/Spice/Kernel/metakernel/EarthMoon.mk')

def RotationX(rad):
    Rx = np.empty((rad.shape,3,3))
    Rx[:,0,:] = [1, 0, 0]
    Rx[:,1,:] = [0, np.cos(rad), np.sin(rad)]
    Rx[:,2,:] = [0, -np.sin(rad), np.cos(rad)]
    return Rx

def RotationY(rad):
    Ry = np.empty((rad.shape,3,3))
    Ry[:,0,:] = [np.cos(rad), 0, -np.sin(rad)]
    Ry[:,1,:] = [0, 1, 0]
    Ry[:,2,:] = [np.sin(rad), 0, np.cos(rad)]
    return Ry

def RotationZ(rad):
    Rz = np.empty((rad.shape,3,3))
    Rz[:,0,:] = [np.cos(rad), np.sin(rad), 0]
    Rz[:,1,:] = [-np.sin(rad), np.cos(rad), 0]
    Rz[:,2,:] = [0, 0, 1]
    return Rz

# def rot_mat_inertial_to_synodic(R12,V12,mu,et):
#     # 定义惯性系到会合系的旋转矩阵
    
#     # 定义两矢量坐标系统
#     norm_R12 = np.linalg.norm(R12,ord=None,axis=1).reshape((np.size(et),1))
#     cross_R12_V12 = np.cross(R12,V12,axisa=1,axisb=1)
#     norm_cross_R12_V12 = np.linalg.norm(cross_R12_V12,ord=None,axis=1).reshape((np.size(et),1))
    
#     # 惯性系到会合系的旋转矩阵
#     x_caret = R12/norm_R12
#     z_caret = cross_R12_V12/norm_cross_R12_V12
#     y_caret = np.cross(z_caret,x_caret,axisa=1,axisb=1)
    
#     rot_mat_I_S = np.empty((np.size(et), 3, 3))
    
#     rot_mat_I_S[:,0] = x_caret
#     rot_mat_I_S[:,1] = y_caret
#     rot_mat_I_S[:,2] = z_caret
    
#     # 旋转矩阵对时间一阶导
#     x_caret_dot_V12 = np.array([])
    
#     for i in range(0,np.size(et)):
#         x_caret_i = x_caret[i,:]
#         V12_i = V12.T[:,i]
#         x_caret_dot_V12_i = np.matmul(x_caret_i,V12_i)
#         x_caret_dot_V12 = np.append(x_caret_dot_V12,x_caret_dot_V12_i)
   
#     d_x_caret = V12/norm_R12-x_caret*(x_caret_dot_V12.reshape((np.size(et),1))/norm_R12)
#     d_z_caret = np.zeros((np.size(et),3))
#     d_y_caret = np.cross(d_z_caret,x_caret,axisa=1,axisb=1)+np.cross(z_caret,d_x_caret,axisa=1,axisb=1)
    
#     d_rot_mat_I_S = np.empty((np.size(et), 3, 3))
    
#     d_rot_mat_I_S[:,0] = d_x_caret
#     d_rot_mat_I_S[:,1] = d_y_caret
#     d_rot_mat_I_S[:,2] = d_z_caret
    
#     # 会合系瞬时旋转角速度rad/s
#     Om = norm_cross_R12_V12/norm_R12**2
#     Om_vector = np.empty((np.size(et), 3, 1))
#     Om_vector[:,0,0] = 0
#     Om_vector[:,1,0] = 0
#     Om_vector[:,2,0] = Om[:,0]
    
#     # 返回惯性系到会合系的旋转矩阵，旋转矩阵对时间一阶导，会合系旋转角速度矢量
#     return rot_mat_I_S, d_rot_mat_I_S, Om_vector

# def rot_mat_synodic_to_inertial(R12,V12,mu,et):
#     # 定义会合系到惯性系的旋转矩阵
   
#     # 首先求惯性系到会合系的旋转矩阵
#     rot_mat_I_S, d_rot_mat_I_S, Om_vector = rot_mat_inertial_to_synodic(R12,V12,mu,et)
    
#     # 求会合系到惯性系旋转矩阵
#     rot_mat_S_I = np.transpose(rot_mat_I_S,axes=[0,2,1])
    
#     # 该旋转矩阵对时间的一阶导
#     d_rot_mat_S_I = -np.matmul(np.matmul(rot_mat_S_I,d_rot_mat_I_S),rot_mat_S_I)
    
#     # 返回会合系到惯性系的旋转矩阵，旋转矩阵对时间一阶导，会合系旋转角速度矢量
#     return rot_mat_S_I, d_rot_mat_S_I, Om_vector

# # 会合系转惯性系旋转矩阵
# def rot_mat_synodic_to_inertial(R12,V12,mu,utc):
    
#     # 定义两矢量坐标系
#     norm_R12 = np.linalg.norm(R12,ord=None,axis=1).reshape((np.size(utc),1))
#     cross_R12_V12 = np.cross(R12,V12,axisa=1,axisb=1)
#     norm_cross_R12_V12 = np.linalg.norm(cross_R12_V12,ord=None,axis=1).reshape((np.size(utc),1))
    
#     # 旋转系到惯性系的旋转矩阵
#     x_caret = R12/norm_R12
#     z_caret = cross_R12_V12/norm_cross_R12_V12
#     y_caret = np.cross(z_caret,x_caret,axisa=1,axisb=1)
#     rot_mat_S_I = np.empty((np.size(utc), 3, 3))
    
#     rot_mat_S_I[:,0] = x_caret
#     rot_mat_S_I[:,1] = y_caret
#     rot_mat_S_I[:,2] = z_caret
#     rot_mat_S_I = np.transpose(rot_mat_S_I,axes=[0,2,1])
    
#     # 会合系瞬时角速度 rad/s
#     Om = norm_cross_R12_V12/norm_R12**2
#     Om_vector = np.empty((np.size(utc), 3, 1))
#     Om_vector[:,0,0] = 0
#     Om_vector[:,1,0] = 0
#     Om_vector[:,2,0] = Om[:,0]
    
#     # 旋转系到惯性系旋转矩阵对时间一阶导
#     d_rot_mat_S_I = np.empty((np.size(utc), 3, 3))
    
#     d_rot_mat_S_I[:,0,0] =  (Om * rot_mat_S_I[:,0,1].reshape((np.size(utc),1))).reshape((np.size(utc)),1,1)[:,0,0]
#     d_rot_mat_S_I[:,0,1] = -(Om * rot_mat_S_I[:,0,0].reshape((np.size(utc),1))).reshape((np.size(utc)),1,1)[:,0,0]
#     d_rot_mat_S_I[:,0,2] = 0
    
#     d_rot_mat_S_I[:,1,0] = (Om * rot_mat_S_I[:,1,1].reshape((np.size(utc),1))).reshape((np.size(utc)),1,1)[:,0,0]
#     d_rot_mat_S_I[:,1,1] = -(Om * rot_mat_S_I[:,1,0].reshape((np.size(utc),1))).reshape((np.size(utc)),1,1)[:,0,0]
#     d_rot_mat_S_I[:,1,2] = 0
    
#     d_rot_mat_S_I[:,2,0] = (Om * rot_mat_S_I[:,2,1].reshape((np.size(utc),1))).reshape((np.size(utc)),1,1)[:,0,0]
#     d_rot_mat_S_I[:,2,1] = -(Om * rot_mat_S_I[:,2,0].reshape((np.size(utc),1))).reshape((np.size(utc)),1,1)[:,0,0]
#     d_rot_mat_S_I[:,2,2] = 0
    
#     # 完整旋转矩阵
#     Full_rot_mat_S_I = np.empty((np.size(utc), 6, 6))
#     Full_rot_mat_S_I[:,0:3,0:3] = rot_mat_S_I
#     Full_rot_mat_S_I[:,0:3,3:6] = np.zeros((np.size(utc), 3, 3))
#     Full_rot_mat_S_I[:,3:6,0:3] = d_rot_mat_S_I
#     Full_rot_mat_S_I[:,3:6,3:6] = rot_mat_S_I
    
    
#     return Full_rot_mat_S_I,norm_R12,Om_vector