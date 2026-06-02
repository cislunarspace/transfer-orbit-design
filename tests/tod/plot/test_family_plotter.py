# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportCallIssue=false, reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false
"""Tests for the unified orbit family plotting orchestrator."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tod.plot.family_plot_orchestrator import (
    FamilyPlotConfig,
    FamilyPlotOrchestrator,
    compute_stability_indices,
    compute_view_bounds,
    resolve_plot_range,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> FamilyPlotConfig:
    defaults = dict(
        family_type="test",
        default_filename="test_family",
        output_subdir="test",
        plane="xy",
    )
    defaults.update(overrides)
    return FamilyPlotConfig(**defaults)


def _make_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        json_file=None,
        start=-1,
        end=-1,
        step=1,
        plot_global_2d=False,
        plot_global_3d=False,
        plot_jacobi_stability=False,
        plot_center="moon",
        plot_elev=20.0,
        plot_azim=-60.0,
        no_show=True,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_mock_orbit() -> MagicMock:
    orbit = MagicMock()
    orbit.states = np.array([[0.9, 0, 0.1, 0, 0, 0], [0.91, 0, 0.11, 0, 0, 0]])
    return orbit


def _make_mock_family(n_orbits: int = 3) -> MagicMock:
    orbits = [_make_mock_orbit() for _ in range(n_orbits)]
    family = MagicMock()
    family.__len__ = MagicMock(return_value=n_orbits)
    family.__getitem__ = MagicMock(side_effect=lambda i: orbits[i])
    family.orbits = orbits
    family.get_jacobi_constants = MagicMock(
        return_value=np.array([3.0 + i * 0.1 for i in range(n_orbits)])
    )
    family.periods = [1.8 + i * 0.1 for i in range(n_orbits)]
    family.add_orbit = MagicMock()
    return family


def _make_fake_orbit_states(x_center: float, y_center: float, z_center: float) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, 100)
    x = x_center + 0.1 * np.cos(t)
    y = y_center + 0.05 * np.sin(t)
    z = z_center + 0.2 * np.sin(2 * t)
    return np.column_stack([x, y, z, np.zeros_like(x), np.zeros_like(x), np.zeros_like(x)])


# ---------------------------------------------------------------------------
# resolve_plot_range
# ---------------------------------------------------------------------------

class TestResolvePlotRange:
    def test_defaults_return_full_range(self) -> None:
        assert resolve_plot_range(-1, -1, 10) == (0, 9)

    def test_start_only_clamps_end(self) -> None:
        assert resolve_plot_range(-1, 5, 10) == (0, 5)

    def test_end_only_clamps_start(self) -> None:
        assert resolve_plot_range(3, -1, 10) == (3, 9)

    def test_both_specified(self) -> None:
        assert resolve_plot_range(2, 7, 10) == (2, 7)

    def test_start_clamped_to_last_index(self) -> None:
        assert resolve_plot_range(15, -1, 10) == (9, 9)

    def test_end_clamped_to_last_index(self) -> None:
        assert resolve_plot_range(-1, 15, 10) == (0, 9)

    def test_both_exceed_n_are_clamped(self) -> None:
        assert resolve_plot_range(8, 20, 10) == (8, 9)

    def test_single_orbit_range(self) -> None:
        assert resolve_plot_range(3, 3, 10) == (3, 3)


# ---------------------------------------------------------------------------
# compute_view_bounds
# ---------------------------------------------------------------------------

class TestComputeViewBounds:
    @pytest.mark.parametrize(
        "x_center,y_center,z_center",
        [(0.85, 0.0, 0.0), (1.15, 0.0, 0.0), (-1.0, 0.0, 0.0)],
    )
    def test_3d_bounds_contain_orbit(self, x_center: float, y_center: float, z_center: float) -> None:
        states = _make_fake_orbit_states(x_center, y_center, z_center)
        xlim_2d, ylim_2d, center_3d, radius_3d = compute_view_bounds(states)
        assert states[:, 0].min() >= center_3d[0] - radius_3d
        assert states[:, 0].max() <= center_3d[0] + radius_3d
        assert states[:, 1].min() >= center_3d[1] - radius_3d
        assert states[:, 1].max() <= center_3d[1] + radius_3d
        assert states[:, 2].min() >= center_3d[2] - radius_3d
        assert states[:, 2].max() <= center_3d[2] + radius_3d

    def test_empty_states_returns_defaults(self) -> None:
        xlim, ylim, center, radius = compute_view_bounds(np.empty((0, 6)))
        assert xlim == (0.8, 1.2)
        assert ylim == (-0.3, 0.3)
        assert center == (1.0, 0.0, 0.0)
        assert radius == 0.4

    def test_2d_bounds_use_x_and_z(self) -> None:
        states = _make_fake_orbit_states(0.85, 0.0, 0.1)
        xlim_2d, ylim_2d, _, _ = compute_view_bounds(states)
        assert xlim_2d[0] < xlim_2d[1]
        assert ylim_2d[0] < ylim_2d[1]
        assert xlim_2d[1] - xlim_2d[0] > 0.1
        assert ylim_2d[1] - ylim_2d[0] > 0.1


# ---------------------------------------------------------------------------
# compute_stability_indices
# ---------------------------------------------------------------------------

class TestComputeStabilityIndices:
    def test_returns_broucke_values(self) -> None:
        mock_orbit = MagicMock()
        mock_family = MagicMock()
        mock_family.__len__ = MagicMock(return_value=2)
        mock_family.__getitem__ = MagicMock(side_effect=[mock_orbit, mock_orbit])

        with patch("tod.plot.family_plot_orchestrator.StabilityAnalysis") as MockSA:
            mock_instance = MockSA.return_value
            mock_instance.compute_stability_index.return_value = {"broucke": 1.5}

            result = compute_stability_indices(mock_family)

        assert result == [1.5, 1.5]
        assert MockSA.call_count == 2


# ---------------------------------------------------------------------------
# Orchestrator.run() orchestration
# ---------------------------------------------------------------------------

class TestOrchestratorRunNoPlots:
    def test_logs_warning_when_all_flags_off(self) -> None:
        config = _make_config()
        args = _make_args()
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch("tod.plot.family_plot_orchestrator.logger") as mock_logger:
            orchestrator.run()
            mock_logger.warning.assert_called_once_with("未选择任何图表，跳过绘制")


class TestOrchestratorStabilityOnDemand:
    def test_skips_stability_when_only_2d(self) -> None:
        """Stability not computed when only --plot-global-2d is on."""
        config = _make_config()
        args = _make_args(plot_global_2d=True)
        family = _make_mock_family()
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch.object(orchestrator, "_load_single_family", return_value=(family, "test")):
            with patch.object(orchestrator, "_render_2d"):
                with patch("tod.plot.family_plot_orchestrator.compute_stability_indices") as mock_stab:
                    with patch("tod.plot.family_plot_orchestrator.FamilyPlotter"):
                        with patch("tod.plot.family_plot_orchestrator.apply_standard_plot_config"):
                            with patch("tod.plot.family_plot_orchestrator.CR3BP_System"):
                                orchestrator.run()

        mock_stab.assert_not_called()

    def test_computes_stability_when_jacobi_stability_on(self) -> None:
        """Stability IS computed when --plot-jacobi-stability is on."""
        config = _make_config()
        args = _make_args(plot_jacobi_stability=True)
        family = _make_mock_family()
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch.object(orchestrator, "_load_single_family", return_value=(family, "test")):
            with patch.object(orchestrator, "_render_jacobi_stability"):
                with patch("tod.plot.family_plot_orchestrator.compute_stability_indices", return_value=[1.0] * 3) as mock_stab:
                    with patch("tod.plot.family_plot_orchestrator.FamilyPlotter"):
                        with patch("tod.plot.family_plot_orchestrator.apply_standard_plot_config"):
                            with patch("tod.plot.family_plot_orchestrator.CR3BP_System"):
                                orchestrator.run()

        mock_stab.assert_called_once()


class TestOrchestratorRouting:
    """Verify run() routes to correct render methods based on flags."""

    def _run_with_flags(self, **flags) -> FamilyPlotOrchestrator:
        config = _make_config()
        args = _make_args(**flags)
        family = _make_mock_family()
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch.object(orchestrator, "_load_single_family", return_value=(family, "test")):
            with patch.object(orchestrator, "_render_2d") as mock_2d:
                with patch.object(orchestrator, "_render_3d") as mock_3d:
                    with patch.object(orchestrator, "_render_jacobi_stability") as mock_stab:
                        with patch("tod.plot.family_plot_orchestrator.compute_stability_indices", return_value=[1.0] * 3):
                            with patch("tod.plot.family_plot_orchestrator.FamilyPlotter"):
                                with patch("tod.plot.family_plot_orchestrator.apply_standard_plot_config"):
                                    with patch("tod.plot.family_plot_orchestrator.CR3BP_System"):
                                        orchestrator.run()
        return orchestrator, mock_2d, mock_3d, mock_stab

    def test_only_2d(self) -> None:
        _, mock_2d, mock_3d, mock_stab = self._run_with_flags(plot_global_2d=True)
        mock_2d.assert_called_once()
        mock_3d.assert_not_called()
        mock_stab.assert_not_called()

    def test_only_3d(self) -> None:
        _, mock_2d, mock_3d, mock_stab = self._run_with_flags(plot_global_3d=True)
        mock_2d.assert_not_called()
        mock_3d.assert_called_once()
        mock_stab.assert_not_called()

    def test_only_stability(self) -> None:
        _, mock_2d, mock_3d, mock_stab = self._run_with_flags(plot_jacobi_stability=True)
        mock_2d.assert_not_called()
        mock_3d.assert_not_called()
        mock_stab.assert_called_once()

    def test_all_three(self) -> None:
        _, mock_2d, mock_3d, mock_stab = self._run_with_flags(
            plot_global_2d=True, plot_global_3d=True, plot_jacobi_stability=True
        )
        mock_2d.assert_called_once()
        mock_3d.assert_called_once()
        mock_stab.assert_called_once()


class TestBuildSubset:
    def test_accesses_correct_range(self) -> None:
        family = _make_mock_family(n_orbits=5)
        config = _make_config()
        args = _make_args()
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch("tod.plot.family_plot_orchestrator.OrbitFamily", return_value=MagicMock()):
            orchestrator._build_subset(family, 1, 3)

        assert family.__getitem__.call_count == 3


class TestLoadFamily:
    def test_raises_system_exit_on_missing_file(self) -> None:
        config = _make_config(default_filename="nonexistent")
        args = _make_args()
        orchestrator = FamilyPlotOrchestrator(config, args)

        with pytest.raises(SystemExit):
            orchestrator._load_single_family(MagicMock(), None, Path("/tmp/test"))

    def test_uses_custom_json_file(self, tmp_path) -> None:
        json_file = tmp_path / "custom_family.json"
        json_file.write_text("{}")
        config = _make_config()
        args = _make_args(json_file=str(json_file))
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch("tod.plot.family_plot_orchestrator.OrbitFamily.load_from_file") as mock_load:
            mock_load.return_value = _make_mock_family()
            family, name = orchestrator._load_single_family(MagicMock(), Path(str(json_file)), tmp_path)

        assert name == "custom_family"
        mock_load.assert_called_once()


# ---------------------------------------------------------------------------
# Regression tests for bug fixes
# ---------------------------------------------------------------------------

class TestElevAzimFromArgs:
    """P2 fix: --plot-elev and --plot-azim from CLI args must reach _render_3d."""

    def test_render_3d_uses_args_elev_azim(self) -> None:
        config = _make_config(
            supports_center_choice=True,
            radius_3d=1.5,
            elev_3d=99.0,
            azim_3d=88.0,
        )
        args = _make_args(plot_global_3d=True, plot_elev=30.0, plot_azim=-45.0)
        family = _make_mock_family()
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch.object(orchestrator, "_load_single_family", return_value=(family, "test")):
            with patch("tod.plot.family_plot_orchestrator.FamilyPlotter") as MockFP:
                mock_plotter = MockFP.return_value
                mock_fig = MagicMock()
                mock_plotter.plot_family_3d.return_value = (mock_fig, MagicMock())
                with patch("tod.plot.family_plot_orchestrator.apply_standard_plot_config"):
                    with patch("tod.plot.family_plot_orchestrator.CR3BP_System"):
                        with patch("tod.plot.family_plot_orchestrator.warnings"):
                            with patch("matplotlib.pyplot.savefig"):
                                with patch("matplotlib.pyplot.close"):
                                    orchestrator.run()

        call_kwargs = mock_plotter.plot_family_3d.call_args
        assert call_kwargs.kwargs["elev"] == 30.0
        assert call_kwargs.kwargs["azim"] == -45.0


class TestSingleOrbitLoad:
    """Unified loader handles both family and single-orbit JSON formats."""

    def test_loads_family_file_when_orbits_key_present(self, tmp_path) -> None:
        json_file = tmp_path / "family.json"
        json_file.write_text('{"orbits": []}')

        config = _make_config()
        args = _make_args(json_file=str(json_file))
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch("tod.plot.family_plot_orchestrator.OrbitFamily.load_from_file") as mock_load:
            mock_load.return_value = _make_mock_family()
            orchestrator._load_single_family(MagicMock(), Path(str(json_file)), tmp_path)

        mock_load.assert_called_once()

    def test_loads_single_orbit_file_when_no_orbits_key(self, tmp_path) -> None:
        json_file = tmp_path / "single_orbit.json"
        json_file.write_text('{"states": []}')

        config = _make_config()
        args = _make_args(json_file=str(json_file))
        orchestrator = FamilyPlotOrchestrator(config, args)

        with patch("tod.plot.family_plot_orchestrator.Orbit.load_from_file") as mock_orbit_load:
            mock_orbit = MagicMock()
            mock_orbit_load.return_value = mock_orbit
            with patch("tod.plot.family_plot_orchestrator.OrbitFamily") as MockOF:
                mock_family = MagicMock()
                MockOF.return_value = mock_family
                orchestrator._load_single_family(MagicMock(), Path(str(json_file)), tmp_path)

        mock_family.add_orbit.assert_called_once_with(mock_orbit)


class TestUnifiedFlags:
    """P1 fix: unified --plot-global-2d/3d and --plot-jacobi-stability flags."""

    def test_config_default_step(self) -> None:
        config = _make_config()
        assert config.step == 5

    def test_build_argparser_accepts_unified_flags(self) -> None:
        from tod.plot.family_plot_orchestrator import build_argparser
        import sys

        parser = build_argparser("test")
        with patch.object(sys, "argv", ["prog", "--plot-global-2d", "--plot-global-3d", "--plot-jacobi-stability"]):
            args = parser.parse_args()
        assert args.plot_global_2d is True
        assert args.plot_global_3d is True
        assert args.plot_jacobi_stability is True
