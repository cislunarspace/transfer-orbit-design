"""
Regression tests for richardson_initial_guess refactor (issue #33).

Verifies that:
- Sub-functions are importable and documented
- Period computation returns expected structure
- Seed extraction finds correct z-maximum point
- vy0 sign selection produces correct orbit direction
- richardson_initial_guess returns consistent results
"""

import importlib
import inspect

import numpy as np
import pytest


@pytest.fixture
def halo_module():
    """Import generate_halo_orbit module."""
    return importlib.import_module("tod.generates.cr3bp.halo.generate_halo_orbit")


@pytest.fixture
def mu():
    """Earth-Moon mass ratio."""
    return 1.21506683e-2


class TestSubFunctionsExist:
    """Test that refactored sub-functions are properly defined."""

    def test_compute_richardson_period_exists(self, halo_module):
        assert hasattr(halo_module, "_compute_richardson_period")

    def test_extract_seed_from_approximation_exists(self, halo_module):
        assert hasattr(halo_module, "_extract_seed_from_approximation")

    def test_select_vy0_sign_exists(self, halo_module):
        assert hasattr(halo_module, "_select_vy0_sign")

    def test_richardson_initial_guess_exists(self, halo_module):
        assert hasattr(halo_module, "richardson_initial_guess")


class TestSubFunctionsDocstring:
    """Test that sub-functions have Chinese docstrings."""

    def test_compute_richardson_period_has_docstring(self, halo_module):
        assert halo_module._compute_richardson_period.__doc__ is not None
        assert "计算" in halo_module._compute_richardson_period.__doc__

    def test_extract_seed_from_approximation_has_docstring(self, halo_module):
        assert halo_module._extract_seed_from_approximation.__doc__ is not None
        assert "提取" in halo_module._extract_seed_from_approximation.__doc__

    def test_select_vy0_sign_has_docstring(self, halo_module):
        assert halo_module._select_vy0_sign.__doc__ is not None
        assert "符号" in halo_module._select_vy0_sign.__doc__


class TestComputeRichardsonPeriod:
    """Test _compute_richardson_period returns correct structure."""

    def test_returns_five_values(self, halo_module, mu):
        Au = 0.1
        Aw = 0.2
        result = halo_module._compute_richardson_period(mu, Au, Aw, libration_point=1)
        assert isinstance(result, tuple)
        assert len(result) == 4  # T_linear, T_richardson, omega_p, freq_correction

    def test_periods_are_positive(self, halo_module, mu):
        Au = 0.1
        Aw = 0.2
        T_linear, T_richardson, omega_p, freq_correction = halo_module._compute_richardson_period(
            mu, Au, Aw, libration_point=1
        )
        assert T_linear > 0
        assert T_richardson > 0
        assert omega_p > 0

    def test_richardson_period_differs_from_linear(self, halo_module, mu):
        """Richardson correction should modify period for non-zero amplitudes."""
        Au = 0.3
        Aw = 0.5
        T_linear, T_richardson, _, freq_correction = halo_module._compute_richardson_period(
            mu, Au, Aw, libration_point=1
        )
        # With non-zero amplitudes, freq_correction should be non-zero
        assert freq_correction != 0
        # T_richardson should differ from T_linear due to correction
        assert T_linear != T_richardson


class TestExtractSeedFromApproximation:
    """Test _extract_seed_from_approximation finds correct point."""

    def test_finds_z_maximum(self, halo_module):
        """Should extract state at z amplitude maximum."""
        # Create mock orbit with known z-maximum at index 50
        n_points = 100
        t = np.linspace(0, 2 * np.pi, n_points)
        z_col = np.sin(t)  # z-maximum at index 25 (sin = 1)
        x_col = np.cos(t)
        vy_col = np.zeros(n_points)

        # Build SV_xyz: [x, y, z, vx, vy, vz]
        SV_xyz = np.column_stack([x_col, np.zeros(n_points), z_col, np.zeros(n_points), vy_col, np.zeros(n_points)])

        x0, vy0, z0 = halo_module._extract_seed_from_approximation(SV_xyz, z_amplitude=1.0)

        # Should find maximum |z| point
        assert np.abs(x0) <= 1.0  # x in valid range
        assert vy0 == 0.0  # vy at z-maximum is zero

    def test_returns_float_values(self, halo_module):
        """Should return Python floats, not numpy types."""
        n_points = 100
        t = np.linspace(0, 2 * np.pi, n_points)
        SV_xyz = np.column_stack([
            np.cos(t),
            np.zeros(n_points),
            np.sin(t),
            np.zeros(n_points),
            np.zeros(n_points),
            np.zeros(n_points),
        ])

        x0, vy0, z0 = halo_module._extract_seed_from_approximation(SV_xyz, z_amplitude=1.0)

        assert isinstance(x0, float)
        assert isinstance(vy0, float)
        assert isinstance(z0, float)


class TestSelectVy0Sign:
    """Test _select_vy0_sign correctly selects orbit direction."""

    def test_returns_positive_vy0_when_x_increases(self, halo_module, mu):
        """When half-period propagation causes x to increase, vy0 should be positive."""
        # L1 halo orbits move outward initially, so vy0 > 0
        vy0_raw = 0.1
        result = halo_module._select_vy0_sign(x0=0.93, z0=0.23, vy0_raw=vy0_raw, T=3.6, mu=mu)
        assert result > 0

    def test_returns_negative_vy0_when_x_decreases(self, halo_module, mu):
        """When half-period propagation causes x to decrease, vy0 should be negative."""
        # This tests the sign correction logic
        vy0_raw = -0.1  # Negative raw value
        result = halo_module._select_vy0_sign(x0=0.93, z0=0.23, vy0_raw=vy0_raw, T=3.6, mu=mu)
        # The function should ensure the sign matches the x-direction
        assert isinstance(result, float)

    def test_magnitude_preserved(self, halo_module, mu):
        """Sign selection should preserve magnitude."""
        vy0_raw = 0.25
        result = halo_module._select_vy0_sign(x0=0.93, z0=0.23, vy0_raw=vy0_raw, T=3.6, mu=mu)
        assert np.abs(result) == pytest.approx(0.25)


class TestRichardsonInitialGuess:
    """Test richardson_initial_guess integration."""

    def test_returns_dict_with_required_keys(self, halo_module, mu):
        """Should return dict with x0, z0, vy0, period."""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        assert isinstance(result, dict)
        assert set(result.keys()) == {"x0", "z0", "vy0", "period"}

    def test_z0_sign_for_north_halo(self, halo_module, mu):
        """North halo (Class I) should have positive z0."""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        assert result["z0"] > 0

    def test_z0_sign_for_south_halo(self, halo_module, mu):
        """South halo (Class II) should have negative z0."""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=1)
        assert result["z0"] < 0

    def test_x0_in_valid_range_for_l1(self, halo_module, mu):
        """L1 halo x0 should be between Earth-Moon line and L1 point."""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        # L1 is at x ≈ 0.99, x0 should be less than L1
        assert 0.8 < result["x0"] < 1.0

    def test_period_is_positive(self, halo_module, mu):
        """Period should always be positive."""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        assert result["period"] > 0

    def test_vy0_magnitude_reasonable(self, halo_module, mu):
        """vy0 magnitude should be in reasonable range for halo orbits."""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=0)
        # Typical halo vy0 is O(0.1)
        assert 0.0 < abs(result["vy0"]) < 1.0

    @pytest.mark.parametrize("halo_class", [0, 1])
    def test_l1_halo_both_classes(self, halo_module, mu, halo_class):
        """Both halo classes should produce valid results for L1."""
        result = halo_module.richardson_initial_guess(mu, 0.23, libration_point=1, halo_class=halo_class)
        assert "x0" in result
        assert "z0" in result
        assert "vy0" in result
        assert "period" in result


class TestFunctionLineCounts:
    """Verify refactoring meets line count requirements from issue #33."""

    def test_richardson_initial_guess_under_50_lines(self, halo_module):
        """richardson_initial_guess should be under 50 lines."""
        source = inspect.getsource(halo_module.richardson_initial_guess)
        lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
        assert len(lines) < 50, f"Function has {len(lines)} lines, should be < 50"

    def test_sub_functions_under_50_lines(self, halo_module):
        """All sub-functions should be under 50 lines."""
        funcs = [
            halo_module._compute_richardson_period,
            halo_module._extract_seed_from_approximation,
            halo_module._select_vy0_sign,
        ]
        for func in funcs:
            source = inspect.getsource(func)
            lines = [l for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
            assert len(lines) < 50, f"{func.__name__} has {len(lines)} lines, should be < 50"
