"""脚本共享的常量、路径与工具包。

本包用于组织相关模块的导入边界，不在导入时执行数值计算。
"""

from .input_contract import (
    InputFileRequest,
    InputResolutionError,
    LoadInputContractError,
    MAX_CANDIDATES_DISPLAYED,
    resolve_input_file,
)
from .paths import ensure_output_dir, find_project_root, safe_resolve_within

__all__ = [
    "InputFileRequest",
    "InputResolutionError",
    "LoadInputContractError",
    "MAX_CANDIDATES_DISPLAYED",
    "ensure_output_dir",
    "find_project_root",
    "resolve_input_file",
    "safe_resolve_within",
]

