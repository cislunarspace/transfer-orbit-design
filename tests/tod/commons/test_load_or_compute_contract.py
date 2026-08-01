"""``load_or_compute`` 输入契约测试（issue #200）。

覆盖 grill-me 决策 7/8：``args.load`` 必须是字符串路径；新增
``args.auto_latest=True`` 显式 opt-in 才能按 mtime 选择最新族文件。
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tod.commons.input_contract import (
    LoadInputContractError,
)
from tod.commons.constants import FAMILY_FILENAME
from tod.generates.family_io import (
    get_latest_family_file,
    load_or_compute,
)


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    return path


def _touch(path: Path, mtime: float) -> Path:
    p = _write(path)
    os.utime(p, (mtime, mtime))
    return p


def _build_args(load: object = None, auto_latest: bool = False) -> SimpleNamespace:
    return SimpleNamespace(load=load, auto_latest=auto_latest)


class TestLoadInputContract:
    """``load_or_compute`` 显式 opt-in 契约。"""

    def test_load_true_raises_contract_error(self, tmp_path: Path) -> None:
        args = _build_args(load=True)
        with pytest.raises(LoadInputContractError):
            load_or_compute(args, system=MagicMock(), compute_func=lambda s: s,
                            output_dir=str(tmp_path))

    def test_load_truthy_non_string_raises(self, tmp_path: Path) -> None:
        args = _build_args(load=42)  # 任何非字符串 truthy
        with pytest.raises(LoadInputContractError):
            load_or_compute(args, system=MagicMock(), compute_func=lambda s: s,
                            output_dir=str(tmp_path))

    def test_load_none_and_no_auto_latest_falls_through(self, tmp_path: Path) -> None:
        # 两者都未提供 → 进入「计算」分支，compute_func 不被调用，None 返回
        args = _build_args(load=None, auto_latest=False)
        system = MagicMock()
        result_system, result_family = load_or_compute(
            args, system=system, compute_func=lambda s: s,
            output_dir=str(tmp_path),
        )
        assert result_system is system
        assert result_family is None

    def test_auto_latest_true_loads_latest_family(self, tmp_path: Path) -> None:
        # 在 output_dir 下放一个 timestamp 子目录里有 family.json
        out = tmp_path / "output"
        new_dir = out / "20240102"
        old_dir = out / "20240101"
        new_dir.mkdir(parents=True)
        old_dir.mkdir(parents=True)
        new_path = _write(new_dir / FAMILY_FILENAME)
        old_path = _write(old_dir / FAMILY_FILENAME)
        # 显式让 new_dir 更晚 mtime
        os.utime(new_dir, (200.0, 200.0))
        os.utime(old_dir, (100.0, 100.0))

        args = _build_args(load=None, auto_latest=True)
        system = MagicMock()
        fake_family = MagicMock()
        fake_family.__len__ = lambda self: 3
        system_orbit_loader = MagicMock(return_value=fake_family)
        # 拦截 OrbitFamily.load_from_file 走我们的回环
        from e2m2e.data.types.orbit import OrbitFamily

        original = OrbitFamily.load_from_file
        OrbitFamily.load_from_file = staticmethod(  # type: ignore[assignment]
            lambda path, sys: fake_family
        )
        try:
            _, family = load_or_compute(
                args, system=system, compute_func=lambda s: s,
                output_dir=str(out),
            )
            assert family is fake_family
        finally:
            OrbitFamily.load_from_file = original  # type: ignore[assignment]

    def test_explicit_absolute_path_loads(self, tmp_path: Path) -> None:
        family_file = _write(tmp_path / FAMILY_FILENAME)
        args = _build_args(load=str(family_file))
        # 走安全检查需要 family_file 在 output_dir.resolve() 内
        # 因此 output_dir 设成 family_file 所在目录
        from e2m2e.data.types.orbit import OrbitFamily
        fake_family = MagicMock()
        fake_family.__len__ = lambda self: 1
        original = OrbitFamily.load_from_file
        OrbitFamily.load_from_file = staticmethod(  # type: ignore[assignment]
            lambda path, sys: fake_family
        )
        try:
            _, family = load_or_compute(
                args, system=MagicMock(), compute_func=lambda s: s,
                output_dir=str(tmp_path),
            )
            assert family is fake_family
        finally:
            OrbitFamily.load_from_file = original  # type: ignore[assignment]
