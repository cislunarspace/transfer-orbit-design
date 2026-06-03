"""CLI 输入文件选择契约。

本模块实现 issue #183 落地后的「输入文件」领域契约：关键输入路径必须由用户
显式指定；只有显式 opt-in（``--auto-latest``）才允许工具按 mtime 选最新
候选；缺参时返回领域错误并附带最多 10 条候选（绝对路径），由调用方决定如何
呈现给用户。

设计原则（来自 grill-me 20 题决策）：

- 模块是纯函数 + 抛领域错误，不直接 ``sys.exit``，不直接 print。
- 显式路径与 ``auto_latest`` 互斥。
- ``auto_latest`` 命中后返回 ``Path``，由 CLI 层负责打印被选中文件。
- 缺参失败时错误信息包含最多 10 条候选（绝对路径，mtime new→old），溢出
  时附加 ``... and N more``。
- mtime 是「最新」的唯一语义。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "InputFileRequest",
    "InputResolutionError",
    "MAX_CANDIDATES_DISPLAYED",
    "resolve_input_file",
]


# 候选提示最多显示条数（grill-me 决策 12）
MAX_CANDIDATES_DISPLAYED = 10


class InputResolutionError(ValueError):
    """输入文件解析失败时抛出的领域错误。

    Attributes:
        flag: 应当由用户传入的 flag 名（例如 ``--file`` / ``--dro-file``）。
        auto_latest_flag: 对应的 ``--auto-latest*`` 显式 opt-in flag 名。
        candidates: 至多 ``MAX_CANDIDATES_DISPLAYED`` 条候选路径（绝对路径），
            已经是 mtime 从新到旧排序。
        remaining: 超出 ``MAX_CANDIDATES_DISPLAYED`` 后被截掉的候选数。
        reason: 失败原因（缺参、互斥、无候选、显式路径不存在等）。
    """

    def __init__(
        self,
        message: str,
        *,
        flag: str | None = None,
        auto_latest_flag: str | None = None,
        candidates: list[Path] | None = None,
        remaining: int = 0,
        reason: str = "missing",
    ) -> None:
        super().__init__(message)
        self.flag = flag
        self.auto_latest_flag = auto_latest_flag
        self.candidates = list(candidates or [])
        self.remaining = remaining
        self.reason = reason

    def format_candidates(self) -> str:
        """生成可粘贴到 stderr 的候选提示字符串。"""
        if not self.candidates and self.remaining == 0:
            return ""
        lines = [str(p) for p in self.candidates]
        if self.remaining > 0:
            lines.append(f"... and {self.remaining} more")
        return "\n".join(lines)


@dataclass(frozen=True)
class InputFileRequest:
    """``resolve_input_file`` 的输入参数。

    Attributes:
        explicit_path: 显式传入的路径（``None`` 表示未提供）。
        auto_latest: 用户是否显式 opt-in 自动选择最新候选。
        search_root: 在其中搜索候选文件的根目录（例如
            ``project_root / "output/transfer"``）。
        pattern: 候选匹配 glob 表达式，相对于 ``search_root``。
        flag: 显式路径对应的 CLI flag 名（用于错误提示）。
        auto_latest_flag: 显式 opt-in flag 名（用于错误提示）。
    """

    explicit_path: Path | None
    auto_latest: bool
    search_root: Path
    pattern: str
    flag: str
    auto_latest_flag: str

    def __post_init__(self) -> None:
        if not self.flag:
            raise ValueError("InputFileRequest.flag 不能为空")
        if not self.auto_latest_flag:
            raise ValueError("InputFileRequest.auto_latest_flag 不能为空")
        if not self.pattern:
            raise ValueError("InputFileRequest.pattern 不能为空")
        if self.search_root is None:
            raise ValueError("InputFileRequest.search_root 不能为空")


def _gather_candidates(search_root: Path, pattern: str) -> list[Path]:
    """在 ``search_root`` 下按 ``pattern`` 收集候选并按 mtime 从新到旧排序。"""
    if not search_root.is_dir():
        return []
    candidates = [p.resolve() for p in search_root.glob(pattern)]
    candidates.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return candidates


def _cap_candidates(candidates: list[Path]) -> tuple[list[Path], int]:
    """截取前 ``MAX_CANDIDATES_DISPLAYED`` 条候选并返回溢出数量。"""
    if len(candidates) <= MAX_CANDIDATES_DISPLAYED:
        return list(candidates), 0
    kept = list(candidates[:MAX_CANDIDATES_DISPLAYED])
    return kept, len(candidates) - MAX_CANDIDATES_DISPLAYED


def resolve_input_file(request: InputFileRequest) -> Path:
    """按 ``InputFileRequest`` 解析出最终输入文件路径。

    解析规则：

    1. 显式路径与 ``auto_latest=True`` 同时存在 → ``InputResolutionError``，
       ``reason="conflict"``。
    2. ``explicit_path`` 提供：
       - 必须存在且是文件，否则 ``reason="missing-explicit"``。
       - 返回 ``explicit_path.resolve()``。
    3. ``auto_latest=True``：在 ``search_root`` 下按 ``pattern`` 匹配，
       按 mtime new→old 排序，取第一条；若没有候选则
       ``reason="no-candidates"``。
    4. 两者都未提供：抛 ``InputResolutionError``，``reason="missing"``，
       错误信息附带候选（若有）。
    """
    if request.explicit_path is not None and request.auto_latest:
        raise InputResolutionError(
            f"{request.flag} 与 {request.auto_latest_flag} 不能同时传入",
            flag=request.flag,
            auto_latest_flag=request.auto_latest_flag,
            reason="conflict",
        )

    if request.explicit_path is not None:
        resolved = request.explicit_path.expanduser().resolve()
        if not resolved.is_file():
            raise InputResolutionError(
                f"{request.flag} 指向的文件不存在: {resolved}",
                flag=request.flag,
                reason="missing-explicit",
            )
        return resolved

    candidates = _gather_candidates(request.search_root, request.pattern)

    if request.auto_latest:
        if not candidates:
            raise InputResolutionError(
                f"{request.auto_latest_flag} 启用但 {request.search_root} 下无匹配 "
                f"{request.pattern} 的候选",
                flag=request.flag,
                auto_latest_flag=request.auto_latest_flag,
                reason="no-candidates",
            )
        return candidates[0]

    shown, remaining = _cap_candidates(candidates)
    raise InputResolutionError(
        f"需要显式输入文件: 传 {request.flag} <path> 或 {request.auto_latest_flag}",
        flag=request.flag,
        auto_latest_flag=request.auto_latest_flag,
        candidates=shown,
        remaining=remaining,
        reason="missing",
    )
