"""跨层共享的路径常量与辅助工具。"""

import logging
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

OUTPUT_DIR: Path = _REPO_ROOT / "output"

logger = logging.getLogger(__name__)

__all__ = [
    "OUTPUT_DIR",
    "detect_kernel_dir",
    "ensure_output_dir",
    "find_project_root",
    "safe_resolve_within",
]


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

    raise FileNotFoundError(f"无法从 {start or __file__} 找到项目根目录（包含 {markers} 的目录）")


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


def ensure_output_dir(output_dir: str = "output") -> None:
    """确保输出目录存在。"""
    os.makedirs(output_dir, exist_ok=True)


def detect_kernel_dir() -> str:
    """探测 SPICE 内核目录。

    优先级：``$SPICE_KERNEL_DIR`` -> ``<repo>/../e2m2e/kernels/``；找不到返回空串。

    e2m2e 改为 pip 安装后，其内部闰秒内核（``.tls``）的自动搜索路径按源码仓库
    布局计算父目录（``parents[3]``），在 site-packages 布局下指向错误位置，导致
    ``SPICE(NOLEAPSECONDS)``、轨道设计失败。规避：调用方须在 import e2m2e 之前把
    本函数返回值写入 ``SPICE_KERNEL_DIR``（e2m2e 的第二搜索路径），见 ``main()``。
    """
    env_val = os.environ.get("SPICE_KERNEL_DIR", "")
    if env_val and Path(env_val).is_dir():
        return env_val

    candidate = _REPO_ROOT.parent / "e2m2e" / "kernels"
    if candidate.is_dir():
        return str(candidate)
    return ""
