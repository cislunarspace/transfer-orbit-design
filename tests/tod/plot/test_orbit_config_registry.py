"""Tests for orbit_config_registry — type detection and default config mapping."""

from pathlib import Path

import pytest

from tod.plot.orbit_config_registry import (
    FALLBACK_CONFIG,
    _CONFIG_REGISTRY,
    detect_orbit_config,
)


class TestDetectOrbitConfig:
    """Verify filename → config mapping for all registered types."""

    @pytest.mark.parametrize(
        "filename, expected_type",
        [
            ("halo_L1_N_family_0.001_1234.json", "Halo"),
            ("halo_L2_S_orbit_5678.json", "Halo"),
            ("dro_31_family_0.14_1234.json", "DRO"),
            ("dro_31_5678.json", "DRO"),
            ("ro_31_family_1234.json", "3:1 RO"),
            ("ro_32_family_1234.json", "3:2 RO"),
            ("aro_32_family_1234.json", "3:2 ARO"),
            ("rro_32_family_1234.json", "3:2 RRO"),
        ],
    )
    def test_detects_known_types(self, filename: str, expected_type: str) -> None:
        config = detect_orbit_config(Path(filename))
        assert config.family_type == expected_type

    def test_unknown_filename_returns_fallback(self) -> None:
        config = detect_orbit_config(Path("unknown_orbit_1234.json"))
        assert config.family_type == "Orbit"

    def test_case_insensitive_detection(self) -> None:
        config = detect_orbit_config(Path("HALO_L1_N_family.json"))
        assert config.family_type == "Halo"

    def test_halo_config_has_xz_plane(self) -> None:
        config = detect_orbit_config(Path("halo_L1_N_family.json"))
        assert config.plane == "xz"
        assert config.dynamic_bounds is True

    def test_dro_config_has_xy_plane(self) -> None:
        config = detect_orbit_config(Path("dro_31_family.json"))
        assert config.plane == "xy"
        assert config.supports_center_choice is True

    def test_ro_31_config_has_target_period(self) -> None:
        import numpy as np
        config = detect_orbit_config(Path("ro_31_family.json"))
        assert config.target_period == pytest.approx(2 * np.pi)

    def test_ro_32_config_has_target_period(self) -> None:
        import numpy as np
        config = detect_orbit_config(Path("ro_32_family.json"))
        assert config.target_period == pytest.approx(4 * np.pi)


class TestRegistryCompleteness:
    """Verify the registry has all expected entries."""

    EXPECTED_PREFIXES = {"halo_", "dro_", "ro_31_", "ro_32_", "aro_", "rro_"}

    def test_all_prefixes_registered(self) -> None:
        registered = {prefix for prefix, _ in _CONFIG_REGISTRY}
        assert registered == self.EXPECTED_PREFIXES

    def test_fallback_config_is_valid(self) -> None:
        assert FALLBACK_CONFIG.family_type == "Orbit"
        assert FALLBACK_CONFIG.output_subdir == "plot"
