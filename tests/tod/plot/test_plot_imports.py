"""Verify that all plot modules under tod.plot can be imported."""

import importlib

import pytest

PLOT_MODULES = [
    "tod.plot",
    "tod.plot.family_plot_orchestrator",
    "tod.plot.orbit_config_registry",
    "tod.plot.plot_orbits",
    "tod.plot.transfer.dro_to_ro.plot_search_results_dro_to_ro",
    "tod.plot.transfer.dro_to_ro.plot_optimize_result_dro_to_ro",
    "tod.plot.transfer.dro_to_geo.plot_search_results_dro_to_geo",
    "tod.plot.transfer.geo_to_dro.plot_search_results_geo_to_dro",
    "tod.plot.transfer.geo_to_dro.plot_optimize_result_geo_to_dro",
    "tod.plot.ephemeris.plot_ephemeris_correction",
    "tod.plot.ephemeris.plot_halo_ephemeris_correction",
    "tod.plot.inspection.plot_interactive_orbit_inspector",
]


@pytest.mark.parametrize("module_name", PLOT_MODULES)
def test_plot_module_imports(module_name: str) -> None:
    """Each plot module should be importable without error."""
    module = importlib.import_module(module_name)
    assert module is not None, f"importlib.import_module({module_name!r}) returned None"
