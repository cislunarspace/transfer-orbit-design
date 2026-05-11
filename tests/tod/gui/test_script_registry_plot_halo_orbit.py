"""Tests for plot_halo_orbit ScriptEntry - issue #53."""

import pytest

from tod.gui.script_registry import SCRIPTS, ScriptEntry


class TestPlotHaloOrbitParams:
    """Tests for plot_halo_orbit CLI parameters."""

    CHART_FLAGS = {"--view-2d", "--view-3d", "--jacobi-period"}

    @pytest.fixture
    def plot_halo_orbit(self) -> ScriptEntry:
        """Find plot_halo_orbit ScriptEntry from SCRIPTS."""
        for entry in SCRIPTS.get("Halo", []):
            if entry.name == "plot_halo_orbit":
                return entry
        pytest.fail("plot_halo_orbit ScriptEntry not found in Halo category")

    def test_has_view_2d_param(self, plot_halo_orbit: ScriptEntry) -> None:
        """plot_halo_orbit should have --view-2d bool parameter for 2D XZ plane plot."""
        flags = [p.flag for p in plot_halo_orbit.cli_params]
        assert "--view-2d" in flags, "Missing --view-2d parameter"

        view_2d_param = next(p for p in plot_halo_orbit.cli_params if p.flag == "--view-2d")
        assert view_2d_param.param_type == "bool"
        assert "XZ" in view_2d_param.help or "2D" in view_2d_param.help.lower()

    def test_has_view_3d_param(self, plot_halo_orbit: ScriptEntry) -> None:
        """plot_halo_orbit should have --view-3d bool parameter for 3D plot."""
        flags = [p.flag for p in plot_halo_orbit.cli_params]
        assert "--view-3d" in flags, "Missing --view-3d parameter"

        view_3d_param = next(p for p in plot_halo_orbit.cli_params if p.flag == "--view-3d")
        assert view_3d_param.param_type == "bool"
        assert "3D" in view_3d_param.help

    def test_has_jacobi_period_param(self, plot_halo_orbit: ScriptEntry) -> None:
        """plot_halo_orbit should have --jacobi-period bool parameter for Jacobi-period plot."""
        flags = [p.flag for p in plot_halo_orbit.cli_params]
        assert "--jacobi-period" in flags, "Missing --jacobi-period parameter"

        jacobi_param = next(p for p in plot_halo_orbit.cli_params if p.flag == "--jacobi-period")
        assert jacobi_param.param_type == "bool"
        assert "Jacobi" in jacobi_param.help or "周期" in jacobi_param.help

    def test_chart_params_not_advanced(self, plot_halo_orbit: ScriptEntry) -> None:
        """Chart selection params should be in main area (not advanced)."""
        for param in plot_halo_orbit.cli_params:
            if param.flag in self.CHART_FLAGS:
                assert not param.advanced, f"{param.flag} should not be advanced"

    def test_chart_params_at_end_of_cli_params(self, plot_halo_orbit: ScriptEntry) -> None:
        """Chart selection params should be at the end of cli_params list (as a group)."""
        flags = [p.flag for p in plot_halo_orbit.cli_params]
        chart_params_in_list = [f for f in flags if f in self.CHART_FLAGS]
        assert len(chart_params_in_list) == 3, f"Expected 3 chart params, got {len(chart_params_in_list)}"

        last_three_flags = flags[-3:]
        assert set(last_three_flags) == self.CHART_FLAGS, (
            f"Chart params should be last 3 params. Expected {self.CHART_FLAGS}, got {set(last_three_flags)}"
        )
