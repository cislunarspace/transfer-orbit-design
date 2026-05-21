"""``tod.generates.artifacts`` 单元测试（issue #92）。

覆盖最小端到端路径：DRO 单轨道文件的自动发现 + 友好错误信息。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tod.generates.artifacts import (
    OrbitArtifactNotFoundError,
    find_latest_single_dro,
)


def _touch_dro(dro_dir: Path, name: str, mtime: float) -> Path:
    """在 dro_dir 下创建一个空的 DRO JSON 占位文件并设置 mtime。"""
    dro_dir.mkdir(parents=True, exist_ok=True)
    path = dro_dir / name
    path.write_text("{}", encoding="utf-8")
    import os

    os.utime(path, (mtime, mtime))
    return path


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """临时项目根目录，含 output/dro 子目录的占位结构。"""
    (tmp_path / "output" / "dro").mkdir(parents=True)
    return tmp_path


def test_returns_most_recent_single_dro(project_root: Path) -> None:
    dro_dir = project_root / "output" / "dro"
    _touch_dro(dro_dir, "dro_31_1000000000.json", mtime=1_000_000_000.0)
    newest = _touch_dro(dro_dir, "dro_31_2000000000.json", mtime=2_000_000_000.0)
    _touch_dro(dro_dir, "dro_31_1500000000.json", mtime=1_500_000_000.0)

    result = find_latest_single_dro(project_root)

    assert result == newest


def test_excludes_family_files(project_root: Path) -> None:
    dro_dir = project_root / "output" / "dro"
    single = _touch_dro(dro_dir, "dro_31_1000000000.json", mtime=1_000_000_000.0)
    # family 文件 mtime 更新，但应被排除
    _touch_dro(
        dro_dir,
        "dro_31_family_0.141886-0.9-0.005_2000000000.json",
        mtime=2_000_000_000.0,
    )

    result = find_latest_single_dro(project_root)

    assert result == single


def test_missing_directory_raises_with_guidance(tmp_path: Path) -> None:
    # 项目根存在但 output/dro 不存在
    with pytest.raises(OrbitArtifactNotFoundError) as exc_info:
        find_latest_single_dro(tmp_path)

    msg = str(exc_info.value)
    # 错误信息须告诉用户如何生成或传入
    assert "generate_31_dro_orbit" in msg
    assert "--dro-file" in msg


def test_empty_directory_raises_with_guidance(project_root: Path) -> None:
    # output/dro 存在但无任何匹配文件
    with pytest.raises(OrbitArtifactNotFoundError) as exc_info:
        find_latest_single_dro(project_root)

    msg = str(exc_info.value)
    assert "generate_31_dro_orbit" in msg
    assert "--dro-file" in msg
