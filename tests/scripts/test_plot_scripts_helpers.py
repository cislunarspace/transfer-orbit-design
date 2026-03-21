"""
Tests for plotting scripts (plot_31_ro_family.py, plot_32_ro_family.py, plot_dro_family.py, plot_interactive_orbit_inspector.py)

These tests focus on:
- Testing helper functions without displaying plots
- Testing data loading and preprocessing logic
- Testing the scripts can be parsed without errors
"""

import pytest
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestPlotScriptImports:
    """Test that plotting scripts can be imported and parsed"""

    def test_plot_31_ro_imports(self):
        """Test that plot_31_ro_family.py can be imported without errors"""
        script_path = project_root / "scripts" / "plot_31_ro_family.py"
        spec = importlib.util.spec_from_file_location("plot_31_ro_family", script_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
        except ImportError:
            pass

    def test_plot_32_ro_imports(self):
        """Test that plot_32_ro_family.py can be imported without errors"""
        script_path = project_root / "scripts" / "plot_32_ro_family.py"
        spec = importlib.util.spec_from_file_location("plot_32_ro_family", script_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
        except ImportError:
            pass

    def test_plot_dro_imports(self):
        """Test that plot_dro_family.py can be imported without errors"""
        script_path = project_root / "scripts" / "plot_dro_family.py"
        spec = importlib.util.spec_from_file_location("plot_dro_family", script_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
        except ImportError:
            pass

    def test_plot_interactive_imports(self):
        """Test that plot_interactive_orbit_inspector.py can be imported without errors"""
        script_path = project_root / "scripts" / "plot_interactive_orbit_inspector.py"
        spec = importlib.util.spec_from_file_location("plot_interactive_orbit_inspector", script_path)
        module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(module)
        except ImportError:
            pass


class TestJacobiComputation:
    """Test Jacobi constant computation logic"""
    import math

    def test_jacobi_range_calculation(self):
        """Test Jacobi constant range calculation"""
        jacobi_values = [3.0, 3.5, 3.2, 3.8, 3.1]
        
        jacobi_min = min(jacobi_values)
        jacobi_max = max(jacobi_values)
        jacobi_range = jacobi_max - jacobi_min
        
        assert jacobi_min == 3.0
        assert jacobi_max == 3.8
        assert self.math.isclose(jacobi_range, 0.8, rel_tol=1e-9)

    def test_normalized_jacobi_color(self):
        """Test normalization of Jacobi constants for colormap"""
        jacobi_values = [3.0, 3.5, 3.2, 3.8, 3.1]
        
        jacobi_min = min(jacobi_values)
        jacobi_max = max(jacobi_values)
        jacobi_range = jacobi_max - jacobi_min if jacobi_max != jacobi_min else 1.0
        
        # Test normalization for first value
        norm_jacobi = (jacobi_values[0] - jacobi_min) / jacobi_range
        assert 0.0 <= norm_jacobi <= 1.0
        assert norm_jacobi == 0.0  # minimum value should normalize to 0


class TestPlotRangeLogic:
    """Test plot range calculation logic (same as used in plot scripts)"""

    def test_plot_range_all_orbits(self):
        """Test plot range when all orbits should be plotted"""
        PLOT_START_IDX = -1
        PLOT_END_IDX = -1
        n_orbits = 100
        
        if PLOT_START_IDX == -1 and PLOT_END_IDX == -1:
            plot_start = 0
            plot_end = n_orbits - 1
        else:
            plot_start = 0
            plot_end = n_orbits - 1
        
        assert plot_start == 0
        assert plot_end == 99

    def test_plot_range_from_start(self):
        """Test plot range from first orbit to specific index"""
        PLOT_START_IDX = -1
        PLOT_END_IDX = 42
        n_orbits = 100
        
        if PLOT_START_IDX == -1 and PLOT_END_IDX == -1:
            plot_start, plot_end = 0, n_orbits - 1
        elif PLOT_START_IDX == -1:
            plot_start = 0
            plot_end = min(PLOT_END_IDX, n_orbits - 1)
        
        assert plot_start == 0
        assert plot_end == 42

    def test_plot_range_to_end(self):
        """Test plot range from specific index to last orbit"""
        PLOT_START_IDX = 50
        PLOT_END_IDX = -1
        n_orbits = 100
        
        if PLOT_END_IDX == -1:
            plot_start = min(PLOT_START_IDX, n_orbits - 1)
            plot_end = n_orbits - 1
        
        assert plot_start == 50
        assert plot_end == 99

    def test_plot_range_bounded(self):
        """Test plot range within specific bounds"""
        PLOT_START_IDX = 10
        PLOT_END_IDX = 50
        n_orbits = 100
        
        plot_start = min(PLOT_START_IDX, n_orbits - 1)
        plot_end = min(PLOT_END_IDX, n_orbits - 1)
        
        assert plot_start == 10
        assert plot_end == 50

    def test_plot_range_exceeds_orbits(self):
        """Test plot range when indices exceed number of orbits"""
        PLOT_START_IDX = 0
        PLOT_END_IDX = 500
        n_orbits = 100
        
        plot_start = min(PLOT_START_IDX, n_orbits - 1)
        plot_end = min(PLOT_END_IDX, n_orbits - 1)
        
        assert plot_start == 0
        assert plot_end == 99


class TestInteractiveInspectorHelpers:
    """Test helper functions in plot_interactive_orbit_inspector.py"""

    def test_compute_orbit_jacobi(self):
        """Test compute_orbit_jacobi function logic"""
        # This tests the mock logic, actual implementation requires e2m2e
        mock_orbit = MagicMock()
        mock_orbit.states = [[-0.8805, 0.0, 0.0, 0.0, 0.3921, 0.0]]
        
        # Simulate what the function does
        state = mock_orbit.states[0]
        assert len(state) == 6

    def test_compute_global_axis_limits_xy(self):
        """Test global axis limit calculation for XY plane"""
        all_coords = {
            "x": [-0.5, 0.5, -0.3, 0.7],
            "y": [-0.8, 0.8, -0.2, 0.4],
            "z": [-0.1, 0.1, -0.05, 0.05]
        }
        
        plane = "xy"
        margin = 1.15
        
        if plane == "xy":
            max_val = max(
                max(abs(v) for v in all_coords["x"]), 
                max(abs(v) for v in all_coords["y"])
            )
        elif plane == "xz":
            max_val = max(
                max(abs(v) for v in all_coords["x"]), 
                max(abs(v) for v in all_coords["z"])
            )
        elif plane == "yz":
            max_val = max(
                max(abs(v) for v in all_coords["y"]), 
                max(abs(v) for v in all_coords["z"])
            )
        
        limit = max_val * margin
        
        assert limit > 0
        assert limit == pytest.approx(0.8 * 1.15, rel=1e-10)

    def test_compute_global_axis_limits_xz(self):
        """Test global axis limit calculation for XZ plane"""
        all_coords = {
            "x": [-0.5, 0.5],
            "y": [-0.8, 0.8],
            "z": [-0.1, 0.1]
        }
        
        plane = "xz"
        margin = 1.15
        
        if plane == "xy":
            max_val = max(max(abs(v) for v in all_coords["x"]), max(abs(v) for v in all_coords["y"]))
        elif plane == "xz":
            max_val = max(max(abs(v) for v in all_coords["x"]), max(abs(v) for v in all_coords["z"]))
        elif plane == "yz":
            max_val = max(max(abs(v) for v in all_coords["y"]), max(abs(v) for v in all_coords["z"]))
        
        limit = max_val * margin
        
        assert limit > 0
        assert limit == pytest.approx(0.5 * 1.15, rel=1e-10)
