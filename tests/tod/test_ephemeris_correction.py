"""
Tests for ephemeris correction script (correct_dro_to_ephemeris.py)

These tests focus on:
- Testing the import structure
- Testing the corrector delegation wrapper
"""

import pytest
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
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


class TestEphemerisCorrectionMethodSelection:
    """Test TOD correction compatibility wrapper delegates to e2m2e."""

    def test_corrector_delegates_to_e2m2e_dispatch(self):
        from tod.generates.ephemeris._corrector import correct_ephemeris_patch_points

        dynamics = object()
        t_patch = np.array([0.0, 1.0, 2.0])
        state_patch = np.zeros((3, 6))
        expected = SimpleNamespace(converged=True)

        with patch(
            "tod.generates.ephemeris._corrector._e2m2e_correct_ephemeris_patch_points",
            return_value=expected,
        ) as dispatch:
            result = correct_ephemeris_patch_points(
                "homotopy",
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

        assert result is expected
        dispatch.assert_called_once_with(
            "homotopy",
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
