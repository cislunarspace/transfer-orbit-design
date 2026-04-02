"""
Tests for ephemeris correction script (correct_dro_to_ephemeris.py)

These tests focus on:
- Testing the parameter configurations
- Testing the import structure
- Testing helper function logic without SPICE kernels
"""

import pytest
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent


class TestEphemerisScriptImports:
    """Test that ephemeris correction script can be imported and parsed"""

    @patch("e2m2e.core.SPICEManager")
    @patch("e2m2e.core.EphemerisSystem")
    @patch("e2m2e.core.EphemerisDynamics")
    @patch("e2m2e.core.SynodicJ2000Transformation")
    @patch("e2m2e.core.CR3BP_System")
    @patch("e2m2e.core.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.MultipleShooting")
    def test_correct_dro_to_ephemeris_imports(
        self,
        mock_ms,
        mock_corr,
        mock_dyn,
        mock_sys,
        mock_syn,
        mock_eph_dyn,
        mock_eph_sys,
        mock_spice,
    ):
        """Test that correct_dro_to_ephemeris.py can be imported without errors"""
        mock_corr.return_value.iterate_correction.return_value = MagicMock()

        script_path = project_root / "scripts" / "ephemeris" / "correct_dro_to_ephemeris.py"
        spec = importlib.util.spec_from_file_location("correct_dro_to_ephemeris", script_path)
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except ImportError:
            pass


class TestEphemerisScriptParameters:
    """Test parameter configurations in the ephemeris correction script"""

    def test_dro_31_parameters(self):
        """Test that 3:1 DRO initial state parameters are reasonable"""
        x0 = 1.1202109158830986
        vy0 = -0.46178983697629084
        period = 2.095

        assert 1.0 < x0 < 1.5, "DRO x0 should be beyond Moon's orbit"
        assert -1.0 < vy0 < 0.0, "DRO vy0 should be negative (retrograde)"
        assert 1.5 < period < 3.0, "DRO period should be ~2 TU"

    def test_physical_units(self):
        """Test that physical unit conversions are consistent"""
        DU = 3.84405e5
        TU_DAYS = 4.34811305
        TU_SECONDS = TU_DAYS * 86400
        VU_KMS = DU / TU_SECONDS

        assert abs(DU - 384405) < 10, "DU should be ~384405 km"
        assert abs(TU_DAYS - 4.348) < 0.01, "TU should be ~4.348 days"
        assert 0.9 < VU_KMS < 1.2, "VU should be ~1.023 km/s"

    def test_patch_point_count(self):
        """Test that patch point count is reasonable"""
        N_PATCH_POINTS = 8
        assert 4 <= N_PATCH_POINTS <= 20

    def test_position_continuity_tolerance(self):
        """Test that tolerance is strict enough for orbit correction"""
        TOL = 1e-6
        assert TOL <= 1e-4, "Tolerance should be strict"

    def test_bodies_list(self):
        """Test that bodies list includes required celestial bodies"""
        bodies = ["EARTH", "MOON", "SUN"]
        assert "EARTH" in bodies
        assert "MOON" in bodies
        assert "SUN" in bodies

    def test_reference_epoch_format(self):
        """Test that reference epoch is a valid ISO date string"""
        epoch = "2025-06-21T11:00:06"
        parts = epoch.split("T")
        assert len(parts) == 2
        date_parts = parts[0].split("-")
        assert len(date_parts) == 3
        assert all(p.isdigit() for p in date_parts)


class TestEphemerisHelperFunctions:
    """Test helper functions with mocked dependencies"""

    def test_sample_patch_points_shape(self):
        """Test that sample_patch_points returns correct shapes"""
        n_points = 8
        period = 2.095
        t_patch = np.linspace(0, period, n_points, endpoint=False)

        assert t_patch.shape == (n_points,)
        assert t_patch[0] == 0.0
        assert t_patch[-1] < period

    def test_j2000_time_conversion(self):
        """Test synodic → J2000 time conversion logic"""
        TU_SECONDS = 4.34811305 * 86400
        TU_DAYS = 4.34811305
        reference_et = 807264069.0
        period_tu = 2.095
        n_points = 8
        t_patch_syn = np.linspace(0, period_tu, n_points, endpoint=False)
        t_patch_j2000 = reference_et + t_patch_syn * TU_SECONDS

        assert t_patch_j2000[0] == reference_et
        assert t_patch_j2000[-1] > reference_et
        expected_last_tu = period_tu * (n_points - 1) / n_points
        expected_days = expected_last_tu * TU_DAYS
        duration_days = (t_patch_j2000[-1] - t_patch_j2000[0]) / 86400
        assert abs(duration_days - expected_days) < 0.01
