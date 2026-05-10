"""Tests for tod.plot.transfer.common — shared transfer plot components."""

import json
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest


class TestLoadSearchResults:
    """Test load_search_results handles both list and dict-with-results-key formats."""

    def test_loads_plain_list(self, tmp_path: Path):
        data = [{"alpha": 1.0, "is_feasible": True}, {"alpha": 1.5, "is_feasible": False}]
        p = tmp_path / "results.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        from tod.plot.transfer.common import load_search_results

        rows = load_search_results(p)
        assert len(rows) == 2
        assert rows[0]["alpha"] == 1.0

    def test_loads_dict_with_results_key(self, tmp_path: Path):
        data = {"results": [{"alpha": 1.0}], "meta": {"n": 1}}
        p = tmp_path / "results.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        from tod.plot.transfer.common import load_search_results

        rows = load_search_results(p)
        assert len(rows) == 1

    def test_raises_on_invalid_type(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text('"just a string"', encoding="utf-8")

        from tod.plot.transfer.common import load_search_results

        with pytest.raises(TypeError, match="期望 list"):
            load_search_results(p)


class TestDepartureDeltaVNorm:
    """Test departure_delta_v_norm: velocity perturbation magnitude."""

    def test_alpha_1_returns_zero(self):
        from tod.plot.transfer.common import departure_delta_v_norm

        # 圆轨道上的状态 (x 轴上, 速度沿 y 方向)
        state6 = np.array([0.5, 0.0, 0.0, 0.0, 1.0, 0.0])
        assert departure_delta_v_norm(state6, alpha=1.0) == pytest.approx(0.0, abs=1e-12)

    def test_alpha_2_returns_nonzero(self):
        from tod.plot.transfer.common import departure_delta_v_norm

        state6 = np.array([0.5, 0.0, 0.0, 0.0, 1.0, 0.0])
        dv = departure_delta_v_norm(state6, alpha=2.0)
        assert dv > 0

    def test_small_r_xy_returns_nan(self):
        from tod.plot.transfer.common import departure_delta_v_norm

        # 位置在 z 轴上, r_xy ≈ 0
        state6 = np.array([0.0, 0.0, 0.5, 0.0, 0.0, 1.0])
        assert np.isnan(departure_delta_v_norm(state6, alpha=1.5))


class TestFeasibleAlphaAndDepartureDv:
    """Test feasible_alpha_and_departure_dv filters and extracts."""

    def _sample_rows(self) -> list[dict]:
        return [
            {"alpha": 1.0, "is_feasible": True, "dv_departure": 0.01},
            {"alpha": 1.5, "is_feasible": False, "dv_departure": 0.02},
            {"alpha": 2.0, "is_feasible": True, "dv_departure": 0.03},
        ]

    def test_returns_only_feasible(self):
        from tod.plot.transfer.common import feasible_alpha_and_departure_dv

        alphas, dvs = feasible_alpha_and_departure_dv(self._sample_rows())
        assert len(alphas) == 2
        assert list(alphas) == pytest.approx([1.0, 2.0])
        assert list(dvs) == pytest.approx([0.01, 0.03])

    def test_empty_when_none_feasible(self):
        from tod.plot.transfer.common import feasible_alpha_and_departure_dv

        rows = [{"alpha": 1.0, "is_feasible": False, "dv_departure": 0.01}]
        alphas, dvs = feasible_alpha_and_departure_dv(rows)
        assert len(alphas) == 0

    def test_falls_back_to_state_computation(self):
        from tod.plot.transfer.common import feasible_alpha_and_departure_dv

        # 没有 dv_departure, 但有 departure_state 和 alpha
        rows = [
            {
                "alpha": 1.0,
                "is_feasible": True,
                "departure_state": [0.5, 0.0, 0.0, 0.0, 1.0, 0.0],
            },
        ]
        alphas, dvs = feasible_alpha_and_departure_dv(rows)
        assert len(alphas) == 1
        assert dvs[0] == pytest.approx(0.0, abs=1e-12)  # alpha=1 → dv=0


class TestFeasibleTransferTimeAndDv:
    """Test feasible_transfer_time_and_dv extraction."""

    def _sample_rows(self) -> list[dict]:
        return [
            {
                "is_feasible": True,
                "alpha": 1.0,
                "dv_departure": 0.01,
                "transfer_time": 5.0,
            },
            {
                "is_feasible": True,
                "alpha": 1.5,
                "dv_departure": 0.02,
                "transfer_time": 10.0,
            },
            {
                "is_feasible": False,
                "dv_departure": 0.03,
                "transfer_time": 7.0,
            },
        ]

    def test_extracts_feasible_only(self):
        from tod.plot.transfer.common import feasible_transfer_time_and_dv

        times, dvs = feasible_transfer_time_and_dv(self._sample_rows())
        assert len(times) == 2
        assert list(times) == pytest.approx([5.0, 10.0])
        assert list(dvs) == pytest.approx([0.01, 0.02])

    def test_empty_input(self):
        from tod.plot.transfer.common import feasible_transfer_time_and_dv

        times, dvs = feasible_transfer_time_and_dv([])
        assert len(times) == 0


class TestSelectFeasibleIndices:
    """Test select_feasible_indices: all/best/random/index selection."""

    def _sample_rows(self) -> list[dict]:
        return [
            {"dv_departure": 0.05, "dv_insertion": 0.01},
            {"dv_departure": 0.01, "dv_insertion": 0.01},
            {"dv_departure": 0.03, "dv_insertion": 0.01},
            {"dv_departure": 0.02, "dv_insertion": 0.01},
        ]

    def test_all_returns_all(self):
        from tod.plot.transfer.common import select_feasible_indices

        indices = select_feasible_indices(self._sample_rows(), "all")
        assert indices == [0, 1, 2, 3]

    def test_all_subsamples_when_exceeds_max(self):
        from tod.plot.transfer.common import select_feasible_indices

        indices = select_feasible_indices(
            self._sample_rows(), "all", seed=42, max_indices=2
        )
        assert len(indices) == 2
        assert all(0 <= i < 4 for i in indices)

    def test_best_returns_single_best(self):
        from tod.plot.transfer.common import select_feasible_indices

        indices = select_feasible_indices(self._sample_rows(), "best")
        # dv_total sorted: row1(0.02), row3(0.03), row2(0.04), row0(0.06)
        assert indices == [1]

    def test_best_n_returns_top_n(self):
        from tod.plot.transfer.common import select_feasible_indices

        indices = select_feasible_indices(self._sample_rows(), "best:2")
        assert len(indices) == 2
        # smallest dv_total: row1(0.02), row3(0.03)
        assert 1 in indices
        assert 3 in indices

    def test_random_returns_one(self):
        from tod.plot.transfer.common import select_feasible_indices

        indices = select_feasible_indices(self._sample_rows(), "random", seed=0)
        assert len(indices) == 1
        assert 0 <= indices[0] < 4

    def test_integer_index(self):
        from tod.plot.transfer.common import select_feasible_indices

        indices = select_feasible_indices(self._sample_rows(), "2")
        assert indices == [2]

    def test_out_of_range_raises(self):
        from tod.plot.transfer.common import select_feasible_indices

        with pytest.raises(ValueError, match="超出范围"):
            select_feasible_indices(self._sample_rows(), "10")


class TestPlotAlphaDeltaV:
    """Test plot_alpha_delta_v creates scatter plot with correct axes."""

    def test_scatter_with_data(self):
        from tod.plot.transfer.common import plot_alpha_delta_v

        fig, ax = plt.subplots()
        plot_alpha_delta_v(ax, np.array([1.0, 2.0]), np.array([0.01, 0.02]), "TEST:")
        assert "TEST:" in ax.get_title()
        assert ax.get_xlabel() == "α"
        plt.close(fig)

    def test_empty_shows_no_data_text(self):
        from tod.plot.transfer.common import plot_alpha_delta_v

        fig, ax = plt.subplots()
        plot_alpha_delta_v(ax, np.array([]), np.array([]), "TEST:")
        texts = [t.get_text() for t in ax.texts]
        assert "无可行解" in texts
        plt.close(fig)


class TestPlotTransferTimeDeltaV:
    """Test plot_transfer_time_delta_v creates scatter with colorbar."""

    def test_scatter_with_data(self):
        from tod.plot.transfer.common import plot_transfer_time_delta_v

        fig, ax = plt.subplots()
        plot_transfer_time_delta_v(
            ax, np.array([5.0, 10.0]), np.array([0.01, 0.02]), "TEST:"
        )
        assert "TEST:" in ax.get_title()
        assert ax.get_xlabel() == "转移时间 (天)"
        plt.close(fig)

    def test_empty_shows_no_data_text(self):
        from tod.plot.transfer.common import plot_transfer_time_delta_v

        fig, ax = plt.subplots()
        plot_transfer_time_delta_v(ax, np.array([]), np.array([]), "TEST:")
        texts = [t.get_text() for t in ax.texts]
        assert "无可行解" in texts
        plt.close(fig)


class TestGeoCirclePoints:
    """Test geo_circle_points returns correct circle geometry."""

    def test_returns_two_arrays(self):
        from tod.plot.transfer.common import geo_circle_points

        gx, gy = geo_circle_points()
        assert len(gx) == len(gy)
        assert len(gx) == 200

    def test_centered_near_negative_mu(self):
        from tod.commons.constants import MU

        from tod.plot.transfer.common import geo_circle_points

        gx, gy = geo_circle_points()
        cx = float(np.mean(gx))
        assert abs(cx - (-MU)) < 0.01


class TestSetEqualAspect3D:
    """Test set_equal_aspect_3d sets equal axis ranges."""

    def test_equal_ranges(self):
        from tod.plot.transfer.common import set_equal_aspect_3d

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        pts = np.array([[0, 0, 0], [1, 2, 3]])
        set_equal_aspect_3d(ax, pts)

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        zlim = ax.get_zlim()
        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]
        z_range = zlim[1] - zlim[0]
        assert abs(x_range - y_range) < 0.01
        assert abs(x_range - z_range) < 0.01
        plt.close(fig)
