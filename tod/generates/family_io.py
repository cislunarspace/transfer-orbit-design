"""轨道族 I/O：加载/保存 family.json、``load_or_compute`` 编排。

本模块承载与轨道族持久化相关的领域逻辑（依赖 ``e2m2e.OrbitFamily``），
从 ``tod/commons/common.py`` 迁移而来（issue #293 / 发现项 F4）：
``common.py`` 仅保留与轨道无关的 FS/路径 helper。
"""

import logging
import os
from pathlib import Path

from tod.commons.input_contract import LoadInputContractError
from tod.commons.paths import ensure_output_dir
from tod.commons.constants import FAMILY_FILENAME

__all__ = [
    "get_latest_family_file",
    "load_or_compute",
    "save_family_to_file",
]

logger = logging.getLogger(__name__)

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
    latest_path = os.path.join(output_dir, latest_dir, family_filename)
    return latest_path if os.path.exists(latest_path) else None

def load_or_compute(
    args, system, compute_func, output_dir, family_filename=FAMILY_FILENAME
):
    """加载或计算轨道族。

    参数:
        args: 命令行参数；需提供 ``args.load`` 与 ``args.auto_latest``：
            - 两者皆为 falsy：进入「计算」分支，``compute_func`` 在调用方
              控制。
            - ``args.load`` 是字符串路径：直接加载该路径。
            - ``args.auto_latest`` 为 True 且 ``args.load`` 为 falsy：按
              mtime 最新加载 ``get_latest_family_file`` 命中的族文件。
            - ``args.load`` 为真但既不是字符串路径、也未传
              ``args.auto_latest``：抛 ``LoadInputContractError``。这一约束
              由 issue #183 落地：公共 helper 不再接受「隐式选最新」。
        system: CR3BP_System对象
        compute_func: 计算轨道族的函数，接受system参数
        output_dir: 输出目录
        family_filename: 轨道族文件名

    返回:
        system: CR3BP_System对象
        family_result: OrbitFamily对象或None

    Raises:
        LoadInputContractError: ``args.load`` 触发新契约失败。
    """
    from e2m2e.core import OrbitFamily

    auto_latest = bool(getattr(args, "auto_latest", False))
    load_value = getattr(args, "load", None)

    # 加载模式：路径字符串 或 显式 auto_latest
    if load_value or auto_latest:
        if load_value is True or (load_value and not isinstance(load_value, str)):
            raise LoadInputContractError(
                "args.load 必须是显式路径字符串，或同时设置 args.auto_latest=True "
                "以显式 opt-in 自动选择最新族文件"
            )

        if auto_latest and not load_value:
            family_path = get_latest_family_file(output_dir, family_filename)
        else:
            load_str = str(load_value)
            if os.path.isabs(load_str):
                family_path = load_str
            elif os.path.exists(load_str):
                family_path = load_str
            else:
                family_path = os.path.join(output_dir, load_str, family_filename)

        if family_path and os.path.exists(family_path):
            # 路径遍历防护：解析真实路径并检查是否在项目根目录内
            resolved_root = Path(output_dir).resolve()
            resolved_path = Path(family_path).resolve()
            try:
                resolved_path.relative_to(resolved_root)
            except ValueError:
                logger.warning("安全拒绝: %s 不在 %s 内", family_path, resolved_root)
                return system, None

            logger.info("加载轨道族数据: %s", family_path)
            family_result = OrbitFamily.load_from_file(family_path, system)
            logger.info("已加载 %d 条轨道", len(family_result))
            return system, family_result
        else:
            logger.warning("未找到数据文件: %s", family_path)
            logger.info("将重新计算...")

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
    logger.info("轨道族已保存: %s", family_path)

    # 同时保存到 latest 链接（创建符号链接的替代方案：复制）
    latest_path = os.path.join(output_dir, family_filename)
    shutil.copy(family_path, latest_path)
    logger.info("最新轨道族: %s", latest_path)

    return family_dir
