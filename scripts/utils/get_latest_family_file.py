"""获取最新的轨道族数据文件"""

import os


def get_latest_family_file(output_dir, family_filename="family.json"):
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
