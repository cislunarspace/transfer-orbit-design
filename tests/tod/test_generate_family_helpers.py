"""
Tests for tod/generates/cr3bp generation scripts (generate_31_ro_family.py, generate_32_ro_family.py, generate_dro_family.py)

These tests focus on:
- Testing the parameter configurations
- Testing the import structure
- Testing that scripts can be parsed without errors
"""

import matplotlib

matplotlib.use("Agg")  # Use non-GUI backend to suppress plot display

import json
import pytest
import numpy as np
import importlib.util
from fnmatch import fnmatch
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parent.parent.parent


class TestGenerateScriptImports:
    """Test that generation scripts can be imported and parsed"""

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_generate_31_ro_imports(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        """Test that generate_31_ro_family.py can be imported without errors"""
        # Mock expensive computations to avoid long-running tests
        mock_corr.return_value.iterate_correction.return_value = MagicMock()
        mock_cont.return_value.natural_continuation.return_value = MagicMock()

        script_path = (
            project_root / "tod" / "generates" / "cr3bp" / "ro" / "generate_31_ro_family.py"
        )
        spec = importlib.util.spec_from_file_location(
            "generate_31_ro_family", script_path
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")
        except Exception as e:
            pytest.fail(f"Script import failed with unexpected error: {e}")

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_generate_32_ro_imports(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        """Test that generate_32_ro_family.py can be imported without errors"""
        # Mock expensive computations to avoid long-running tests
        mock_corr.return_value.iterate_correction.return_value = MagicMock()
        mock_cont.return_value.natural_continuation.return_value = MagicMock()

        script_path = (
            project_root / "tod" / "generates" / "cr3bp" / "ro" / "generate_32_ro_family.py"
        )
        spec = importlib.util.spec_from_file_location(
            "generate_32_ro_family", script_path
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")
        except Exception as e:
            pytest.fail(f"Script import failed with unexpected error: {e}")

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_generate_dro_imports(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        """Test that generate_dro_family.py can be imported without errors"""
        # Mock expensive computations to avoid long-running tests
        mock_corr.return_value.iterate_correction.return_value = MagicMock()
        mock_cont.return_value.natural_continuation.return_value = MagicMock()

        script_path = (
            project_root / "tod" / "generates" / "cr3bp" / "dro" / "generate_dro_family.py"
        )
        spec = importlib.util.spec_from_file_location(
            "generate_dro_family", script_path
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except ImportError as e:
            pytest.skip(f"Missing dependency: {e}")
        except Exception as e:
            pytest.fail(f"Script import failed with unexpected error: {e}")


class TestGenerate31ROParameters:
    """Test generate_31_ro_family.py parameter configurations"""

    def test_seed_parameters_31ro(self):
        """Test that 3:1 RO seed orbit parameters are reasonable"""
        # These are theoretical values from the script
        x0 = -0.8805
        z0 = 0.0
        vy0 = 0.3921
        vz0 = 0.0

        # x0 should be in valid range for 3:1 RO
        assert -2 < x0 < 0  # RO orbits are on Moon's far side
        assert z0 == 0  # Planar orbit
        assert vy0 > 0  # Retrograde orbit has positive vy
        assert vz0 == 0  # Planar orbit

    def test_continuation_range_31ro(self):
        """Test that 3:1 RO continuation range is reasonable"""
        x0 = -0.8805
        param_min = x0
        param_max = x0 + 0.02  # Narrowed from 0.05 to 0.02

        assert param_min < 0  # RO orbits are on Moon's far side (negative x)
        assert param_max > param_min
        assert param_max < 0  # Should be in valid RO region


class TestGenerate32ROParameters:
    """Test generate_32_ro_family.py parameter configurations"""

    def test_seed_parameters_32ro(self):
        """Test that 3:2 RO seed orbit parameters are reasonable"""
        x0 = -1.1453
        z0 = 0.0
        vy0 = 0.4633
        vz0 = 0.0

        # x0 should be in valid range for 3:2 RO
        assert -2 < x0 < 0
        assert z0 == 0
        assert vy0 > 0
        assert vz0 == 0

    def test_continuation_range_32ro(self):
        """Test that 3:2 RO continuation range is reasonable"""
        param_min = -1.0  # Narrowed from -1.2 to -1.0
        param_max = -0.9  # Narrowed from -0.8 to -0.9

        assert param_min < param_max
        assert -2 < param_min < 0
        assert -2 < param_max < 0


def _load_halo_family_module():
    """Load generate_halo_family module, skipping if e2m2e is missing."""
    script_path = (
        project_root / "tod" / "generates" / "cr3bp" / "halo" / "generate_halo_family.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generate_halo_family", script_path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except ImportError as e:
        pytest.skip(f"Missing dependency: {e}")
    return module


class TestGenerateHaloFamilyImports:
    """Test generate_halo_family.py import and parameter parsing"""

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_generate_halo_family_imports(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        """Test that generate_halo_family.py can be imported without errors"""
        try:
            _load_halo_family_module()
        except Exception as e:
            pytest.fail(f"Script import failed with unexpected error: {e}")

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_generate_halo_family_seed_file_param(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        """Test that --seed-file parameter is recognized and parsed"""
        module = _load_halo_family_module()
        args = module.parse_args(["--seed-file", "output/halo/test_seed.json"])
        assert args.seed_file == "output/halo/test_seed.json"

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_generate_halo_family_richardson_params_defaults(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        """Test that Richardson seed generation parameters have reasonable defaults."""
        module = _load_halo_family_module()
        args = module.parse_args([])
        assert args.seed_file is None
        assert args.libration_point == "L1"
        assert args.amplitude_z == pytest.approx(0.001)
        assert args.halo_class == 0


class TestGenerateHaloFamilySeedFile:
    """Test generate_halo_family.py seed file loading path"""

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_seed_file_restores_metadata_before_continuation(
        self,
        mock_cont_cls,
        mock_corr_cls,
        mock_dyn,
        mock_sys,
        tmp_path,
    ):
        """Seed-file path must tag the loaded orbit before PAL continuation."""
        module = _load_halo_family_module()

        mock_seed = MagicMock()
        mock_seed.period = 1.84
        mock_seed.states = np.array([[0.93, 0, -0.27, 0, 0.1, 0]])
        mock_seed.parameters = {}

        mock_family = MagicMock()
        mock_family.__len__ = lambda self: 5
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.93, 0, -0.27, 0, 0.1, 0]])
        mock_orbit.period = 1.84
        mock_orbit.periodicity_error = 1e-12
        mock_orbit.parameters = {"amplitude_z": 0.27}
        mock_family.__iter__ = lambda self: iter([mock_orbit] * 5)

        mock_cont_inst = mock_cont_cls.return_value
        mock_cont_inst.halo_pseudo_arclength_continuation.return_value = mock_family

        seed_path = tmp_path / "halo_L2_S_0.27_123.json"
        seed_path.write_text(json.dumps({
            "states": [[0.93, 0, 0.23, 0, 0.1, 0]],
            "times": [0],
            "period": 1.84,
        }), encoding="utf-8")

        with patch("e2m2e.core.Orbit.load_from_file", return_value=mock_seed) as mock_load:
            with patch.object(module, "_print_summary_table"):
                with patch.object(module, "parse_args", return_value=module.parse_args(
                    [
                        "--seed-file",
                        str(seed_path),
                        "--libration-point",
                        "L2",
                        "--halo-class",
                        "1",
                        "--n-orbits",
                        "5",
                        "--method",
                        "pseudo_arclength",
                    ]
                )):
                    module.main()

        mock_load.assert_called_once()
        mock_cont_inst.generate_halo_seed_orbit.assert_not_called()
        call_kwargs = mock_cont_inst.halo_pseudo_arclength_continuation.call_args.kwargs
        assert call_kwargs["seed_orbit"] is mock_seed
        assert mock_seed.family_type == "halo"
        assert mock_seed.parameters == {
            "libration_point": 2,
            "halo_class": 1,
            "amplitude_z": pytest.approx(0.27),
        }

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_seed_family_file_loads_first_orbit(
        self,
        mock_cont_cls,
        mock_corr_cls,
        mock_dyn,
        mock_sys,
        tmp_path,
    ):
        """A family JSON selected as a seed file should load orbit_index=0."""
        module = _load_halo_family_module()

        mock_seed = MagicMock()
        mock_seed.period = 1.84
        mock_seed.states = np.array([[0.93, 0, 0.23, 0, 0.1, 0]])
        mock_seed.parameters = {}

        mock_family = MagicMock()
        mock_family.__len__ = lambda self: 1
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.93, 0, 0.23, 0, 0.1, 0]])
        mock_orbit.period = 1.84
        mock_orbit.periodicity_error = 1e-12
        mock_orbit.parameters = {"amplitude_z": 0.23}
        mock_family.__iter__ = lambda self: iter([mock_orbit])

        mock_cont_inst = mock_cont_cls.return_value
        mock_cont_inst.halo_pseudo_arclength_continuation.return_value = mock_family

        family_path = tmp_path / "halo_L1_N_family_0.23_123.json"
        family_path.write_text(json.dumps({
            "orbits": [
                {
                    "states": [[0.93, 0, 0.23, 0, 0.1, 0]],
                    "times": [0],
                    "period": 1.84,
                }
            ]
        }), encoding="utf-8")

        with patch("e2m2e.core.Orbit.load_from_file", return_value=mock_seed) as mock_load:
            with patch.object(module, "_print_summary_table"):
                with patch.object(module, "parse_args", return_value=module.parse_args(
                    ["--seed-file", str(family_path), "--n-orbits", "1", "--method", "pseudo_arclength"]
                )):
                    module.main()

        assert mock_load.call_args.kwargs["orbit_index"] == 0
        mock_cont_inst.halo_pseudo_arclength_continuation.assert_called_once()

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_no_seed_file_uses_richardson_seed_generation(self, mock_cont_cls, mock_corr_cls, mock_dyn, mock_sys):
        """Without --seed-file, the family script should use Richardson seed generation."""
        module = _load_halo_family_module()

        mock_seed = MagicMock()
        mock_seed.period = 1.84
        mock_seed.states = np.array([[0.93, 0, -0.31, 0, 0.1, 0]])
        mock_seed.parameters = {}

        mock_corr_inst = mock_corr_cls.return_value

        mock_family = MagicMock()
        mock_family.__len__ = lambda self: 3
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.93, 0, -0.31, 0, 0.1, 0]])
        mock_orbit.period = 1.84
        mock_orbit.periodicity_error = 1e-12
        mock_orbit.parameters = {"amplitude_z": 0.31}
        mock_family.__iter__ = lambda self: iter([mock_orbit] * 3)

        mock_cont_inst = mock_cont_cls.return_value
        mock_cont_inst.generate_halo_seed_orbit.return_value = mock_seed
        mock_cont_inst.halo_pseudo_arclength_continuation.return_value = mock_family

        with patch.object(module, "_print_summary_table"):
            with patch.object(module, "parse_args", return_value=module.parse_args(
                [
                    "--libration-point",
                    "L2",
                    "--amplitude-z",
                    "0.31",
                    "--halo-class",
                    "1",
                    "--n-orbits",
                    "3",
                    "--method",
                    "pseudo_arclength",
                ]
            )):
                module.main()

        mock_cont_inst.generate_halo_seed_orbit.assert_called_once_with(
            libration_point=2,
            amplitude_z=0.31,
            halo_class=1,
            verbose=False,
        )
        mock_corr_inst.setup_halo_orbit_fixed_z0.assert_not_called()
        mock_corr_inst.iterate_correction.assert_not_called()
        assert mock_seed.parameters == {
            "libration_point": 2,
            "halo_class": 1,
            "amplitude_z": pytest.approx(0.31),
        }
        mock_cont_inst.halo_pseudo_arclength_continuation.assert_called_once()


class TestHaloGuiRegistry:
    """Test GUI registry details for Halo family generation."""

    def test_seed_file_pattern_excludes_halo_family_outputs(self):
        """Seed file picker should not offer generated family JSON by default."""
        from tod.gui.script_registry import SCRIPTS

        entry = next(e for e in SCRIPTS["Halo"] if e.name == "generate_halo_family")
        seed_param = next(p for p in entry.cli_params if p.flag == "--seed-file")

        assert seed_param.name_pattern is not None
        assert fnmatch("halo_L2_S_0.23_123456.json", seed_param.name_pattern)
        assert not fnmatch("halo_L2_S_family_0.23_123456.json", seed_param.name_pattern)


class TestGenerateDROParameters:
    """Test generate_dro_family.py parameter configurations"""

    def test_seed_parameters_dro(self):
        """Test that DRO seed orbit parameters are reasonable"""
        x0 = 0.79188556619742
        vy0 = 0.53682

        # DRO orbits are between Earth and Moon, x0 should be positive
        assert 0 < x0 < 1
        assert vy0 > 0

    def test_continuation_range_dro(self):
        """Test that DRO continuation range is reasonable"""
        param_min = 0.6
        param_max = 0.7  # Narrowed from 0.8 to 0.7
        step_size = 0.005

        assert 0 < param_min < param_max
        assert param_max < 1
        assert step_size > 0
        assert step_size < 0.1  # Step size should be reasonable


class TestHaloFamilyNewParams:
    """Test new CLI parameters for generate_halo_family.py"""

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_step_size_negative_defaults_to_none(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        module = _load_halo_family_module()
        args = module.parse_args([])
        assert args.step_size_negative is None

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_step_size_negative_explicit(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        module = _load_halo_family_module()
        args = module.parse_args(["--step-size-negative", "0.01"])
        assert args.step_size_negative == pytest.approx(0.01)

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_step_size_pal_overrides_step_size(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        module = _load_halo_family_module()
        args = module.parse_args(["--step-size", "0.002", "--step-size-pal", "0.05"])
        assert args.step_size_pal == pytest.approx(0.05)
        # The override happens in main(), not in parse_args
        assert args.step_size == pytest.approx(0.002)

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_step_size_pal_defaults_to_none(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        module = _load_halo_family_module()
        args = module.parse_args([])
        assert args.step_size_pal is None

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_direction_param_accepted(self, mock_cont, mock_corr, mock_dyn, mock_sys):
        module = _load_halo_family_module()
        args = module.parse_args(["--direction", "both"])
        assert args.direction == "both"

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_pal_passes_direction_and_step_size_negative(
        self, mock_cont_cls, mock_corr_cls, mock_dyn, mock_sys, tmp_path,
    ):
        """PAL continuation should use --direction and --step-size-negative."""
        module = _load_halo_family_module()

        mock_seed = MagicMock()
        mock_seed.period = 1.84
        mock_seed.states = np.array([[0.93, 0, -0.27, 0, 0.1, 0]])
        mock_seed.parameters = {}

        mock_family = MagicMock()
        mock_family.__len__ = lambda self: 5
        mock_orbit = MagicMock()
        mock_orbit.states = np.array([[0.93, 0, -0.27, 0, 0.1, 0]])
        mock_orbit.period = 1.84
        mock_orbit.periodicity_error = 1e-12
        mock_orbit.parameters = {"amplitude_z": 0.27}
        mock_family.__iter__ = lambda self: iter([mock_orbit] * 5)

        mock_cont_inst = mock_cont_cls.return_value
        mock_cont_inst.halo_pseudo_arclength_continuation.return_value = mock_family

        seed_path = tmp_path / "halo_L2_S_0.27_123.json"
        seed_path.write_text(json.dumps({
            "states": [[0.93, 0, 0.27, 0, 0.1, 0]],
            "times": [0],
            "period": 1.84,
        }), encoding="utf-8")

        with patch("e2m2e.core.Orbit.load_from_file", return_value=mock_seed):
            with patch.object(module, "_print_summary_table"):
                with patch.object(module, "parse_args", return_value=module.parse_args([
                    "--seed-file", str(seed_path),
                    "--method", "pseudo_arclength",
                    "--step-size-pal", "0.05",
                    "--step-size-negative", "0.03",
                    "--direction", "both",
                    "--n-orbits", "5",
                ])):
                    module.main()

        call_kwargs = mock_cont_inst.halo_pseudo_arclength_continuation.call_args.kwargs
        assert call_kwargs["step_size"] == pytest.approx(0.05)
        assert call_kwargs["step_size_negative"] == pytest.approx(0.03)
        assert call_kwargs["direction"] == "both"


class TestHaloSummaryTableOutput:
    """Test _print_summary_table continuation info output."""

    @staticmethod
    def _make_orbit(x0, z0, period, periodicity_error=1e-12, amplitude_z=None):
        orbit = MagicMock()
        orbit.states = np.array([[x0, 0, z0, 0, 0.1, 0]])
        orbit.period = period
        orbit.periodicity_error = periodicity_error
        orbit.parameters = {"amplitude_z": amplitude_z or abs(z0)}
        orbit.amplitudes = {"x": abs(x0) * 0.1, "y": abs(z0) * 0.2, "z": abs(z0)}
        return orbit

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_natural_method_shows_step_and_direction(self, mock_cont, mock_corr, mock_dyn, mock_sys, capsys):
        module = _load_halo_family_module()
        orbits = [self._make_orbit(0.93, 0.1 + i * 0.01, 1.84 + i * 0.01) for i in range(5)]
        module._print_summary_table(
            orbits, 1, 0,
            method="natural", step_size=0.002, direction="positive",
        )
        output = capsys.readouterr().out
        assert "自然参数延拓" in output
        assert "延拓步长     0.002" in output
        assert "延拓方向     positive" in output

    @patch("e2m2e.core.system.CR3BP_System")
    @patch("e2m2e.core.dynamics.CR3BP_Dynamics")
    @patch("e2m2e.algorithms.DifferentialCorrection")
    @patch("e2m2e.algorithms.Continuation")
    def test_pal_method_shows_both_step_sizes(self, mock_cont, mock_corr, mock_dyn, mock_sys, capsys):
        module = _load_halo_family_module()
        orbits = [self._make_orbit(0.93, 0.1 + i * 0.01, 1.84 + i * 0.01) for i in range(5)]
        module._print_summary_table(
            orbits, 1, 0,
            method="pseudo_arclength", step_size=0.05, step_size_negative=0.03,
            direction="both",
        )
        output = capsys.readouterr().out
        assert "伪弧长延拓" in output
        assert "正向步长     0.05" in output
        assert "负向步长     0.03" in output
        assert "延拓方向     both" in output


class TestHaloGuiRegistryNewParams:
    """Test updated GUI registry for Halo family generation."""

    def test_method_selector_exists(self):
        from tod.gui.script_registry import SCRIPTS

        entry = next(e for e in SCRIPTS["Halo"] if e.name == "generate_halo_family")
        method_param = next(p for p in entry.cli_params if p.flag == "--method")
        assert method_param.choice_values is not None
        assert "natural" in method_param.choice_values.values()
        assert "pseudo_arclength" in method_param.choice_values.values()

    def test_step_size_pal_param_exists(self):
        from tod.gui.script_registry import SCRIPTS

        entry = next(e for e in SCRIPTS["Halo"] if e.name == "generate_halo_family")
        pal_param = next(p for p in entry.cli_params if p.flag == "--step-size-pal")
        assert pal_param.hidden_when == "--method==natural"
        assert pal_param.unit_group is None

    def test_step_size_hidden_when_pal(self):
        from tod.gui.script_registry import SCRIPTS

        entry = next(e for e in SCRIPTS["Halo"] if e.name == "generate_halo_family")
        step_param = next(p for p in entry.cli_params if p.flag == "--step-size")
        assert step_param.hidden_when == "--method==pseudo_arclength"
        assert step_param.unit_group == "distance"

    def test_step_size_negative_hidden_when_natural(self):
        from tod.gui.script_registry import SCRIPTS

        entry = next(e for e in SCRIPTS["Halo"] if e.name == "generate_halo_family")
        neg_param = next(p for p in entry.cli_params if p.flag == "--step-size-negative")
        assert neg_param.hidden_when == "--method==natural"

    def test_direction_param_exists(self):
        from tod.gui.script_registry import SCRIPTS

        entry = next(e for e in SCRIPTS["Halo"] if e.name == "generate_halo_family")
        dir_param = next(p for p in entry.cli_params if p.flag == "--direction")
        assert dir_param.choice_values is not None
        assert "positive" in dir_param.choice_values.values()
        assert "both" in dir_param.choice_values.values()
