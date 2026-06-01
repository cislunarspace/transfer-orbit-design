# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""Tests for Halo ephemeris correction visualization."""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest

from tod.plot.ephemeris.plot_halo_ephemeris_correction import (
    generate_plots,
    load_halo_correction_data,
    parse_args,
    plot_3d_trajectory_comparison,
    plot_residual_convergence,
    plot_xy_projection_comparison,
)


@pytest.fixture
def sample_correction_json(tmp_path: Path) -> Path:
    """Create a minimal halo ephemeris correction JSON file."""
    data = {
        "orbit_type": "halo",
        "method": "standard",
        "converged": True,
        "iterations": 12,
        "max_residual": 0.001,
        "velocity_residual": 1e-5,
        "residual_history": [10.0, 5.0, 1.0, 0.1, 0.01, 0.001],
        "velocity_residual_history": [1.0, 0.5, 0.1, 0.01, 0.005, 1e-5],
        "reference_epoch": "2025-06-21T11:00:06",
        "n_patch_points": 5,
        "bodies": ["EARTH", "MOON", "SUN"],
        "cr3bp_halo": {
            "source_file": "output/halo/halo_L1_N_test.json",
            "x0": 0.83,
            "vy0": 0.1,
            "z0": 0.23,
            "period_tu": 3.0,
        },
        "position_errors_km": [0.001, 0.0005, 0.0008, 0.0003],
        "corrected_states": [
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            [0.5, 0.5, 0.1, -0.5, 0.5, 0.01],
            [0.0, 1.0, 0.0, -1.0, 0.0, 0.0],
            [-0.5, 0.5, -0.1, -0.5, -0.5, -0.01],
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        ],
        "corrected_times_et": [0.0, 1e6, 2e6, 3e6, 4e6],
        "full_trajectory_states": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]] * 100,
        "full_trajectory_times_et": list(np.linspace(0, 4e6, 100)),
    }
    json_path = tmp_path / "halo_ephemeris_correction_test.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    return json_path


class TestLoadHaloCorrectionData:
    def test_loads_valid_json(self, sample_correction_json: Path):
        result = load_halo_correction_data(sample_correction_json)
        assert result["orbit_type"] == "halo"

    def test_parses_residual_history(self, sample_correction_json: Path):
        result = load_halo_correction_data(sample_correction_json)
        assert result["residual_history"] == [10.0, 5.0, 1.0, 0.1, 0.01, 0.001]

    def test_parses_velocity_residual_history(self, sample_correction_json: Path):
        result = load_halo_correction_data(sample_correction_json)
        assert result["velocity_residual_history"] == [1.0, 0.5, 0.1, 0.01, 0.005, 1e-5]

    def test_converts_states_to_numpy(self, sample_correction_json: Path):
        result = load_halo_correction_data(sample_correction_json)
        assert isinstance(result["corrected_states"], np.ndarray)
        assert result["corrected_states"].shape == (5, 6)

    def test_converts_times_to_numpy(self, sample_correction_json: Path):
        result = load_halo_correction_data(sample_correction_json)
        assert isinstance(result["corrected_times_et"], np.ndarray)
        assert result["corrected_times_et"].shape == (5,)

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_halo_correction_data(Path("/nonexistent/file.json"))

    def test_raises_on_missing_required_key(self, tmp_path: Path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text(json.dumps({"orbit_type": "halo"}), encoding="utf-8")
        with pytest.raises(KeyError):
            load_halo_correction_data(bad_json)


class TestPlotResidualConvergence:
    def test_creates_two_axes(self):
        fig = plt.figure()
        residual_history = [10.0, 5.0, 1.0, 0.1, 0.01, 0.001]
        plot_residual_convergence(fig, residual_history, velocity_residual_history=None)
        assert len(fig.get_axes()) == 2
        plt.close(fig)

    def test_position_axis_is_semilogy(self):
        fig = plt.figure()
        residual_history = [10.0, 5.0, 1.0, 0.1]
        plot_residual_convergence(fig, residual_history, velocity_residual_history=None)
        ax_pos = fig.get_axes()[0]
        assert ax_pos.get_yscale() == "log"
        plt.close(fig)

    def test_plots_position_residuals(self):
        fig = plt.figure()
        residual_history = [10.0, 5.0, 1.0, 0.1]
        plot_residual_convergence(fig, residual_history, velocity_residual_history=None)
        ax_pos = fig.get_axes()[0]
        lines = ax_pos.get_lines()
        assert len(lines) >= 1
        xdata = lines[0].get_xdata()
        assert list(xdata) == [1, 2, 3, 4]
        assert list(lines[0].get_ydata()) == residual_history
        plt.close(fig)

    def test_plots_velocity_residuals_when_provided(self):
        fig = plt.figure()
        pos_history = [10.0, 5.0, 1.0]
        vel_history = [1.0, 0.5, 0.1]
        plot_residual_convergence(fig, pos_history, vel_history)
        ax_vel = fig.get_axes()[1]
        lines = ax_vel.get_lines()
        vel_data_lines = [line for line in lines if line.get_label() and "vel" in line.get_label().lower()]
        assert len(vel_data_lines) >= 1
        plt.close(fig)

    def test_velocity_axis_hidden_when_none(self):
        fig = plt.figure()
        residual_history = [10.0, 5.0, 1.0]
        plot_residual_convergence(fig, residual_history, velocity_residual_history=None)
        ax_vel = fig.get_axes()[1]
        assert not ax_vel.get_visible()
        plt.close(fig)

    def test_tolerance_line_drawn(self):
        fig = plt.figure()
        residual_history = [10.0, 5.0, 1.0, 0.1]
        plot_residual_convergence(
            fig, residual_history, velocity_residual_history=None, tolerance=0.01,
        )
        ax_pos = fig.get_axes()[0]
        lines = ax_pos.get_lines()
        tol_lines = [line for line in lines if line.get_linestyle() == "--"]
        assert len(tol_lines) >= 1
        plt.close(fig)


class TestPlotXYProjectionComparison:
    @pytest.fixture
    def trajectory_data(self) -> dict:
        """Synthetic trajectory data for XY projection tests."""
        t = np.linspace(0, 2 * np.pi, 200)
        pre_xy = np.column_stack([np.cos(t), np.sin(t)])
        post_xy = np.column_stack([1.05 * np.cos(t), 0.95 * np.sin(t)])
        patch_xy = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
        return {
            "pre_xy": pre_xy,
            "post_xy": post_xy,
            "patch_xy": patch_xy,
        }

    def test_creates_two_subplots(self, trajectory_data: dict):
        fig = plt.figure()
        plot_xy_projection_comparison(
            fig,
            pre_xy=trajectory_data["pre_xy"],
            post_xy=trajectory_data["post_xy"],
            patch_xy=trajectory_data["patch_xy"],
        )
        axes = fig.get_axes()
        assert len(axes) == 2
        plt.close(fig)

    def test_left_subplot_is_pre_correction(self, trajectory_data: dict):
        fig = plt.figure()
        plot_xy_projection_comparison(
            fig,
            pre_xy=trajectory_data["pre_xy"],
            post_xy=trajectory_data["post_xy"],
            patch_xy=trajectory_data["patch_xy"],
        )
        ax_pre = fig.get_axes()[0]
        title = ax_pre.get_title().lower()
        assert "before" in title or "pre" in title or "前" in title
        plt.close(fig)

    def test_right_subplot_is_post_correction(self, trajectory_data: dict):
        fig = plt.figure()
        plot_xy_projection_comparison(
            fig,
            pre_xy=trajectory_data["pre_xy"],
            post_xy=trajectory_data["post_xy"],
            patch_xy=trajectory_data["patch_xy"],
        )
        ax_post = fig.get_axes()[1]
        title = ax_post.get_title().lower()
        assert "after" in title or "post" in title or "后" in title
        plt.close(fig)

    def test_patch_points_plotted_as_scatter(self, trajectory_data: dict):
        fig = plt.figure()
        plot_xy_projection_comparison(
            fig,
            pre_xy=trajectory_data["pre_xy"],
            post_xy=trajectory_data["post_xy"],
            patch_xy=trajectory_data["patch_xy"],
        )
        for ax in fig.get_axes():
            collections = ax.collections
            assert len(collections) >= 1
        plt.close(fig)

    def test_axes_labels_present(self, trajectory_data: dict):
        fig = plt.figure()
        plot_xy_projection_comparison(
            fig,
            pre_xy=trajectory_data["pre_xy"],
            post_xy=trajectory_data["post_xy"],
            patch_xy=trajectory_data["patch_xy"],
        )
        for ax in fig.get_axes():
            assert ax.get_xlabel() != ""
            assert ax.get_ylabel() != ""
        plt.close(fig)


class TestPlot3dTrajectoryComparison:
    @pytest.fixture
    def orbit_3d_data(self) -> dict:
        """Synthetic 3D trajectory data."""
        t = np.linspace(0, 2 * np.pi, 200)
        cr3bp_states = np.column_stack([
            np.cos(t),
            np.sin(t),
            0.1 * np.sin(2 * t),
        ])
        eph_states = np.column_stack([
            1.02 * np.cos(t),
            0.98 * np.sin(t),
            0.12 * np.sin(2 * t),
        ])
        patch_states = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
        ])
        return {
            "cr3bp_states": cr3bp_states,
            "eph_states": eph_states,
            "patch_states": patch_states,
        }

    def test_creates_single_3d_axes(self, orbit_3d_data: dict):
        fig = plt.figure()
        plot_3d_trajectory_comparison(
            fig,
            cr3bp_states=orbit_3d_data["cr3bp_states"],
            eph_states=orbit_3d_data["eph_states"],
            patch_states=orbit_3d_data["patch_states"],
            mu=0.01215,
        )
        axes = fig.get_axes()
        assert len(axes) >= 1
        assert axes[0].name == "3d"
        plt.close(fig)

    def test_plots_two_trajectory_lines(self, orbit_3d_data: dict):
        fig = plt.figure()
        plot_3d_trajectory_comparison(
            fig,
            cr3bp_states=orbit_3d_data["cr3bp_states"],
            eph_states=orbit_3d_data["eph_states"],
            patch_states=orbit_3d_data["patch_states"],
            mu=0.01215,
        )
        ax = fig.get_axes()[0]
        lines = ax.get_lines()
        assert len(lines) >= 2
        plt.close(fig)

    def test_marks_earth_and_moon(self, orbit_3d_data: dict):
        fig = plt.figure()
        plot_3d_trajectory_comparison(
            fig,
            cr3bp_states=orbit_3d_data["cr3bp_states"],
            eph_states=orbit_3d_data["eph_states"],
            patch_states=orbit_3d_data["patch_states"],
            mu=0.01215,
        )
        ax = fig.get_axes()[0]
        collections = ax.collections
        # Earth + Moon + patch points = at least 3 scatter plots
        assert len(collections) >= 3
        plt.close(fig)

    def test_marks_patch_points(self, orbit_3d_data: dict):
        fig = plt.figure()
        plot_3d_trajectory_comparison(
            fig,
            cr3bp_states=orbit_3d_data["cr3bp_states"],
            eph_states=orbit_3d_data["eph_states"],
            patch_states=orbit_3d_data["patch_states"],
            mu=0.01215,
        )
        ax = fig.get_axes()[0]
        legend = ax.get_legend()
        assert legend is not None
        legend_texts = [t.get_text().lower() for t in legend.get_texts()]
        assert any("patch" in t for t in legend_texts)
        plt.close(fig)

    def test_has_axis_labels(self, orbit_3d_data: dict):
        fig = plt.figure()
        plot_3d_trajectory_comparison(
            fig,
            cr3bp_states=orbit_3d_data["cr3bp_states"],
            eph_states=orbit_3d_data["eph_states"],
            patch_states=orbit_3d_data["patch_states"],
            mu=0.01215,
        )
        ax = fig.get_axes()[0]
        assert ax.get_xlabel() != ""
        assert ax.get_ylabel() != ""
        plt.close(fig)


class TestGeneratePlots:
    def test_saves_three_png_files(self, sample_correction_json: Path, tmp_path: Path):
        generate_plots(sample_correction_json, output_dir=tmp_path)
        pngs = list(tmp_path.glob("*.png"))
        assert len(pngs) == 3

    def test_png_names_match_chart_types(self, sample_correction_json: Path, tmp_path: Path):
        generate_plots(sample_correction_json, output_dir=tmp_path)
        names = [p.name for p in tmp_path.glob("*.png")]
        assert any("3d" in n for n in names)
        assert any("residual" in n for n in names)
        assert any("xy" in n for n in names)

    def test_returns_output_paths(self, sample_correction_json: Path, tmp_path: Path):
        paths = generate_plots(sample_correction_json, output_dir=tmp_path)
        assert len(paths) == 3
        for p in paths:
            assert p.exists()
            assert p.suffix == ".png"


class TestParseArgs:
    def test_parse_args_returns_namespace(self):
        sys.argv = ["test"]
        args = parse_args()
        assert hasattr(args, "ephemeris_file")
        assert hasattr(args, "output_dir")

    def test_parse_args_with_file(self):
        sys.argv = ["test", "--ephemeris-file", "/tmp/test.json"]
        args = parse_args()
        assert args.ephemeris_file == "/tmp/test.json"

    def test_parse_args_with_output_dir(self):
        sys.argv = ["test", "--output-dir", "/tmp/out"]
        args = parse_args()
        assert args.output_dir == "/tmp/out"
