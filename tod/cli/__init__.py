"""CLI 输入文件选择契约包。

集中暴露 ``resolve_input_file`` 等供脚本层复用的工具，遵循 issue #183
「输入文件必须显式选择」领域契约。
"""

from .input_file import (
    InputFileRequest,
    InputResolutionError,
    MAX_CANDIDATES_DISPLAYED,
    resolve_input_file,
)

__all__ = [
    "InputFileRequest",
    "InputResolutionError",
    "MAX_CANDIDATES_DISPLAYED",
    "resolve_input_file",
]
