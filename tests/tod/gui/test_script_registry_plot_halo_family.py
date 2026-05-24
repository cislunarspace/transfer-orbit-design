"""Tests for plot_halo_family ScriptEntry - issue #104."""

import importlib.util
from pathlib import Path

import pytest

from tod.gui.script_registry import SCRIPTS, ScriptEntry

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _load_raw_entry() -> ScriptEntry:
    """Load the raw ScriptEntry from the GUI params file."""
    params_file = _PROJECT_ROOT / "tod" / "gui" / "scripts" / "plot" / "halo" / "plot_halo_family.py"
    spec = importlib.util.spec_from_file_location("_plot_halo_family_params", params_file)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.SCRIPT_ENTRY


class TestPlotHaloFamilyParams:
    """Tests for plot_halo_family CLI parameters."""

    CHART_FLAGS = {"--view-2d", "--view-3d", "--jacobi-period-stability"}

    @pytest.fixture
    def plot_halo_family(self) -> ScriptEntry:
        """Find plot_halo_family ScriptEntry from SCRIPTS."""
        for entry in SCRIPTS.get("plot", []):
            if entry.name == "plot_halo_family":
                return entry
        pytest.fail("plot_halo_family ScriptEntry not found in plot category")

    @pytest.fixture
    def raw_entry(self) -> ScriptEntry:
        """Load the raw ScriptEntry with all fields including multi_cli_params."""
        return _load_raw_entry()

    def test_has_json_file_param(self, raw_entry: ScriptEntry) -> None:
        """plot_halo_family should have --json-file parameter with file_category=halo."""
        multi_flags = [p.flag for p in raw_entry.multi_cli_params]
        assert "--json-file" in multi_flags, "Missing --json-file parameter"

        json_param = next(p for p in raw_entry.multi_cli_params if p.flag == "--json-file")
        assert json_param.file_category == "halo"

    def test_has_start_param(self, plot_halo_family: ScriptEntry) -> None:
        """plot_halo_family should have --start parameter."""
        flags = [p.flag for p in plot_halo_family.cli_params]
        assert "--start" in flags

    def test_has_end_param(self, plot_halo_family: ScriptEntry) -> None:
        """plot_halo_family should have --end parameter."""
        flags = [p.flag for p in plot_halo_family.cli_params]
        assert "--end" in flags

    def test_has_view_2d_param(self, plot_halo_family: ScriptEntry) -> None:
        """plot_halo_family should have --view-2d bool parameter for 2D XZ plane plot."""
        flags = [p.flag for p in plot_halo_family.cli_params]
        assert "--view-2d" in flags, "Missing --view-2d parameter"

        view_2d_param = next(p for p in plot_halo_family.cli_params if p.flag == "--view-2d")
        assert view_2d_param.param_type == "bool"
        assert "XZ" in view_2d_param.help or "2D" in view_2d_param.help.lower()

    def test_has_view_3d_param(self, plot_halo_family: ScriptEntry) -> None:
        """plot_halo_family should have --view-3d bool parameter for 3D plot."""
        flags = [p.flag for p in plot_halo_family.cli_params]
        assert "--view-3d" in flags, "Missing --view-3d parameter"

        view_3d_param = next(p for p in plot_halo_family.cli_params if p.flag == "--view-3d")
        assert view_3d_param.param_type == "bool"
        assert "3D" in view_3d_param.help

    def test_has_jacobi_period_stability_param(self, plot_halo_family: ScriptEntry) -> None:
        """plot_halo_family should have --jacobi-period-stability bool parameter."""
        flags = [p.flag for p in plot_halo_family.cli_params]
        assert "--jacobi-period-stability" in flags, "Missing --jacobi-period-stability parameter"

        jacobi_param = next(p for p in plot_halo_family.cli_params if p.flag == "--jacobi-period-stability")
        assert jacobi_param.param_type == "bool"
        assert "Jacobi" in jacobi_param.help or "周期" in jacobi_param.help

    def test_no_env_params(self, plot_halo_family: ScriptEntry) -> None:
        """plot_halo_family should not use EnvParam (only CliParam)."""
        assert len(plot_halo_family.env_params) == 0, (
            "plot_halo_family should use CliParam instead of EnvParam"
        )

    def test_chart_params_not_advanced(self, plot_halo_family: ScriptEntry) -> None:
        """Chart selection params should be in main area (not advanced)."""
        for param in plot_halo_family.cli_params:
            if param.flag in self.CHART_FLAGS:
                assert not param.advanced, f"{param.flag} should not be advanced"

    def test_chart_params_at_end_of_cli_params(self, plot_halo_family: ScriptEntry) -> None:
        """Chart selection params should be at the end of cli_params list (as a group)."""
        flags = [p.flag for p in plot_halo_family.cli_params]
        chart_params_in_list = [f for f in flags if f in self.CHART_FLAGS]
        assert len(chart_params_in_list) == 3, f"Expected 3 chart params, got {len(chart_params_in_list)}"

        last_three_flags = flags[-3:]
        assert set(last_three_flags) == self.CHART_FLAGS, (
            f"Chart params should be last 3 params. Expected {self.CHART_FLAGS}, got {set(last_three_flags)}"
        )
