"""
``grid_search_dro_to_geo.serialize_result`` 单元测试（issue #71）。

覆盖：
- 4 个 first_* 字段被透传到 JSON。
- e2m2e 旧版本（缺这些字段）下序列化不崩，4 个字段为 None。
"""

from __future__ import annotations

import numpy as np

from tod.transfers.dro_to_geo.grid_search_dro_to_geo import serialize_result


def _make_result_with_first_fields() -> dict:
    """构造一个携带完整 first_* 字段的合成 TransferSearch result。"""
    return {
        "departure_time_index": 3,
        "departure_time": 0.0,
        "alpha": 1.234,
        "transfer_time": 22.998,
        "dv_departure": 0.05,
        "dv_arrival": 0.04,
        "min_distance": 0.0001,
        "intersection_found": True,
        "first_intersection_idx": 42,
        "first_intersection_time": 1.234,
        "first_min_distance_idx": 38,
        "first_min_distance_time": 1.123,
        "collision_found": False,
        "collision_body": None,
        "local_minimum_found": False,
        "local_minimum_distance": float("inf"),
        "status": "success",
        "departure_state": np.array([1.0, 0.0, 0.0, 0.0, 0.5, 0.0]),
    }


def _make_legacy_result_without_first_fields() -> dict:
    """构造一个 e2m2e 旧版本（缺 4 个 first_* 字段）的合成 result。"""
    r = _make_result_with_first_fields()
    for k in (
        "first_intersection_idx",
        "first_intersection_time",
        "first_min_distance_idx",
        "first_min_distance_time",
    ):
        r.pop(k)
    return r


class TestSerializeResultIncludesFirstFeasibilityFields:
    def test_all_four_first_fields_present(self):
        r = _make_result_with_first_fields()
        out = serialize_result(r, is_feasible=True)
        assert out["first_intersection_idx"] == 42
        assert out["first_intersection_time"] == 1.234
        assert out["first_min_distance_idx"] == 38
        assert out["first_min_distance_time"] == 1.123

    def test_is_feasible_uses_param_not_id_lookup(self):
        r = _make_result_with_first_fields()
        out = serialize_result(r, is_feasible=False)
        assert out["is_feasible"] is False
        out2 = serialize_result(r, is_feasible=True)
        assert out2["is_feasible"] is True


class TestSerializeResultHandlesMissingFirstFields:
    def test_legacy_e2m2e_result_serializes_with_none_first_fields(self):
        r = _make_legacy_result_without_first_fields()
        out = serialize_result(r, is_feasible=True)
        assert out["first_intersection_idx"] is None
        assert out["first_intersection_time"] is None
        assert out["first_min_distance_idx"] is None
        assert out["first_min_distance_time"] is None
        # 其他字段应正常
        assert out["alpha"] == 1.234
        assert out["intersection_found"] is True
