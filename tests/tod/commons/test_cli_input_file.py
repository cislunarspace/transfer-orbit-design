"""tod.commons.input_contract 模块的测试。

覆盖 grill-me 20 题决策锁定的 resolver 行为：

- 缺参失败（含候选提示、cap、绝对路径）
- 显式路径成功
- 显式 ``--auto-latest`` 成功（按 mtime 选择）
- 显式路径与 ``--auto-latest`` 互斥
- 显式路径不存在失败
- ``--auto-latest`` 无候选失败
- 候选按 mtime 从新到旧排序
- 候选超 cap 时附加 ``... and N more``
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tod.commons.input_contract import (
    InputFileRequest,
    InputResolutionError,
    MAX_CANDIDATES_DISPLAYED,
    resolve_input_file,
)


def _touch(path: Path, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    os.utime(path, (mtime, mtime))
    return path


def _make_candidates(root: Path, names: list[str], mtimes: list[float]) -> list[Path]:
    assert len(names) == len(mtimes)
    files = []
    for name, mtime in zip(names, mtimes, strict=True):
        files.append(_touch(root / name, mtime))
    return files


def _make_request(
    tmp_path: Path,
    *,
    explicit: Path | None = None,
    auto_latest: bool = False,
    pattern: str = "*.json",
    flag: str = "--file",
    auto_latest_flag: str = "--auto-latest",
) -> InputFileRequest:
    return InputFileRequest(
        explicit_path=explicit,
        auto_latest=auto_latest,
        search_root=tmp_path / "transfer",
        pattern=pattern,
        flag=flag,
        auto_latest_flag=auto_latest_flag,
    )


class TestMissingExplicitInput:
    """缺参失败路径。"""

    def test_missing_without_candidates(self, tmp_path: Path) -> None:
        req = _make_request(tmp_path)
        with pytest.raises(InputResolutionError) as exc_info:
            resolve_input_file(req)
        err = exc_info.value
        assert err.reason == "missing"
        assert err.flag == "--file"
        assert err.auto_latest_flag == "--auto-latest"
        assert err.candidates == []
        assert err.remaining == 0
        assert "--file" in str(err) and "--auto-latest" in str(err)

    def test_missing_lists_candidates_newest_first(self, tmp_path: Path) -> None:
        search_root = tmp_path / "transfer"
        _make_candidates(
            search_root,
            names=["a_1.json", "a_2.json", "a_3.json"],
            mtimes=[100.0, 300.0, 200.0],
        )
        req = _make_request(tmp_path)
        with pytest.raises(InputResolutionError) as exc_info:
            resolve_input_file(req)
        err = exc_info.value
        assert err.reason == "missing"
        # 新→旧顺序：mtime=300 → 200 → 100
        assert [p.name for p in err.candidates] == ["a_2.json", "a_3.json", "a_1.json"]
        assert all(p.is_absolute() for p in err.candidates)

    def test_missing_caps_candidates_and_reports_remaining(self, tmp_path: Path) -> None:
        search_root = tmp_path / "transfer"
        n_total = MAX_CANDIDATES_DISPLAYED + 3
        names = [f"f_{i}.json" for i in range(n_total)]
        # 让索引 0 是 mtime 最新，索引越靠后越旧
        mtimes = [float(n_total - i) for i in range(n_total)]
        _make_candidates(search_root, names=names, mtimes=mtimes)

        req = _make_request(tmp_path)
        with pytest.raises(InputResolutionError) as exc_info:
            resolve_input_file(req)
        err = exc_info.value
        assert len(err.candidates) == MAX_CANDIDATES_DISPLAYED
        assert err.remaining == n_total - MAX_CANDIDATES_DISPLAYED
        assert "f_0.json" == Path(err.candidates[0]).name
        # 候选提示字符串含 ... and N more
        rendered = err.format_candidates()
        assert "... and 3 more" in rendered


class TestExplicitPath:
    """显式路径解析。"""

    def test_existing_path_is_returned_absolute(self, tmp_path: Path) -> None:
        target = _touch(tmp_path / "explicit.json", mtime=1.0)
        req = _make_request(tmp_path, explicit=target)
        resolved = resolve_input_file(req)
        assert resolved == target.resolve()
        assert resolved.is_absolute()

    def test_missing_explicit_path_raises(self, tmp_path: Path) -> None:
        ghost = tmp_path / "nope.json"
        req = _make_request(tmp_path, explicit=ghost)
        with pytest.raises(InputResolutionError) as exc_info:
            resolve_input_file(req)
        assert exc_info.value.reason == "missing-explicit"
        assert "不存在" in str(exc_info.value)


class TestAutoLatest:
    """``--auto-latest`` 显式 opt-in 解析。"""

    def test_auto_latest_picks_newest(self, tmp_path: Path) -> None:
        search_root = tmp_path / "transfer"
        _make_candidates(
            search_root,
            names=["old.json", "mid.json", "new.json"],
            mtimes=[100.0, 200.0, 300.0],
        )
        req = _make_request(tmp_path, auto_latest=True)
        assert resolve_input_file(req).name == "new.json"

    def test_auto_latest_with_no_candidates_raises(self, tmp_path: Path) -> None:
        req = _make_request(tmp_path, auto_latest=True)
        with pytest.raises(InputResolutionError) as exc_info:
            resolve_input_file(req)
        assert exc_info.value.reason == "no-candidates"
        assert "--auto-latest" in str(exc_info.value)


class TestConflict:
    """显式路径与 ``--auto-latest`` 互斥。"""

    def test_explicit_and_auto_latest_conflict(self, tmp_path: Path) -> None:
        target = _touch(tmp_path / "explicit.json", mtime=1.0)
        req = _make_request(tmp_path, explicit=target, auto_latest=True)
        with pytest.raises(InputResolutionError) as exc_info:
            resolve_input_file(req)
        err = exc_info.value
        assert err.reason == "conflict"
        assert err.flag == "--file"
        assert err.auto_latest_flag == "--auto-latest"
        assert "不能同时传入" in str(err)


class TestSearchRootMissing:
    """``search_root`` 目录不存在时行为。"""

    def test_search_root_missing_is_treated_as_no_candidates(
        self, tmp_path: Path
    ) -> None:
        req = _make_request(tmp_path)  # 目录尚未创建
        with pytest.raises(InputResolutionError) as exc_info:
            resolve_input_file(req)
        assert exc_info.value.candidates == []

        # 显式 auto_latest 同样失败
        req_latest = _make_request(tmp_path, auto_latest=True)
        with pytest.raises(InputResolutionError) as exc_info2:
            resolve_input_file(req_latest)
        assert exc_info2.value.reason == "no-candidates"


class TestRequestValidation:
    """``InputFileRequest`` 字段必填校验。"""

    def test_blank_flag_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            InputFileRequest(
                explicit_path=None,
                auto_latest=False,
                search_root=tmp_path,
                pattern="*.json",
                flag="",
                auto_latest_flag="--auto-latest",
            )

    def test_blank_pattern_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            InputFileRequest(
                explicit_path=None,
                auto_latest=False,
                search_root=tmp_path,
                pattern="",
                flag="--file",
                auto_latest_flag="--auto-latest",
            )
