"""
Tests for scripts/utils/params.py module

Tests the physical constants used for Earth-Moon-Sun system.
"""

import pytest

from scripts.utils.params import MU, M_SUN, OMEGA_SUN, RHO, DU, TU, VU, T_MOON


class TestPhysicalConstants:
    """Test Earth-Moon-Sun physical constants"""

    def test_mu_is_positive(self):
        """MU (Earth-Moon mass ratio) should be positive"""
        assert MU > 0
        assert MU < 1  # Moon is much smaller than Earth

    def test_m_sun_is_positive(self):
        """M_SUN (nondimensional sun mass) should be positive"""
        assert M_SUN > 0

    def test_omega_sun_is_positive(self):
        """OMEGA_SUN (nondimensional angular velocity) should be positive"""
        assert OMEGA_SUN > 0
        assert OMEGA_SUN < 1  # Should be less than 1 rotation per time unit

    def test_rho_is_positive(self):
        """RHO (nondimensional sun-Earth-moon distance) should be positive"""
        assert RHO > 0
        assert RHO > 1  # Sun is much farther than 1 DU

    def test_du_is_positive(self):
        """DU (distance unit in km) should be positive"""
        assert DU > 0

    def test_tu_is_positive(self):
        """TU (time unit in days) should be positive"""
        assert TU > 0

    def test_vu_is_positive(self):
        """VU (velocity unit in m/s) should be positive"""
        assert VU > 0

    def test_t_moon_equals_2pi(self):
        """Moon orbital period in nondimensional units should be 2π"""
        import math
        assert math.isclose(T_MOON, 2 * math.pi, rel_tol=1e-10)

    def test_constants_consistency(self):
        """VU should be consistent with DU and TU (VU = DU/TU in appropriate units)"""
        import math
        expected_vu = DU * 1000 / (TU * 86400)
        assert math.isclose(VU, expected_vu, rel_tol=0.01)
