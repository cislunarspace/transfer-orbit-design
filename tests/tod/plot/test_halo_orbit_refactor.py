"""Regression tests verifying plot_halo_orbit refactor (issue #47).

Ensures that:
- compute_stability_for_family is not imported
- main() no longer accepts plot4 parameter
- No λmax text remains in titles or labels
- Plot 3 uses plot_jacobi_period instead of plot_jacobi_period_stability
- Plot 4 code block is removed
"""

import importlib
import inspect
import textwrap

import pytest


@pytest.fixture
def halo_module():
    """Import plot_halo_orbit module for inspection."""
    return importlib.import_module("tod.plot.halo.plot_halo_orbit")


class TestNoStabilityImport:
    def test_compute_stability_not_imported(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "compute_stability_for_family" not in source


class TestNoPlot4:
    def test_main_has_no_plot4_param(self, halo_module):
        sig = inspect.signature(halo_module.main)
        assert "plot4" not in sig.parameters

    def test_source_has_no_plot4_variable(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "plot4" not in source

    def test_source_has_no_plot_family_overview_call(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "plot_family_overview" not in source


class TestNoLambdaMax:
    def test_titles_have_no_lambda_max(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "λmax" not in source
        assert "\\u03bbmax" not in source.lower()

    def test_labels_have_no_stability_info(self, halo_module):
        source = inspect.getsource(halo_module)
        # seed label should not contain stability info
        assert "λmax=" not in source
        assert "\\u03bbmax=" not in source.lower()


class TestPlot3UsesJacobiPeriod:
    def test_calls_plot_jacobi_period(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "plot_jacobi_period(" in source

    def test_does_not_call_plot_jacobi_period_stability(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "plot_jacobi_period_stability" not in source


class TestNoStabilityVariables:
    def test_no_stability_subset(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "stability_subset" not in source

    def test_no_stability_sorted(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "stability_sorted" not in source

    def test_no_smin_smax(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "smin" not in source
        assert "smax" not in source

    def test_no_seed_stability(self, halo_module):
        source = inspect.getsource(halo_module)
        assert "seed_stability" not in source
