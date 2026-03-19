"""
通用辅助函数

包含在多个 phase1_*.py 脚本中重复使用的函数和常量。
"""

import argparse
import os

# ============================================================
# 系统参数（论文Table 1）
# ============================================================
# 地月系统质量比，μ = m2/(m1+m2)，其中m1为地球质量，m2为月球质量
MU = 1.21506683e-2  # Mass ratio of the Earth–moon system

# 距离单位：1 DU = 384405 km，地月平均距离
DU = 3.84405000e5  # Distance unit km

# 时间单位：1 TU = 4.34811305 天，地月系统的特征时间尺度
TU = 4.34811305  # Time unit days

# 速度单位：1 VU = 1023.23281 m/s，基于DU和TU计算得出
VU = 1023.23281  # Velocity unit m/s

# 月球轨道周期（无量纲）
T_MOON = 2 * 3.141592653589793  # 2π ≈ 6.283

# 轨道族统一文件名
FAMILY_FILENAME = "family.json"


# ============================================================
# 通用辅助函数
# ============================================================
def ensure_output_dir(output_dir="output"):
    """确保输出目录存在"""
    os.makedirs(output_dir, exist_ok=True)


def get_latest_family_file(output_dir, family_filename=FAMILY_FILENAME):
    """获取最新的轨道族数据文件

    参数:
        output_dir: 输出目录路径
        family_filename: 轨道族文件名

    返回:
        最新轨道族文件路径，如果没有则返回None
    """
    if not os.path.exists(output_dir):
        return None

    family_path = os.path.join(output_dir, family_filename)
    if os.path.exists(family_path):
        return family_path

    # 兼容旧格式：查找带时间戳的文件夹
    dirs = [
        d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))
    ]
    if not dirs:
        return None

    # 按修改时间排序，返回最新的
    dirs.sort(key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True)
    latest_dir = dirs[0]
    return os.path.join(output_dir, latest_dir, family_filename)


def load_or_compute(
    args, system, compute_func, output_dir, family_filename=FAMILY_FILENAME
):
    """加载或计算轨道族

    参数:
        args: 命令行参数
        system: CR3BP_System对象
        compute_func: 计算轨道族的函数，接受system参数
        output_dir: 输出目录
        family_filename: 轨道族文件名

    返回:
        system: CR3BP_System对象
        family_result: OrbitFamily对象或None
    """
    import e2m2e
    from e2m2e.core import OrbitFamily

    # 加载模式
    if args.load:
        if args.load == True:
            # 未指定具体文件，查找最新的
            family_path = get_latest_family_file(output_dir, family_filename)
        else:
            # 指定了文件名（可能是完整路径或相对路径）
            if os.path.isabs(args.load):
                family_path = args.load
            else:
                # 可能是 output/phase1_dro/xxx 或直接文件名
                if os.path.exists(args.load):
                    family_path = args.load
                else:
                    family_path = os.path.join(output_dir, args.load, family_filename)

        if family_path and os.path.exists(family_path):
            print(f"加载轨道族数据: {family_path}")
            family_result = OrbitFamily.load_from_file(family_path, system)
            print(f"已加载 {len(family_result)} 条轨道")
            return system, family_result
        else:
            print(f"未找到数据文件: {family_path}")
            print("将重新计算...")

    return system, None


def save_family_to_file(family_result, output_dir, family_filename=FAMILY_FILENAME):
    """保存轨道族到文件（自动生成时间戳目录）

    参数:
        family_result: OrbitFamily对象
        output_dir: 输出目录
        family_filename: 轨道族文件名

    返回:
        family_dir: 保存的目录路径
    """
    import datetime
    import shutil

    ensure_output_dir(output_dir)

    # 生成时间戳作为子目录名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    family_dir = os.path.join(output_dir, timestamp)
    os.makedirs(family_dir, exist_ok=True)

    # 保存轨道族（统一文件）
    family_path = os.path.join(family_dir, family_filename)
    family_result.save_to_file(family_path)
    print(f"轨道族已保存: {family_path}")

    # 同时保存到 latest 链接（创建符号链接的替代方案：复制）
    latest_path = os.path.join(output_dir, family_filename)
    shutil.copy(family_path, latest_path)
    print(f"最新轨道族: {latest_path}")

    return family_dir
