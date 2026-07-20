"""路径与目录辅助工具。

本模块为 Transfer Orbit Design 的脚本化工作流提供路径解析与输出目录工具。
"""

import logging
import os
from pathlib import Path

__all__ = [
    "ensure_output_dir",
    "find_project_root",
    "safe_resolve_within",
]

logger = logging.getLogger(__name__)


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
