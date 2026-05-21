"""Tests for plot_halo_family thin wrapper — verifies delegation to orchestrator."""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestHaloWrapperDelegation:
    def test_main_delegates_to_orchestrator(self) -> None:
        from tod.plot.halo import plot_halo_family

        with patch.object(plot_halo_family, "build_argparser") as mock_parser:
            mock_args = MagicMock()
            mock_args.plot_global_2d = True
            mock_args.plot_global_3d = False
            mock_args.plot_jacobi_stability = False
            mock_parser.return_value.parse_args.return_value = mock_args

            with patch.object(plot_halo_family, "FamilyPlotOrchestrator") as MockOrch:
                mock_instance = MockOrch.return_value
                plot_halo_family.main()
                MockOrch.assert_called_once()
                mock_instance.run.assert_called_once()

    def test_main_overrides_args_when_kwargs_provided(self) -> None:
        from tod.plot.halo import plot_halo_family

        with patch.object(plot_halo_family, "build_argparser") as mock_parser:
            mock_args = MagicMock()
            mock_args.plot_global_2d = False
            mock_args.plot_global_3d = False
            mock_args.plot_jacobi_stability = False
            mock_parser.return_value.parse_args.return_value = mock_args

            with patch.object(plot_halo_family, "FamilyPlotOrchestrator") as MockOrch:
                mock_instance = MockOrch.return_value
                plot_halo_family.main(plot1=True, plot2=False, plot3=False)

                assert mock_args.plot_global_2d is True
                MockOrch.assert_called_once()

    def test_config_has_correct_plane(self) -> None:
        from tod.plot.halo.plot_halo_family import CONFIG
        assert CONFIG.plane == "xz"
        assert CONFIG.dynamic_bounds is True
