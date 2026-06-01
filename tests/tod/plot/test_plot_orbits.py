"""Tests for the unified plot_orbits entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tod.plot.plot_orbits import build_argparser, _resolve_config
from tod.plot.family_plot_orchestrator import (
    FamilyPlotConfig,
    _get_center_coordinates,
    _resolve_3d_center_radius,
)
from tod.commons.constants import MU


class TestBuildArgparser:
    def test_accepts_plane_override(self) -> None:
        parser = build_argparser()
        with patch.object(sys, "argv", ["prog", "--plane", "xz"]):
            args = parser.parse_args()
        assert args.plane == "xz"

    def test_plane_accepts_empty_string(self) -> None:
        parser = build_argparser()
        with patch.object(sys, "argv", ["prog", "--plane", ""]):
            args = parser.parse_args()
        assert args.plane == ""

    def test_accepts_output_dir(self) -> None:
        parser = build_argparser()
        with patch.object(sys, "argv", ["prog", "--output-dir", "my_output"]):
            args = parser.parse_args()
        assert args.output_dir == "my_output"

    def test_step_default_is_none(self) -> None:
        parser = build_argparser()
        with patch.object(sys, "argv", ["prog"]):
            args = parser.parse_args()
        assert args.step is None

    def test_view_2d_flag(self) -> None:
        parser = build_argparser()
        with patch.object(sys, "argv", ["prog", "--view-2d"]):
            args = parser.parse_args()
        assert args.plot_global_2d is True

    def test_view_3d_flag(self) -> None:
        parser = build_argparser()
        with patch.object(sys, "argv", ["prog", "--view-3d"]):
            args = parser.parse_args()
        assert args.plot_global_3d is True


class TestResolveConfig:
    def test_detects_halo_from_file(self, tmp_path: Path) -> None:
        halo_file = tmp_path / "halo_L1_N_family.json"
        halo_file.write_text("{}")
        args = argparse.Namespace(
            json_file=str(halo_file),
            plane=None,
            output_dir=None,
        )
        config = _resolve_config(args)
        assert config.family_type == "Halo"
        assert config.plane == "xz"

    def test_detects_dro_from_file(self, tmp_path: Path) -> None:
        dro_file = tmp_path / "dro_31_family.json"
        dro_file.write_text("{}")
        args = argparse.Namespace(
            json_file=str(dro_file),
            plane=None,
            output_dir=None,
        )
        config = _resolve_config(args)
        assert config.family_type == "DRO"
        assert config.plane == "xy"

    def test_cli_plane_overrides_detection(self, tmp_path: Path) -> None:
        dro_file = tmp_path / "dro_31_family.json"
        dro_file.write_text("{}")
        args = argparse.Namespace(
            json_file=str(dro_file),
            plane="xz",
            output_dir=None,
        )
        config = _resolve_config(args)
        assert config.plane == "xz"

    def test_cli_output_dir_overrides(self, tmp_path: Path) -> None:
        halo_file = tmp_path / "halo_L1_N_family.json"
        halo_file.write_text("{}")
        args = argparse.Namespace(
            json_file=str(halo_file),
            plane=None,
            output_dir="custom_output",
        )
        config = _resolve_config(args)
        assert config.output_subdir == "custom_output"

    def test_detected_output_subdir_preserved_when_no_cli_override(self, tmp_path: Path) -> None:
        halo_file = tmp_path / "halo_L1_N_family.json"
        halo_file.write_text("{}")
        args = argparse.Namespace(
            json_file=str(halo_file),
            plane=None,
            output_dir=None,
        )
        config = _resolve_config(args)
        assert config.output_subdir == "halo"

    def test_default_output_subdir_is_plot(self) -> None:
        args = argparse.Namespace(
            json_file=None,
            plane=None,
            output_dir=None,
        )
        config = _resolve_config(args)
        assert config.output_subdir == "plot"

    def test_multi_file_detects_from_first(self, tmp_path: Path) -> None:
        halo_file = tmp_path / "halo_L1_N_family.json"
        halo_file.write_text("{}")
        args = argparse.Namespace(
            json_file=json.dumps([{"path": str(halo_file)}]),
            plane=None,
            output_dir=None,
        )
        config = _resolve_config(args)
        assert config.family_type == "Halo"

    def test_empty_plane_string_does_not_override(self, tmp_path: Path) -> None:
        halo_file = tmp_path / "halo_L1_N_family.json"
        halo_file.write_text("{}")
        args = argparse.Namespace(
            json_file=str(halo_file),
            plane="",
            output_dir=None,
        )
        config = _resolve_config(args)
        assert config.plane == "xz"  # auto-detected from halo, not overridden by ""

    def test_invalid_plane_raises(self, tmp_path: Path) -> None:
        halo_file = tmp_path / "halo_L1_N_family.json"
        halo_file.write_text("{}")
        args = argparse.Namespace(
            json_file=str(halo_file),
            plane="invalid",
            output_dir=None,
        )
        with pytest.raises(ValueError, match="--plane"):
            _resolve_config(args)


class TestGetCenterCoordinates:
    """Tests for _get_center_coordinates helper."""

    def test_moon_center(self) -> None:
        center = _get_center_coordinates("moon", MU)
        assert abs(center[0] - (1.0 - MU)) < 1e-10
        assert center[1] == 0.0
        assert center[2] == 0.0

    def test_earth_center(self) -> None:
        center = _get_center_coordinates("earth", MU)
        assert center == (0.0, 0.0, 0.0)

    def test_emb_center(self) -> None:
        center = _get_center_coordinates("emb", MU)
        assert abs(center[0] - MU) < 1e-10
        assert center[1] == 0.0
        assert center[2] == 0.0

    def test_unknown_center_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown center type"):
            _get_center_coordinates("mars", MU)


class TestResolve3dCenterRadius:
    """Regression tests for _resolve_3d_center_radius.

    The core bug: Halo config has dynamic_bounds=True, so _render_3d used
    bounds-derived center and ignored the user's --plot-center choice entirely.
    _resolve_3d_center_radius must ALWAYS respect args.plot_center.
    """

    @staticmethod
    def _args(plot_center: str = "moon") -> argparse.Namespace:
        return argparse.Namespace(plot_center=plot_center)

    def test_halo_uses_plot_center_not_data_center(self) -> None:
        """Halo config (dynamic_bounds=True) must respect user's --plot-center."""
        cfg = FamilyPlotConfig(
            family_type="Halo",
            default_filename="halo_L1_N_family",
            output_subdir="halo",
            plane="xz",
            dynamic_bounds=True,
        )
        # bounds[2] is data center (near Moon), bounds[3] is data radius
        data_bounds = ((0.7, 0.9), (-0.1, 0.1), (0.95, 0.0, 0.0), 0.3)

        center, radius = _resolve_3d_center_radius(cfg, self._args("earth"), data_bounds)

        # Center should be Earth (0,0,0), NOT data-derived (0.95,0,0)
        assert center == (0.0, 0.0, 0.0)
        # Radius must expand to include the data when center differs
        assert radius >= 0.3

    def test_halo_moon_center_keeps_data_radius(self) -> None:
        """When center matches data location (moon), radius should stay tight."""
        cfg = FamilyPlotConfig(
            family_type="Halo",
            default_filename="halo_L1_N_family",
            output_subdir="halo",
            plane="xz",
            dynamic_bounds=True,
        )
        data_bounds = ((0.7, 0.9), (-0.1, 0.1), (1.0 - MU, 0.0, 0.0), 0.3)

        center, radius = _resolve_3d_center_radius(cfg, self._args("moon"), data_bounds)

        assert abs(center[0] - (1.0 - MU)) < 1e-10
        # radius should be close to the data radius since center is near data
        assert radius <= 0.35  # small tolerance for center offset

    def test_ro_config_respects_plot_center_over_hardcoded(self) -> None:
        """RO configs with hardcoded center_3d must also respect --plot-center."""
        cfg = FamilyPlotConfig(
            family_type="3:1 RO",
            default_filename="ro_31_family",
            output_subdir="ro",
            plane="xy",
            center_3d=(-0.85, 0, 0),
            radius_3d=0.5,
        )

        center, radius = _resolve_3d_center_radius(cfg, self._args("earth"), bounds=None)

        # Should use Earth center, NOT hardcoded (-0.85, 0, 0)
        assert center == (0.0, 0.0, 0.0)
        assert radius == 0.5  # still uses config radius

    def test_dro_config_respects_plot_center(self) -> None:
        """DRO config (supports_center_choice=True) must still work correctly."""
        cfg = FamilyPlotConfig(
            family_type="DRO",
            default_filename="dro_31_family",
            output_subdir="dro",
            plane="xy",
            radius_3d=1.5,
            supports_center_choice=True,
        )

        center, radius = _resolve_3d_center_radius(cfg, self._args("emb"), bounds=None)

        assert abs(center[0] - MU) < 1e-10
        assert radius == 1.5

    def test_fallback_radius_when_no_config(self) -> None:
        """Fallback config (no radius_3d, no dynamic_bounds) uses default radius."""
        cfg = FamilyPlotConfig(
            family_type="Orbit",
            default_filename="orbit",
            output_subdir="plot",
            plane="xy",
        )

        center, radius = _resolve_3d_center_radius(cfg, self._args("moon"), bounds=None)

        assert abs(center[0] - (1.0 - MU)) < 1e-10
        assert radius == 1.0  # default fallback

    def test_dynamic_bounds_adjusts_radius_for_distant_center(self) -> None:
        """When user center is far from data, radius must expand to include orbits."""
        cfg = FamilyPlotConfig(
            family_type="Halo",
            default_filename="halo_L1_N_family",
            output_subdir="halo",
            plane="xz",
            dynamic_bounds=True,
        )
        # Data centered near Moon
        data_bounds = ((0.7, 0.9), (-0.1, 0.1), (1.0 - MU, 0.0, 0.0), 0.2)

        center, radius = _resolve_3d_center_radius(cfg, self._args("earth"), data_bounds)

        # Earth is ~0.99 away from Moon; radius must be >= 0.99 + 0.2
        assert center == (0.0, 0.0, 0.0)
        assert radius >= 1.0  # must see orbits from Earth
