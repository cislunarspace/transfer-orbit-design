"""Tests for the unified plot_orbits entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tod.plot.plot_orbits import build_argparser, _resolve_config


class TestBuildArgparser:
    def test_accepts_plane_override(self) -> None:
        parser = build_argparser()
        with patch.object(sys, "argv", ["prog", "--plane", "xz"]):
            args = parser.parse_args()
        assert args.plane == "xz"

    def test_accepts_output_dir(self) -> None:
        parser = build_argparser()
        with patch.object(sys, "argv", ["prog", "--output-dir", "my_output"]):
            args = parser.parse_args()
        assert args.output_dir == "my_output"

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

    def test_default_output_dir_is_plot(self) -> None:
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
            json_file=f'[{{"path": "{halo_file}"}}]',
            plane=None,
            output_dir=None,
        )
        config = _resolve_config(args)
        assert config.family_type == "Halo"
