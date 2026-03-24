"""
DRO-RO 网格搜索

使用方法:
    1. 修改下方 "参数配置" 部分
    2. 确保轨道数据JSON文件存在
    3. 运行: python grid_search.py
"""

import argparse
import json
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import sys

# =============================================================================
# 参数配置
# =============================================================================

# 轨道数据文件路径，单条轨道
DRO_FILE = "output/dro/dro_31_3857029810.json"
RO_FILE = "output/ro/ro_31_3857030320.json"

# 搜索参数
N_DEPARTURE = 200      # 出发点采样数量 (范围: 50-500)
N_ALPHA = 101          # α方向网格点数 (范围: 51-501)
MAX_TRANSFER_TIME = 15.0  # 最大转移时间 (TU)

# alpha 搜索范围
ALPHA_MIN = 0.5
ALPHA_MAX = 2.5

# 筛选阈值
INTERSECTION_THRESHOLD = 0.001   # 相交判定距离 (当距离小于此值认为相交)
MIN_DISTANCE_THRESHOLD = 0.05   # 候选解最小距离阈值

# 碰撞检测半径 (无量纲)
EARTH_RADIUS = 0.01 # //TODO 这里对应多少km？
MOON_RADIUS = 0.01 # //TODO 这里对应多少km？

# 积分配置
DT = 0.001   # 积分步长 //TODO 这个步长的单位是什么？
INTEGRATOR = 'rk4'  # //TODO 这里应该要使用更高精度的积分器

# 物理常数
MU = 1.21506683e-2  # 地月质量比 //TODO 这里的参数应该要从common中选取

print("=" * 70)
print("DRO-RO 转移轨道网格搜索")
print("=" * 70)
print(f"\n搜索配置:")
print(f"  出发点数量: {N_DEPARTURE}")
print(f"  α范围: [{ALPHA_MIN:.2f}, {ALPHA_MAX:.2f}], n={N_ALPHA}")
print(f"  最大转移时间: {MAX_TRANSFER_TIME:.1f} TU")
print(f"  积分步长: {DT}")
print(f"  相交阈值: {INTERSECTION_THRESHOLD:.6f}")
print(f"  候选解阈值: {MIN_DISTANCE_THRESHOLD:.6f}")
print(f"  碰撞半径: 地球={EARTH_RADIUS:.4f}, 月球={MOON_RADIUS:.4f}")

