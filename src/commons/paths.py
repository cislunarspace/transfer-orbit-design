"""跨层共享的路径常量与辅助工具。"""

import logging
import os
from pathlib import Path

from src.commons.kernels import user_kernel_dir

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

OUTPUT_DIR: Path = _REPO_ROOT / "output"

logger = logging.getLogger(__name__)

__all__ = [
    "OUTPUT_DIR",
    "detect_kernel_dir",
    "ensure_output_dir",
    "find_project_root",
    "load_configured_kernel_dir",
    "safe_resolve_within",
    "save_configured_kernel_dir",
    "user_config_dir",
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


def user_config_dir() -> Path:
    """用户配置目录（Windows ``%APPDATA%``，其余平台 XDG 配置目录）。"""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "transfer-orbit-design"


def load_configured_kernel_dir() -> str:
    """读用户上次显式选择/下载的内核目录（配置文件中记录的路径）。

    文件缺失或指向不存在的目录时返回空串。
    """
    p = user_config_dir() / "kernels_dir.txt"
    if p.is_file():
        v = p.read_text(encoding="utf-8").strip()
        if v and Path(v).is_dir():
            return v
    return ""


def save_configured_kernel_dir(path: str | Path) -> None:
    """把用户显式选择/下载的内核目录写入配置文件，供下次启动探测。"""
    d = user_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "kernels_dir.txt").write_text(str(Path(path).resolve()), encoding="utf-8")


def detect_kernel_dir() -> str:
    """探测 SPICE 内核目录。

    优先级：``$SPICE_KERNEL_DIR`` -> 配置文件记录（用户上次选择/下载） ->
    ``<repo>/kernels/`` -> 用户数据目录默认位置 -> ``<repo>/../e2m2e/kernels/``；
    找不到返回空串。

    注意：本函数只判断目录存在，不校验内核完整性（仓库根 ``kernels/`` 只
    提交小内核，行星历 ``.bsp`` 需另行补齐）；完整性判断见
    ``src.commons.kernels.kernel_dir_usable``。

    e2m2e 改为 pip 安装后，其内部闰秒内核（``.tls``）的自动搜索路径按源码仓库
    布局计算父目录（``parents[3]``），在 site-packages 布局下指向错误位置，导致
    ``SPICE(NOLEAPSECONDS)``、轨道设计失败。规避：调用方须在 import e2m2e 之前把
    本函数返回值写入 ``SPICE_KERNEL_DIR``（e2m2e 的第二搜索路径），见 ``main()``。
    """
    env_val = os.environ.get("SPICE_KERNEL_DIR", "")
    if env_val and Path(env_val).is_dir():
        return env_val

    configured = load_configured_kernel_dir()
    if configured:
        return configured

    # 本项目自带 kernels/（小内核入库，.bsp 由 scripts/download_kernels.py 补）
    own = _REPO_ROOT / "kernels"
    if own.is_dir():
        return str(own)

    # 用户数据目录默认位置（GUI 引导下载的落点）
    user_dir = user_kernel_dir()
    if user_dir.is_dir():
        return str(user_dir)

    # 回退：同父目录的 e2m2e 源码仓库内核（开发机历史布局）
    candidate = _REPO_ROOT.parent / "e2m2e" / "kernels"
    if candidate.is_dir():
        return str(candidate)
    return ""
