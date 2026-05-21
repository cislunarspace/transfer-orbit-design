"""Tests for plot_halo_family CLI parameters - issue #104."""

import sys
from unittest.mock import patch, MagicMock

import pytest
import numpy as np


class TestParseArgs:
    """Tests for parse_args() CLI argument parsing."""

    def test_parse_view_2d_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """parse_args should accept --view-2d boolean flag."""
        from tod.plot.halo import plot_halo_family
        monkeypatch.setattr(sys, "argv", ["prog", "--view-2d"])
        args = plot_halo_family.parse_args()
        assert args.view_2d is True

    def test_parse_view_3d_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """parse_args should accept --view-3d boolean flag."""
        from tod.plot.halo import plot_halo_family
        monkeypatch.setattr(sys, "argv", ["prog", "--view-3d"])
        args = plot_halo_family.parse_args()
        assert args.view_3d is True

    def test_parse_jacobi_period_stability_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """parse_args should accept --jacobi-period-stability boolean flag."""
        from tod.plot.halo import plot_halo_family
        monkeypatch.setattr(sys, "argv", ["prog", "--jacobi-period-stability"])
        args = plot_halo_family.parse_args()
        assert args.jacobi_period_stability is True

    def test_parse_all_three_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """parse_args should accept all three boolean flags together."""
        from tod.plot.halo import plot_halo_family
        monkeypatch.setattr(sys, "argv", ["prog", "--view-2d", "--view-3d", "--jacobi-period-stability"])
        args = plot_halo_family.parse_args()
        assert args.view_2d is True
        assert args.view_3d is True
        assert args.jacobi_period_stability is True

    def test_parse_no_plot_flags_defaults_to_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no plot flags are provided, they should default to False."""
        from tod.plot.halo import plot_halo_family
        monkeypatch.setattr(sys, "argv", ["prog"])
        args = plot_halo_family.parse_args()
        assert args.view_2d is False
        assert args.view_3d is False
        assert args.jacobi_period_stability is False

    def test_parse_with_json_file_and_plot_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """parse_args should accept --json-file along with plot flags."""
        from tod.plot.halo import plot_halo_family
        monkeypatch.setattr(sys, "argv", ["prog", "--json-file", "test.json", "--view-2d"])
        args = plot_halo_family.parse_args()
        assert args.json_file == "test.json"
        assert args.view_2d is True

    def test_parse_start_and_end_indices(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """parse_args should accept --start and --end indices."""
        from tod.plot.halo import plot_halo_family
        monkeypatch.setattr(sys, "argv", ["prog", "--start", "10", "--end", "20"])
        args = plot_halo_family.parse_args()
        assert args.start == 10
        assert args.end == 20


class TestMainPlottingControl:
    """Tests for main() plotting control logic."""

    def test_main_logs_warning_when_no_plot_flags(self) -> None:
        """main should log warning when no chart flags are enabled."""
        from tod.plot.halo import plot_halo_family
        with patch.object(plot_halo_family, "parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.json_file = None
            mock_args.start = -1
            mock_args.end = -1
            mock_args.view_2d = False
            mock_args.view_3d = False
            mock_args.jacobi_period_stability = False
            mock_parse.return_value = mock_args

            with patch.object(plot_halo_family.logger, "warning") as mock_warning:
                plot_halo_family.main()
                mock_warning.assert_called_once_with("未选择任何图表，跳过绘制")

    def test_main_calls_2d_plot_when_view_2d_enabled(self) -> None:
        """main should call _plot_2d_view when --view-2d is enabled."""
        from tod.plot.halo import plot_halo_family
        # Mock family data
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.9, 0, 0.1], [0.91, 0, 0.11], [0.92, 0, 0.12]])
        mock_family = MagicMock()
        mock_family.__len__ = MagicMock(return_value=1)
        mock_family.__getitem__ = MagicMock(return_value=mock_orbit)
        mock_family.get_jacobi_constants = MagicMock(return_value=np.array([3.0]))
        mock_family.periods = [1.8]
        mock_system = MagicMock()

        # Mock plotter
        mock_plotter = MagicMock()
        with patch.object(plot_halo_family, "_load_family", return_value=mock_family):
            with patch.object(plot_halo_family, "_compute_stability_indices") as mock_stability:
                with patch.object(plot_halo_family, "CR3BP_System", return_value=mock_system):
                    with patch.object(plot_halo_family, "FamilyPlotter", return_value=mock_plotter):
                        with patch.object(plot_halo_family, "_plot_2d_view") as mock_2d:
                            with patch.object(plot_halo_family, "_plot_3d_view") as mock_3d:
                                with patch.object(plot_halo_family, "_plot_jacobi_period_stability") as mock_jacobi:
                                    with patch.object(plot_halo_family, "parse_args") as mock_parse:
                                        mock_args = MagicMock()
                                        mock_args.json_file = None
                                        mock_args.start = -1
                                        mock_args.end = -1
                                        mock_args.view_2d = True
                                        mock_args.view_3d = False
                                        mock_args.jacobi_period_stability = False
                                        mock_parse.return_value = mock_args

                                        plot_halo_family.main()

                                        mock_2d.assert_called_once()
                                        mock_3d.assert_not_called()
                                        mock_jacobi.assert_not_called()
                                        mock_stability.assert_not_called()

    def test_main_calls_3d_plot_when_view_3d_enabled(self) -> None:
        """main should call _plot_3d_view when --view-3d is enabled."""
        from tod.plot.halo import plot_halo_family
        # Mock family data
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.9, 0, 0.1], [0.91, 0, 0.11], [0.92, 0, 0.12]])
        mock_family = MagicMock()
        mock_family.__len__ = MagicMock(return_value=1)
        mock_family.__getitem__ = MagicMock(return_value=mock_orbit)
        mock_family.get_jacobi_constants = MagicMock(return_value=np.array([3.0]))
        mock_family.periods = [1.8]
        mock_system = MagicMock()

        # Mock plotter
        mock_plotter = MagicMock()
        with patch.object(plot_halo_family, "_load_family", return_value=mock_family):
            with patch.object(plot_halo_family, "_compute_stability_indices") as mock_stability:
                with patch.object(plot_halo_family, "CR3BP_System", return_value=mock_system):
                    with patch.object(plot_halo_family, "FamilyPlotter", return_value=mock_plotter):
                        with patch.object(plot_halo_family, "_plot_2d_view") as mock_2d:
                            with patch.object(plot_halo_family, "_plot_3d_view") as mock_3d:
                                with patch.object(plot_halo_family, "_plot_jacobi_period_stability") as mock_jacobi:
                                    with patch.object(plot_halo_family, "parse_args") as mock_parse:
                                        mock_args = MagicMock()
                                        mock_args.json_file = None
                                        mock_args.start = -1
                                        mock_args.end = -1
                                        mock_args.view_2d = False
                                        mock_args.view_3d = True
                                        mock_args.jacobi_period_stability = False
                                        mock_parse.return_value = mock_args

                                        plot_halo_family.main()

                                        mock_2d.assert_not_called()
                                        mock_3d.assert_called_once()
                                        mock_jacobi.assert_not_called()
                                        mock_stability.assert_not_called()

    def test_main_skips_stability_computation_when_only_view_2d_enabled(self) -> None:
        """When only --view-2d is enabled, _compute_stability_indices should not be called."""
        from tod.plot.halo import plot_halo_family
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.9, 0, 0.1], [0.91, 0, 0.11], [0.92, 0, 0.12]])
        mock_family = MagicMock()
        mock_family.__len__ = MagicMock(return_value=1)
        mock_family.__getitem__ = MagicMock(return_value=mock_orbit)
        mock_family.get_jacobi_constants = MagicMock(return_value=np.array([3.0]))
        mock_family.periods = [1.8]
        mock_system = MagicMock()
        mock_plotter = MagicMock()

        with patch.object(plot_halo_family, "_load_family", return_value=mock_family):
            with patch.object(plot_halo_family, "_compute_stability_indices") as mock_stability:
                with patch.object(plot_halo_family, "CR3BP_System", return_value=mock_system):
                    with patch.object(plot_halo_family, "FamilyPlotter", return_value=mock_plotter):
                        with patch.object(plot_halo_family, "_plot_2d_view"):
                            with patch.object(plot_halo_family, "parse_args") as mock_parse:
                                mock_args = MagicMock()
                                mock_args.json_file = None
                                mock_args.start = -1
                                mock_args.end = -1
                                mock_args.view_2d = True
                                mock_args.view_3d = False
                                mock_args.jacobi_period_stability = False
                                mock_parse.return_value = mock_args

                                plot_halo_family.main()

                                mock_stability.assert_not_called()

    def test_main_skips_stability_computation_when_only_view_3d_enabled(self) -> None:
        """When only --view-3d is enabled, _compute_stability_indices should not be called."""
        from tod.plot.halo import plot_halo_family
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.9, 0, 0.1], [0.91, 0, 0.11], [0.92, 0, 0.12]])
        mock_family = MagicMock()
        mock_family.__len__ = MagicMock(return_value=1)
        mock_family.__getitem__ = MagicMock(return_value=mock_orbit)
        mock_family.get_jacobi_constants = MagicMock(return_value=np.array([3.0]))
        mock_family.periods = [1.8]
        mock_system = MagicMock()
        mock_plotter = MagicMock()

        with patch.object(plot_halo_family, "_load_family", return_value=mock_family):
            with patch.object(plot_halo_family, "_compute_stability_indices") as mock_stability:
                with patch.object(plot_halo_family, "CR3BP_System", return_value=mock_system):
                    with patch.object(plot_halo_family, "FamilyPlotter", return_value=mock_plotter):
                        with patch.object(plot_halo_family, "_plot_3d_view"):
                            with patch.object(plot_halo_family, "parse_args") as mock_parse:
                                mock_args = MagicMock()
                                mock_args.json_file = None
                                mock_args.start = -1
                                mock_args.end = -1
                                mock_args.view_2d = False
                                mock_args.view_3d = True
                                mock_args.jacobi_period_stability = False
                                mock_parse.return_value = mock_args

                                plot_halo_family.main()

                                mock_stability.assert_not_called()

    def test_main_calls_stability_computation_when_view_2d_and_jacobi_flag_enabled(self) -> None:
        """When --view-2d and --jacobi-period-stability are both enabled, _compute_stability_indices should be called."""
        from tod.plot.halo import plot_halo_family
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.9, 0, 0.1], [0.91, 0, 0.11], [0.92, 0, 0.12]])
        mock_family = MagicMock()
        mock_family.__len__ = MagicMock(return_value=1)
        mock_family.__getitem__ = MagicMock(return_value=mock_orbit)
        mock_family.get_jacobi_constants = MagicMock(return_value=np.array([3.0]))
        mock_family.periods = [1.8]
        mock_system = MagicMock()
        mock_plotter = MagicMock()

        with patch.object(plot_halo_family, "_load_family", return_value=mock_family):
            with patch.object(plot_halo_family, "_compute_stability_indices", return_value=[1.5]) as mock_stability:
                with patch.object(plot_halo_family, "CR3BP_System", return_value=mock_system):
                    with patch.object(plot_halo_family, "FamilyPlotter", return_value=mock_plotter):
                        with patch.object(plot_halo_family, "_plot_2d_view"):
                            with patch.object(plot_halo_family, "_plot_jacobi_period_stability"):
                                with patch.object(plot_halo_family, "parse_args") as mock_parse:
                                    mock_args = MagicMock()
                                    mock_args.json_file = None
                                    mock_args.start = -1
                                    mock_args.end = -1
                                    mock_args.view_2d = True
                                    mock_args.view_3d = False
                                    mock_args.jacobi_period_stability = True
                                    mock_parse.return_value = mock_args

                                    plot_halo_family.main()

                                    mock_stability.assert_called_once()

    def test_main_calls_stability_computation_when_view_3d_and_jacobi_flag_enabled(self) -> None:
        """When --view-3d and --jacobi-period-stability are both enabled, _compute_stability_indices should be called."""
        from tod.plot.halo import plot_halo_family
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.9, 0, 0.1], [0.91, 0, 0.11], [0.92, 0, 0.12]])
        mock_family = MagicMock()
        mock_family.__len__ = MagicMock(return_value=1)
        mock_family.__getitem__ = MagicMock(return_value=mock_orbit)
        mock_family.get_jacobi_constants = MagicMock(return_value=np.array([3.0]))
        mock_family.periods = [1.8]
        mock_system = MagicMock()
        mock_plotter = MagicMock()

        with patch.object(plot_halo_family, "_load_family", return_value=mock_family):
            with patch.object(plot_halo_family, "_compute_stability_indices", return_value=[1.5]) as mock_stability:
                with patch.object(plot_halo_family, "CR3BP_System", return_value=mock_system):
                    with patch.object(plot_halo_family, "FamilyPlotter", return_value=mock_plotter):
                        with patch.object(plot_halo_family, "_plot_3d_view"):
                            with patch.object(plot_halo_family, "_plot_jacobi_period_stability"):
                                with patch.object(plot_halo_family, "parse_args") as mock_parse:
                                    mock_args = MagicMock()
                                    mock_args.json_file = None
                                    mock_args.start = -1
                                    mock_args.end = -1
                                    mock_args.view_2d = False
                                    mock_args.view_3d = True
                                    mock_args.jacobi_period_stability = True
                                    mock_parse.return_value = mock_args

                                    plot_halo_family.main()

                                    mock_stability.assert_called_once()

    def test_main_calls_jacobi_period_stability_plot_when_flag_enabled(self) -> None:
        """main should call _plot_jacobi_period_stability when --jacobi-period-stability is enabled."""
        from tod.plot.halo import plot_halo_family
        # Mock family data
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.9, 0, 0.1], [0.91, 0, 0.11], [0.92, 0, 0.12]])
        mock_family = MagicMock()
        mock_family.__len__ = MagicMock(return_value=1)
        mock_family.__getitem__ = MagicMock(return_value=mock_orbit)
        mock_family.get_jacobi_constants = MagicMock(return_value=np.array([3.0]))
        mock_family.periods = [1.8]
        mock_system = MagicMock()

        # Mock plotter
        mock_plotter = MagicMock()
        with patch.object(plot_halo_family, "_load_family", return_value=mock_family):
            with patch.object(plot_halo_family, "_compute_stability_indices", return_value=[1.5]):
                with patch.object(plot_halo_family, "CR3BP_System", return_value=mock_system):
                    with patch.object(plot_halo_family, "FamilyPlotter", return_value=mock_plotter):
                        with patch.object(plot_halo_family, "_plot_2d_view") as mock_2d:
                            with patch.object(plot_halo_family, "_plot_3d_view") as mock_3d:
                                with patch.object(plot_halo_family, "_plot_jacobi_period_stability") as mock_jacobi:
                                    with patch.object(plot_halo_family, "parse_args") as mock_parse:
                                        mock_args = MagicMock()
                                        mock_args.json_file = None
                                        mock_args.start = -1
                                        mock_args.end = -1
                                        mock_args.view_2d = False
                                        mock_args.view_3d = False
                                        mock_args.jacobi_period_stability = True
                                        mock_parse.return_value = mock_args

                                        plot_halo_family.main()

                                        mock_2d.assert_not_called()
                                        mock_3d.assert_not_called()
                                        mock_jacobi.assert_called_once()
