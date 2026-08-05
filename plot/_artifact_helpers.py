"""查找轨道产物的辅助函数。"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "OrbitArtifactNotFoundError",
    "find_latest_single_dro",
]

_SINGLE_DRO_RE = re.compile(r"^dro_\d+\.json$")


class OrbitArtifactNotFoundError(FileNotFoundError):
    """未找到所需的轨道产物文件，异常信息附带可执行的修复指引。"""


def find_latest_single_dro(project_root: Path) -> Path:
    """返回 ``project_root/output/dro`` 下最新的单条 DRO 轨道文件。

    匹配规则：文件名严格符合 ``dro_<digits>.json``，排除旧单轨命名与 family
    集合（如 ``dro_31_family_*.json``）。"最新"按文件修改时间（mtime）判定，
    与 timestamp 文件名解耦，方便测试中通过 ``os.utime`` 直接控制顺序。

    Raises:
        OrbitArtifactNotFoundError: ``output/dro`` 不存在或无匹配文件，
            异常信息会指引用户运行生成脚本或显式传入 ``--dro-file``。
    """
    dro_dir = project_root / "output" / "dro"
    candidates = (
        sorted(
            (p for p in dro_dir.glob("dro_*.json") if _SINGLE_DRO_RE.match(p.name)),
            key=lambda p: (p.stat().st_mtime, p.name),
        )
        if dro_dir.is_dir()
        else []
    )
    if not candidates:
        raise OrbitArtifactNotFoundError(
            f"未找到单条 DRO 轨道文件 (查找位置: {dro_dir})。\n"
            f"  - 运行 DRO 轨道生成脚本；\n"
            f"  - 或通过 --dro-file <path> 显式指定。"
        )
    return candidates[-1].resolve()
