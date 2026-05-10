"""共享日志配置。

各模块通过 ``logging.getLogger(__name__)`` 获取 logger；
外部脚本（如 GUI）可调用 ``configure_logging(level=...)`` 调整级别。
"""

import logging
import sys

_PREFIX = "tod"


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger。"""
    return logging.getLogger(name)


def configure_logging(level: int = logging.INFO) -> None:
    """配置 ``tod`` 命名空间的根 logger。

    Args:
        level: 日志级别，默认 ``logging.INFO``。
    """
    root = logging.getLogger(_PREFIX)
    root.setLevel(level)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(levelname)s [%(name)s] %(message)s")
        )
        root.addHandler(handler)
