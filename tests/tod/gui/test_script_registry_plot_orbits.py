"""Tests for the unified plot_orbits GUI ScriptEntry."""

import importlib.util
from pathlib import Path

import pytest

from tod.gui.script_registry import SCRIPTS

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_raw_entry():
    """Load the raw ScriptEntry from the GUI params file."""
    params_file = _PROJECT_ROOT / "tod" / "gui" / "scripts" / "plot" / "plot_orbits.py"
    spec = importlib.util.spec_from_file_location("_plot_orbits_params", params_file)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.SCRIPT_ENTRY


class TestPlotOrbitsParams:
    """Tests for the unified plot_orbits CLI parameters."""

    CHART_FLAGS = {"--view-2d", "--view-3d", "--jacobi-period-stability"}

    @pytest.fixture
    def plot_orbits(self) -> object:
        """Find plot_orbits ScriptEntry from SCRIPTS."""
        for entry in SCRIPTS.get("plot", []):
            if entry.name == "plot_orbits":
                return entry
        pytest.fail("plot_orbits ScriptEntry not found in plot category")

    @pytest.fixture
    def raw_entry(self) -> object:
        """Load the raw ScriptEntry with all fields including multi_cli_params."""
        return _load_raw_entry()

    def test_has_json_file_param(self, raw_entry) -> None:
        """plot_orbits should have --json-file parameter."""
        multi_flags = [p.flag for p in raw_entry.multi_cli_params]
        assert "--json-file" in multi_flags, "Missing --json-file parameter"

        cli_params = raw_entry.cli_params
        step_param = next((p for p in cli_params if p.flag == "--step"), None)
        assert step_param is not None
        assert step_param.default == ""  # empty default = auto-detect from config

    def test_has_view_2d_param(self, plot_orbits) -> None:
        flags = [p.flag for p in plot_orbits.cli_params]
        assert "--view-2d" in flags

    def test_has_plane_param(self, plot_orbits) -> None:
        flags = [p.flag for p in plot_orbits.cli_params]
        assert "--plane" in flags

    def test_has_plot_center_param(self, plot_orbits) -> None:
        flags = [p.flag for p in plot_orbits.cli_params]
        assert "--plot-center" in flags

    def test_has_plot_elev_param(self, plot_orbits) -> None:
        flags = [p.flag for p in plot_orbits.cli_params]
        assert "--plot-elev" in flags

    def test_json_file_has_orbit_category(self, raw_entry) -> None:
        """--json-file should filter by orbit category."""
        json_param = next(p for p in raw_entry.multi_cli_params if p.flag == "--json-file")
        assert json_param.file_category == "orbit"

    def test_no_env_params(self, plot_orbits) -> None:
        assert len(plot_orbits.env_params) == 0

    def test_output_dir_is_plot(self, raw_entry) -> None:
        assert raw_entry.output_dir == "output/plot"

    def test_script_path_points_to_plot_orbits(self, raw_entry) -> None:
        assert "plot_orbits.py" in raw_entry.script_path

    def test_old_entries_not_in_registry(self) -> None:
        """Old halo/dro/ro entries should no longer appear in the registry."""
        names = [e.name for e in SCRIPTS.get("plot", [])]
        for old_name in ["plot_halo_family", "plot_dro_family", "plot_31_ro_family", "plot_32_ro_family", "plot_aro_family", "plot_rro_family"]:
            assert old_name not in names, f"Old entry {old_name} still found in registry"
