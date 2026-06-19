"""plot_optimize_result_dro_to_geo 论文模式测试。"""

from __future__ import annotations

import numpy as np
import pytest


def test_resolve_figsize_cm_none():
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _resolve_figsize_cm

    assert _resolve_figsize_cm(None) is None


def test_resolve_figsize_cm_single_value():
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _resolve_figsize_cm

    result = _resolve_figsize_cm("8.5")
    assert result is not None
    w, h = result
    assert abs(w - 8.5 / 2.54) < 1e-6
    assert abs(h - 8.5 / 2.54) < 1e-6


def test_resolve_figsize_cm_width_height():
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _resolve_figsize_cm

    result = _resolve_figsize_cm("8.5,6")
    assert result is not None
    w, h = result
    assert abs(w - 8.5 / 2.54) < 1e-6
    assert abs(h - 6 / 2.54) < 1e-6


def test_resolve_figsize_cm_chinese_comma():
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _resolve_figsize_cm

    result = _resolve_figsize_cm("8.5，6")
    assert result is not None
    w, h = result
    assert abs(w - 8.5 / 2.54) < 1e-6
    assert abs(h - 6 / 2.54) < 1e-6


def test_successful_records_filters_correctly():
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _successful_records

    records = [
        {"nlp": {"success": True}},
        {"nlp": {"success": False}},
        {"nlp": {}},
    ]
    result = _successful_records(records)
    assert len(result) == 1
    assert result[0]["nlp"]["success"] is True


def test_select_records_best():
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _select_records

    records = [
        {"nlp": {"objective_value": 2.0}},
        {"nlp": {"objective_value": 1.0}},
        {"nlp": {"objective_value": 3.0}},
    ]
    result = _select_records(records, "best", 0, 500)
    assert len(result) == 1
    assert result[0]["nlp"]["objective_value"] == 1.0


def test_compute_departure_velocity_identity():
    from tod.plot.transfer.common import compute_departure_velocity

    state = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
    v = compute_departure_velocity(state, 1.0)
    np.testing.assert_allclose(v, [0.0, 1.0, 0.0], atol=1e-12)


def test_compute_departure_velocity_alpha_scaling():
    from tod.plot.transfer.common import compute_departure_velocity

    state = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
    v = compute_departure_velocity(state, 0.5)
    np.testing.assert_allclose(v, [0.0, 0.5, 0.0], atol=1e-12)
