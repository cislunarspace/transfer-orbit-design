"""
DRO到RO转移轨道绘制脚本

用法:
    python plot_transfer.py --result optimization_result.json --dro dro_family.json --ro ro_31_family.json
"""

import sys
import glob
import argparse
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import matplotlib.pyplot as plt
import e2m2e
from scripts.utils.common import MU

OUTPUT_DIR = project_root / "output"

# =============================================================================
# 1. 解析命令行参数
# =============================================================================
parser = argparse.ArgumentParser(description="绘制DRO到RO转移轨道")
parser.add_argument("--result", type=str, required=True, help="优化结果JSON文件")
parser.add_argument("--dro", type=str, required=True, help="DRO轨道数据JSON文件")
parser.add_argument("--ro", type=str, required=True, help="RO轨道数据JSON文件")
parser.add_argument("--dro-index", type=int, default=0, help="DRO轨道索引")
parser.add_argument("--ro-index", type=int, default=0, help="RO轨道索引")
parser.add_argument("--save", type=str, default=None, help="保存图片路径(不含扩展名)")
args = parser.parse_args()

# =============================================================================
# 2. 加载数据
# =============================================================================
# 加载优化结果
import json

with open(args.result, "r") as f:
    result_data = json.load(f)

# 加载轨道数据
dro_files = glob.glob(args.dro)
ro_files = glob.glob(args.ro)

if not dro_files:
    raise FileNotFoundError(f"未找到DRO文件: {args.dro}")
if not ro_files:
    raise FileNotFoundError(f"未找到RO文件: {args.ro}")

dro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(dro_files[0])
ro_data = e2m2e.core.orbit.OrbitFamily.load_from_file(ro_files[0])

# =============================================================================
# 3. 系统初始化
# =============================================================================
system = e2m2e.core.system.CR3BP_System(mu=MU, primary="earth", secondary="moon")

# 提取轨道
dro_orbit = dro_data.orbits[args.dro_index]
ro_orbit = ro_data.orbits[args.ro_index]

mu = system.mu

# =============================================================================
# 4. 绘制2D转移轨道图
# =============================================================================
fig, ax = plt.subplots(figsize=(10, 10))

# 绘制DRO轨道
dro_states = np.array(dro_orbit.states)
ax.plot(dro_states[:, 0], dro_states[:, 1], "b-", linewidth=1.5, label="DRO", alpha=0.7)

# 绘制RO轨道
ro_states = np.array(ro_orbit.states)
ax.plot(ro_states[:, 0], ro_states[:, 1], "g-", linewidth=1.5, label="RO", alpha=0.7)

# 绘制地球和月球位置
ax.plot(0, 0, "ko", markersize=10, label="Earth")
ax.plot(1 - mu, 0, "o", color="gray", markersize=6, label="Moon")

# 绘制转移轨迹(如果有)
if (
    "transfer_trajectory" in result_data
    and result_data["transfer_trajectory"] is not None
):
    traj = np.array(result_data["transfer_trajectory"])
    ax.plot(traj[:, 0], traj[:, 1], "r-", linewidth=2.5, label="Transfer Trajectory")

    # 标记出发点和插入点
    if len(traj) > 0:
        ax.plot(traj[0, 0], traj[0, 1], "ro", markersize=8, label="Departure")
        ax.plot(traj[-1, 0], traj[-1, 1], "go", markersize=8, label="Insertion")

ax.set_xlabel("x (DU)")
ax.set_ylabel("y (DU)")
ax.set_title("DRO to RO Transfer Trajectory")
ax.set_aspect("equal")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper right")

# 保存图片
if args.save:
    save_path_2d = f"{args.save}_2d.png"
    plt.savefig(save_path_2d, dpi=150, bbox_inches="tight")
    print(f"图像已保存: {save_path_2d}")
else:
    plt.show()

plt.close()

# =============================================================================
# 5. 绘制3D转移轨道图
# =============================================================================
fig = plt.figure(figsize=(12, 10))
ax3d = fig.add_subplot(111, projection="3d")

# 绘制DRO轨道
ax3d.plot(
    dro_states[:, 0],
    dro_states[:, 1],
    dro_states[:, 2],
    "b-",
    linewidth=1.5,
    label="DRO",
    alpha=0.7,
)

# 绘制RO轨道
ax3d.plot(
    ro_states[:, 0],
    ro_states[:, 1],
    ro_states[:, 2],
    "g-",
    linewidth=1.5,
    label="RO",
    alpha=0.7,
)

# 绘制转移轨迹
if (
    "transfer_trajectory" in result_data
    and result_data["transfer_trajectory"] is not None
):
    traj = np.array(result_data["transfer_trajectory"])
    ax3d.plot(
        traj[:, 0],
        traj[:, 1],
        traj[:, 2],
        "r-",
        linewidth=2.5,
        label="Transfer Trajectory",
    )

    # 标记出发点和插入点
    if len(traj) > 0:
        ax3d.scatter(
            traj[0, 0],
            traj[0, 1],
            traj[0, 2],
            c="red",
            s=100,
            marker="o",
            label="Departure",
        )
        ax3d.scatter(
            traj[-1, 0],
            traj[-1, 1],
            traj[-1, 2],
            c="green",
            s=100,
            marker="o",
            label="Insertion",
        )

ax3d.set_xlabel("x (DU)")
ax3d.set_ylabel("y (DU)")
ax3d.set_zlabel("z (DU)")
ax3d.set_title("DRO to RO Transfer Trajectory (3D)")
ax3d.legend()

# 保存图片
if args.save:
    save_path_3d = f"{args.save}_3d.png"
    plt.savefig(save_path_3d, dpi=150, bbox_inches="tight")
    print(f"图像已保存: {save_path_3d}")
else:
    plt.show()

plt.close()

print("绘制完成!")
