"""
通用辅助函数

包含在多个脚本中重复使用的函数和常量。
"""

import os
from pathlib import Path

# 常量从 constants.py 集中定义，此处 re-export 以保持向后兼容
from .constants import DU, FAMILY_FILENAME, MU, T_MOON, TU, VU


def find_project_root(start: Path | None = None) -> Path:
    """从给定起点向上遍历，直到找到项目根目录。

    项目根目录定义为包含 pyproject.toml 或 .git 的目录。

    Args:
        start: 起始目录，默认使用调用者的 __file__ 所在目录

    Returns:
        项目根目录的绝对路径

    Raises:
        FileNotFoundError: 无法找到项目根目录
    """
    current = (start or Path(__file__)).resolve().parent
    markers = ("pyproject.toml", ".git")

    for _ in range(20):  # 限制遍历深度，防止无限循环
        if any((current / marker).exists() for marker in markers):
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    raise FileNotFoundError(
        f"无法从 {start or __file__} 找到项目根目录（包含 {markers} 的目录）"
    )


def safe_resolve_within(user_path: str, allowed_root: Path) -> Path | None:
    """安全解析用户路径，验证其位于 allowed_root 内。

    Args:
        user_path: 用户提供的路径字符串
        allowed_root: 允许访问的根目录

    Returns:
        解析后的绝对路径；若路径在 allowed_root 外则返回 None
    """
    resolved = Path(user_path).expanduser().resolve()
    try:
        resolved.relative_to(allowed_root.resolve())
    except ValueError:
        return None
    return resolved


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
        if args.load is True:
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
            # 路径遍历防护：解析真实路径并检查是否在项目根目录内
            resolved_root = Path(output_dir).resolve()
            resolved_path = Path(family_path).resolve()
            try:
                resolved_path.relative_to(resolved_root)
            except ValueError:
                print(f"安全拒绝: {family_path} 不在 {resolved_root} 内")
                return system, None

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
    import shutil
    import time

    ensure_output_dir(output_dir)

    # 生成时间戳作为子目录名（使用 epoch 整数，与生成脚本一致）
    timestamp = str(int(time.time()))
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
