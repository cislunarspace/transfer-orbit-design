"""保存轨道族到文件（自动生成时间戳目录）"""

import datetime
import os
import shutil

from .ensure_output_dir import ensure_output_dir


def save_family_to_file(family_result, output_dir, family_filename="family.json"):
    """保存轨道族到文件

    参数:
        family_result: OrbitFamily对象
        output_dir: 输出目录
        family_filename: 轨道族文件名

    返回:
        family_dir: 保存的目录路径
    """
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
