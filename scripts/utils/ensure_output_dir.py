"""确保输出目录存在"""

import os


def ensure_output_dir(output_dir="output"):
    """确保输出目录存在

    参数:
        output_dir: 输出目录路径
    """
    os.makedirs(output_dir, exist_ok=True)
