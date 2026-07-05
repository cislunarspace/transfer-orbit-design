"""
``plot_search_results_dro_to_geo._resolve_truncation`` 单元测试（issue #71）。

覆盖 F1 切片 + D1 fallback 的所有分支：
- intersection_found=True 时使用 first_intersection_*
- intersection_found=False 时使用 first_min_distance_*
- first_*_idx == 0 时 fallback 到不截断（出发即在阈值内）
- 字段缺失时 fallback 到不截断（旧 JSON）
"""

from __future__ import annotations

from pathlib import Path

from tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo import (
    _resolve_dro_file,
    _resolve_truncation,
)


def test_resolve_dro_file_discovers_new_single_dro_name(monkeypatch, tmp_path: Path) -> None:
    import os

    dro_dir = tmp_path / "output" / "dro"
    dro_dir.mkdir(parents=True)
    old_name = dro_dir / "dro_31_300.json"
    family = dro_dir / "dro_31_family_999.json"
    newest = dro_dir / "dro_200.json"
    older = dro_dir / "dro_100.json"
    for path in (old_name, family, older, newest):
        path.write_text("{}", encoding="utf-8")

    # find_latest_single_dro 按 mtime 判定最新；用 os.utime 确保 newest 排最后
    os.utime(older, (1000, 1000))
    os.utime(newest, (2000, 2000))

    monkeypatch.setattr(
        "tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo.project_root",
        tmp_path,
    )

    assert _resolve_dro_file(None) == newest.resolve()


class TestResolveTruncationIntersectionPath:
    def test_uses_first_intersection_when_intersection_found_true(self):
        row = {
            "transfer_time": 22.998,
            "intersection_found": True,
            "first_intersection_idx": 42,
            "first_intersection_time": 1.234,
            "first_min_distance_idx": 38,
            "first_min_distance_time": 1.123,
        }
        k, t = _resolve_truncation(row)
        assert k == 42
        assert t == 1.234


class TestResolveTruncationMinDistancePath:
    def test_uses_first_min_distance_when_intersection_found_false(self):
        row = {
            "transfer_time": 22.998,
            "intersection_found": False,
            "first_intersection_idx": None,
            "first_intersection_time": None,
            "first_min_distance_idx": 55,
            "first_min_distance_time": 2.5,
        }
        k, t = _resolve_truncation(row)
        assert k == 55
        assert t == 2.5


class TestResolveTruncationFallbacks:
    def test_first_idx_zero_falls_back_to_full_length(self):
        """D1: 出发点即在阈值内（geo_to_dro 等场景），不截断。"""
        row = {
            "transfer_time": 22.998,
            "intersection_found": True,
            "first_intersection_idx": 0,
            "first_intersection_time": 0.0,
            "first_min_distance_idx": 0,
            "first_min_distance_time": 0.0,
        }
        k, t = _resolve_truncation(row)
        assert k is None
        assert t == 22.998

    def test_missing_fields_fall_back_to_full_length(self):
        """旧 JSON：4 个字段全缺失，应静默 fallback 到全程。"""
        row = {
            "transfer_time": 22.998,
            "intersection_found": True,
            # 4 个 first_* 字段都缺
        }
        k, t = _resolve_truncation(row)
        assert k is None
        assert t == 22.998

    def test_intersection_path_with_none_idx_falls_back(self):
        """intersection_found=True 但 first_intersection_idx 为 None 时 fallback。
        （理论上 e2m2e 不会写出这种组合，但绘图端要 robust。）"""
        row = {
            "transfer_time": 22.998,
            "intersection_found": True,
            "first_intersection_idx": None,
            "first_intersection_time": None,
            "first_min_distance_idx": 30,
            "first_min_distance_time": 1.5,
        }
        k, t = _resolve_truncation(row)
        # 走 intersection 分支，发现 None → fallback；不会偷偷转去 min_distance 分支
        assert k is None
        assert t == 22.998
