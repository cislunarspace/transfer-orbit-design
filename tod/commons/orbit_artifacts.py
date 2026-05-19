"""轨道产物目录 — 发现 ``output/`` 目录下生成的轨道 JSON 文件。

issue #92: 替换转移搜索脚本中硬编码的 DRO timestamp 路径。
当前仅支持单条 DRO 轨道（``dro_31_<timestamp>.json``）。
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "OrbitArtifactNotFoundError",
    "find_latest_single_dro",
]

_SINGLE_DRO_RE = re.compile(r"^dro_31_\d+\.json$")


class OrbitArtifactNotFoundError(FileNotFoundError):
    """未找到所需的轨道产物文件，异常信息附带可执行的修复指引。"""


def find_latest_single_dro(project_root: Path) -> Path:
    """返回 ``project_root/output/dro`` 下最新的单条 3:1 DRO 轨道文件。

    匹配规则：文件名严格符合 ``dro_31_<digits>.json``，排除 family 集合
    （如 ``dro_31_family_*.json``）。"最新"按文件修改时间（mtime）判定，
    与 timestamp 文件名解耦，方便测试中通过 ``os.utime`` 直接控制顺序。

    Raises:
        OrbitArtifactNotFoundError: ``output/dro`` 不存在或无匹配文件，
            异常信息会指引用户运行生成脚本或显式传入 ``--dro-file``。
    """
    dro_dir = project_root / "output" / "dro"
    candidates = (
        sorted(
            (p for p in dro_dir.glob("dro_31_*.json") if _SINGLE_DRO_RE.match(p.name)),
            key=lambda p: p.stat().st_mtime,
        )
        if dro_dir.is_dir()
        else []
    )
    if not candidates:
        raise OrbitArtifactNotFoundError(
            f"未找到单条 3:1 DRO 轨道文件 (查找位置: {dro_dir})。\n"
            f"  - 运行 `python -m tod.generates.cr3bp.dro.generate_31_dro_orbit` 生成；\n"
            f"  - 或通过 --dro-file <path> 显式指定。"
        )
    return candidates[-1].resolve()
