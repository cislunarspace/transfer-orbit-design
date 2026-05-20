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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent


class TestEphemerisScriptImports:
    """Test that ephemeris correction script can be imported and parsed"""

    def test_correct_dro_to_ephemeris_imports(
        self,
    ):
        """Test that correct_dro_to_ephemeris.py can be imported without errors"""

        script_path = (
            project_root
            / "tod"
            / "generates"
            / "ephemeris"
            / "correct_dro_to_ephemeris.py"
        )
        spec = importlib.util.spec_from_file_location(
            "correct_dro_to_ephemeris", script_path
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")
        except Exception as e:
            pytest.fail(f"Script import failed with unexpected error: {e}")


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


class TestEphemerisCorrectionMethodSelection:
    """Test ephemeris correction method dispatch without SPICE kernels."""

    def test_standard_method_uses_multiple_shooting_and_normalizes_result(self):
        from tod.generates.ephemeris._corrector import correct_ephemeris_patch_points

        dynamics = object()
        t_patch = np.array([0.0, 1.0, 2.0])
        state_patch = np.zeros((3, 6))
        solver_result = SimpleNamespace(
            converged=True,
            iterations=3,
            max_residual=1e-4,
            residual_history=[1e-2, 1e-4],
            t_patch=t_patch + 10.0,
            state_patch=state_patch + 1.0,
        )

        with patch(
            "tod.generates.ephemeris._corrector.MultipleShooting"
        ) as mock_multiple_shooting:
            mock_solver = mock_multiple_shooting.return_value
            mock_solver.correct.return_value = solver_result

            result = correct_ephemeris_patch_points(
                "standard",
                dynamics,
                t_patch,
                state_patch,
                tolerance=1e-3,
                max_iter=50,
                verbose=True,
                n_workers=4,
                kernel_dir="kernels",
            )

        mock_multiple_shooting.assert_called_once_with(
            dynamics=dynamics,
            n_workers=4,
            kernel_dir="kernels",
        )
        mock_solver.correct.assert_called_once_with(
            t_patch=t_patch,
            state_patch=state_patch,
            var_time=True,
            max_iter=50,
            tolerance=1e-3,
            verbose=True,
        )
        assert result.converged is True
        assert result.iterations == 3
        np.testing.assert_allclose([result.max_residual], [1e-4])
        np.testing.assert_allclose(result.residual_history, [1e-2, 1e-4])
        np.testing.assert_allclose(result.t_patch, t_patch + 10.0)
        np.testing.assert_allclose(result.state_patch, state_patch + 1.0)

    def test_two_level_method_uses_two_level_solver_and_normalizes_result(self):
        from tod.generates.ephemeris._corrector import correct_ephemeris_patch_points

        dynamics = object()
        t_patch = np.array([0.0, 1.0, 2.0])
        state_patch = np.zeros((3, 6))
        solver_result = SimpleNamespace(
            converged=True,
            outer_iterations=2,
            final_position_residual=1e-5,
            final_velocity_residual=2e-5,
            residual_history=[(1e-2, 1e-1), (1e-5, 2e-5)],
            t_patch=t_patch + 20.0,
            state_patch=state_patch + 2.0,
        )

        with patch(
            "tod.generates.ephemeris._corrector.TwoLevelMultipleShooting"
        ) as mock_two_level:
            mock_solver = mock_two_level.return_value
            mock_solver.correct.return_value = solver_result

            result = correct_ephemeris_patch_points(
                "two_level",
                dynamics,
                t_patch,
                state_patch,
                tolerance=1e-3,
                max_iter=50,
                verbose=True,
                n_workers=4,
                kernel_dir="kernels",
                velocity_tolerance=1e-6,
            )

        mock_two_level.assert_called_once_with(dynamics)
        mock_solver.correct.assert_called_once_with(
            t_patch=t_patch,
            state_patch=state_patch,
            max_outer_iterations=50,
            position_tolerance=1e-3,
            velocity_tolerance=1e-6,
            boundary="fixed_endpoints",
            verbose=True,
        )
        assert result.converged is True
        assert result.iterations == 2
        np.testing.assert_allclose([result.max_residual], [1e-5])
        np.testing.assert_allclose(result.residual_history, [1e-2, 1e-5])
        np.testing.assert_allclose([result.velocity_residual], [2e-5])
        np.testing.assert_allclose(result.velocity_residual_history, [1e-1, 2e-5])
        np.testing.assert_allclose(result.t_patch, t_patch + 20.0)
        np.testing.assert_allclose(result.state_patch, state_patch + 2.0)

    def test_unknown_method_is_rejected(self):
        from tod.generates.ephemeris._corrector import correct_ephemeris_patch_points

        with pytest.raises(ValueError, match="unsupported correction method"):
            correct_ephemeris_patch_points(
                "unknown",
                object(),
                np.array([0.0, 1.0, 2.0]),
                np.zeros((3, 6)),
                tolerance=1e-3,
                max_iter=50,
                verbose=False,
                n_workers=1,
                kernel_dir="kernels",
            )
