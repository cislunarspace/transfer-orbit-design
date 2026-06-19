"""plot_optimize_result_dro_to_geo 论文模式测试。"""

from __future__ import annotations

import argparse
import os
from unittest.mock import patch

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


def test_resolve_dro_input_explicit_file_not_found(tmp_path):
    """--dro-file 指向不存在的文件时应抛出 FileNotFoundError。"""
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _resolve_dro_input

    args = argparse.Namespace(
        dro_file=str(tmp_path / "nonexistent.json"),
        auto_latest_dro=False,
    )
    with pytest.raises(FileNotFoundError, match="DRO 文件不存在"):
        _resolve_dro_input(args)


def test_resolve_dro_input_no_flags_no_env_raises():
    """无 --dro-file、无 --auto-latest-dro、无 env DRO_FILE 时应报错。"""
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _resolve_dro_input

    args = argparse.Namespace(dro_file=None, auto_latest_dro=False)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DRO_FILE", None)
        with pytest.raises(SystemExit):
            _resolve_dro_input(args)


def test_resolve_dro_input_env_dro_file(tmp_path):
    """env DRO_FILE 应作为回退。"""
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _resolve_dro_input

    dro_file = tmp_path / "env_dro.json"
    dro_file.write_text("{}")

    args = argparse.Namespace(dro_file=None, auto_latest_dro=False)
    with patch.dict(os.environ, {"DRO_FILE": str(dro_file)}):
        result = _resolve_dro_input(args)
    assert result == dro_file.resolve()


def test_prepare_transfer_data_missing_departure_state():
    """缺 departure_state 的记录应给出清晰 KeyError。"""
    from tod.plot.transfer.dro_to_geo.plot_optimize_result_dro_to_geo import _prepare_transfer_data

    args = argparse.Namespace(dro_file=None, auto_latest_dro=False)
    rec = {"nlp": {"alpha": 1.0, "transfer_time": 5.0, "delta_v1": 0.01, "delta_v2": 0.005}}
    with pytest.raises(KeyError, match="departure_state"):
        _prepare_transfer_data(args, rec)
