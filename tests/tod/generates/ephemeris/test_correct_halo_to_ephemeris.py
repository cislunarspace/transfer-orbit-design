"""Tests for correct_halo_to_ephemeris pipeline."""

import importlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, mock_open, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Mock e2m2e heavy dependencies before importing the module under test.
# e2m2e requires pydantic/spiceypy kernels which are not available in CI.
# ---------------------------------------------------------------------------

def _make_e2m2e_mocks():
    """Build lightweight mock modules for e2m2e and spiceypy."""
    spiceypy_mod = MagicMock()
    spiceypy_mod.furnsh = MagicMock()

    e2m2e_mod = MagicMock()
    core = MagicMock()
    alg = MagicMock()

    # CR3BP_System.from_known_system → returns object with mu/DU/TU/VU
    _em = MagicMock()
    _em.mu = 1.21506683e-2
    _em.DU = 384405.0
    _em.TU = 4.34811305
    _em.VU = 1023.23281
    core.CR3BP_System = MagicMock()
    core.CR3BP_System.from_known_system = MagicMock(return_value=_em)
    core.CR3BP_System.return_value = MagicMock()
    core.Orbit = MagicMock()
    core.SPICEManager = MagicMock()
    core.EphemerisSystem = MagicMock()
    core.EphemerisDynamics = MagicMock()
    core.SynodicJ2000Transformation = MagicMock()

    alg.sample_patch_points = MagicMock()
    alg.convert_to_j2000 = MagicMock()

    e2m2e_mod.core = core
    e2m2e_mod.algorithms = alg

    return {
        "spiceypy": spiceypy_mod,
        "e2m2e": e2m2e_mod,
        "e2m2e.core": core,
        "e2m2e.algorithms": alg,
    }


@pytest.fixture(autouse=True)
def _mock_e2m2e():
    """Inject lightweight mocks for e2m2e and spiceypy into sys.modules."""
    mocks = _make_e2m2e_mocks()
    saved = {}
    for name, mod in mocks.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    for key in list(sys.modules):
        if key.startswith("tod.commons"):
            saved[key] = sys.modules.pop(key)

    saved["tod.generates.ephemeris._corrector"] = sys.modules.pop(
        "tod.generates.ephemeris._corrector", None
    )
    saved["tod.generates.ephemeris.correct_halo_to_ephemeris"] = sys.modules.pop(
        "tod.generates.ephemeris.correct_halo_to_ephemeris", None
    )

    # Force deterministic correction method regardless of env
    saved_env = os.environ.pop("EPHEMERIS_CORRECTION_METHOD", None)
    saved_env_halo = os.environ.pop("HALO_INPUT_FILE", None)

    yield

    for name, orig in saved.items():
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig

    for key in list(sys.modules):
        if key.startswith("tod.commons"):
            sys.modules.pop(key, None)

    # Restore env vars
    if saved_env is not None:
        os.environ["EPHEMERIS_CORRECTION_METHOD"] = saved_env
    if saved_env_halo is not None:
        os.environ["HALO_INPUT_FILE"] = saved_env_halo


@pytest.fixture()
def halo_module():
    return importlib.import_module(
        "tod.generates.ephemeris.correct_halo_to_ephemeris"
    )


# ---------------------------------------------------------------------------
# Tracer bullet: module-level constants
# ---------------------------------------------------------------------------

class TestModuleConstants:
    def test_n_patch_points(self, halo_module):
        assert halo_module.N_PATCH_POINTS == 10

    def test_correction_method(self, halo_module):
        assert halo_module.CORRECTION_METHOD == "two_level"

    def test_reference_epoch(self, halo_module):
        assert halo_module.REFERENCE_EPOCH == "2025-06-21T11:00:06"

    def test_bodies(self, halo_module):
        assert halo_module.BODIES == ["EARTH", "MOON", "SUN"]

    def test_position_continuity_tol(self, halo_module):
        assert halo_module.POSITION_CONTINUITY_TOL == 1e-3

    def test_velocity_continuity_tol(self, halo_module):
        assert halo_module.VELOCITY_CONTINUITY_TOL == 1e-6

    def test_halo_json_file_points_to_halo_dir(self, halo_module):
        parts = Path(halo_module.HALO_JSON_FILE).parts
        assert "halo" in parts

    def test_halo_input_file_env_override(self, halo_module):
        custom_path = str(Path(__file__).resolve().parent / "orbit.json")
        os.environ["HALO_INPUT_FILE"] = custom_path
        try:
            mod = importlib.reload(halo_module)
            assert str(mod.HALO_JSON_FILE) == custom_path
        finally:
            os.environ.pop("HALO_INPUT_FILE", None)
            importlib.reload(halo_module)


# ---------------------------------------------------------------------------
# Orbit loading: raises ValueError when orbit has no period
# ---------------------------------------------------------------------------

class TestOrbitPeriodValidation:
    def test_raises_value_error_when_period_is_none(self, halo_module):
        """main() must raise ValueError if loaded orbit has no period."""
        mock_orbit = MagicMock()
        mock_orbit.period = None
        mock_orbit.states = [[1.0, 0.0, 0.0, 0.0, 0.1, 0.0]]

        mock_spice = MagicMock()
        mock_spice.find_ephemeris_kernel.return_value = "/fake/kernel.bsp"
        mock_spice.utc_to_et.return_value = 1e8
        halo_module.SPICEManager.return_value = mock_spice

        with patch.object(halo_module.Orbit, "load_from_file", return_value=mock_orbit):
            with pytest.raises(ValueError, match="周期"):
                halo_module.main()


# ---------------------------------------------------------------------------
# Full pipeline flow (mocked external deps)
# ---------------------------------------------------------------------------

N = 10


def _fake_halo_orbit():
    orbit = MagicMock()
    orbit.period = 3.68
    orbit.states = [[0.93 + i * 0.01, 0.0, 0.23, 0.0, 0.10, 0.0] for i in range(100)]
    return orbit


def _fake_correction_result(n_patch):
    result = MagicMock()
    result.converged = True
    result.iterations = 5
    result.max_residual = 1e-4
    result.velocity_residual = 1e-7
    result.residual_history = [1e-1, 1e-2, 1e-3, 1e-4]
    result.velocity_residual_history = [1e-2, 1e-4, 1e-6, 1e-7]
    result.t_patch = np.linspace(1e8, 1e8 + 3e5, n_patch)
    result.state_patch = np.random.randn(n_patch, 6) * 1e5
    return result


def _build_propagate_side_effect(correction_result, n_seg):
    """Build side_effect list for propagate: each call returns a dict with states/time."""
    side_effects = []
    for i in range(n_seg):
        prop_states = np.random.randn(50, 6) * 1e5
        prop_states[-1] = correction_result.state_patch[i + 1]
        prop_times = np.linspace(
            correction_result.t_patch[i],
            correction_result.t_patch[i + 1],
            50,
        )
        side_effects.append({"states": prop_states, "time": prop_times})
    return side_effects


class TestFullPipeline:
    def test_pipeline_calls_all_steps(self, halo_module, tmp_path):
        orbit = _fake_halo_orbit()
        correction_result = _fake_correction_result(N)

        mock_spice = MagicMock()
        mock_spice.find_ephemeris_kernel.return_value = "/fake/kernel.bsp"
        mock_spice.utc_to_et.return_value = 1e8
        halo_module.SPICEManager.return_value = mock_spice

        halo_module.Orbit.load_from_file.return_value = orbit

        t_syn = np.linspace(0, orbit.period, N)
        states_syn = np.random.randn(N, 6) * 0.1
        halo_module.sample_patch_points.return_value = (t_syn, states_syn)

        t_j2000 = np.linspace(1e8, 1e8 + 3e5, N)
        states_j2000 = np.random.randn(N, 6) * 1e5
        halo_module.convert_to_j2000.return_value = (t_j2000, states_j2000)

        mock_dyn = MagicMock()
        n_seg = N - 1
        mock_dyn.propagate.side_effect = _build_propagate_side_effect(
            correction_result, n_seg
        )
        halo_module.EphemerisDynamics.return_value = mock_dyn

        halo_module.OUTPUT_DIR = tmp_path

        with patch.object(
            halo_module, "correct_ephemeris_patch_points",
            return_value=correction_result,
        ) as mock_correct:
            halo_module.main()

        halo_module.Orbit.load_from_file.assert_called_once()
        halo_module.sample_patch_points.assert_called_once_with(orbit, N)
        halo_module.convert_to_j2000.assert_called_once()
        mock_correct.assert_called_once()
        assert mock_dyn.propagate.call_count == n_seg


# ---------------------------------------------------------------------------
# Output JSON structure
# ---------------------------------------------------------------------------

class TestOutputJson:
    def test_output_contains_halo_specific_fields(self, halo_module, tmp_path):
        orbit = _fake_halo_orbit()
        correction_result = _fake_correction_result(N)

        mock_spice = MagicMock()
        mock_spice.find_ephemeris_kernel.return_value = "/fake/kernel.bsp"
        mock_spice.utc_to_et.return_value = 1e8
        halo_module.SPICEManager.return_value = mock_spice
        halo_module.Orbit.load_from_file.return_value = orbit
        halo_module.sample_patch_points.return_value = (
            np.linspace(0, orbit.period, N),
            np.random.randn(N, 6) * 0.1,
        )
        halo_module.convert_to_j2000.return_value = (
            np.linspace(1e8, 1e8 + 3e5, N),
            np.random.randn(N, 6) * 1e5,
        )

        mock_dyn = MagicMock()
        mock_dyn.propagate.side_effect = _build_propagate_side_effect(
            correction_result, N - 1
        )
        halo_module.EphemerisDynamics.return_value = mock_dyn
        halo_module.OUTPUT_DIR = tmp_path

        with patch.object(
            halo_module, "correct_ephemeris_patch_points",
            return_value=correction_result,
        ):
            halo_module.main()

        # Read output JSON
        json_files = list(tmp_path.glob("halo_ephemeris_correction_*.json"))
        assert len(json_files) == 1
        data = json.loads(json_files[0].read_text(encoding="utf-8"))

        assert data["orbit_type"] == "halo"
        assert data["method"] == "two_level"
        assert data["converged"] is True
        assert data["reference_epoch"] == "2025-06-21T11:00:06"
        assert data["bodies"] == ["EARTH", "MOON", "SUN"]
        assert data["n_patch_points"] == N

        # Halo-specific cr3bp_halo block
        halo_block = data["cr3bp_halo"]
        assert "source_file" in halo_block
        assert "x0" in halo_block
        assert "vy0" in halo_block
        assert "z0" in halo_block
        assert "period_tu" in halo_block
        assert halo_block["z0"] == 0.23
        assert halo_block["period_tu"] == 3.68

        # Trajectory data
        assert "corrected_states" in data
        assert "corrected_times_et" in data
        assert "full_trajectory_states" in data
        assert "full_trajectory_times_et" in data
        assert "position_errors_km" in data
        assert len(data["position_errors_km"]) == N - 1

        # Residual info
        assert data["max_residual"] == pytest.approx(1e-4)
        assert data["velocity_residual"] == pytest.approx(1e-7)
        assert data["iterations"] == 5


# ---------------------------------------------------------------------------
# Correction method argument
# ---------------------------------------------------------------------------

class TestCorrectionMethodArg:
    def test_passes_two_level_method_to_corrector(self, halo_module, tmp_path):
        orbit = _fake_halo_orbit()
        correction_result = _fake_correction_result(N)

        mock_spice = MagicMock()
        mock_spice.find_ephemeris_kernel.return_value = "/fake/kernel.bsp"
        mock_spice.utc_to_et.return_value = 1e8
        halo_module.SPICEManager.return_value = mock_spice
        halo_module.Orbit.load_from_file.return_value = orbit
        halo_module.sample_patch_points.return_value = (
            np.linspace(0, orbit.period, N),
            np.random.randn(N, 6) * 0.1,
        )
        halo_module.convert_to_j2000.return_value = (
            np.linspace(1e8, 1e8 + 3e5, N),
            np.random.randn(N, 6) * 1e5,
        )

        mock_dyn = MagicMock()
        mock_dyn.propagate.side_effect = _build_propagate_side_effect(
            correction_result, N - 1
        )
        halo_module.EphemerisDynamics.return_value = mock_dyn
        halo_module.OUTPUT_DIR = tmp_path

        with patch.object(
            halo_module, "correct_ephemeris_patch_points",
            return_value=correction_result,
        ) as mock_correct:
            halo_module.main()

        call_args = mock_correct.call_args
        assert call_args[0][0] == "two_level"
        assert call_args.kwargs["tolerance"] == halo_module.POSITION_CONTINUITY_TOL
        assert call_args.kwargs["velocity_tolerance"] == halo_module.VELOCITY_CONTINUITY_TOL


# ---------------------------------------------------------------------------
# Continuity verification + file save
# ---------------------------------------------------------------------------

class TestContinuityAndSave:
    def test_propagates_each_segment_and_saves_json(self, halo_module, tmp_path):
        orbit = _fake_halo_orbit()
        correction_result = _fake_correction_result(N)

        mock_spice = MagicMock()
        mock_spice.find_ephemeris_kernel.return_value = "/fake/kernel.bsp"
        mock_spice.utc_to_et.return_value = 1e8
        halo_module.SPICEManager.return_value = mock_spice
        halo_module.Orbit.load_from_file.return_value = orbit
        halo_module.sample_patch_points.return_value = (
            np.linspace(0, orbit.period, N),
            np.random.randn(N, 6) * 0.1,
        )
        halo_module.convert_to_j2000.return_value = (
            np.linspace(1e8, 1e8 + 3e5, N),
            np.random.randn(N, 6) * 1e5,
        )

        mock_dyn = MagicMock()
        n_seg = N - 1
        side_fx = _build_propagate_side_effect(correction_result, n_seg)
        mock_dyn.propagate.side_effect = side_fx
        halo_module.EphemerisDynamics.return_value = mock_dyn
        halo_module.OUTPUT_DIR = tmp_path

        with patch.object(
            halo_module, "correct_ephemeris_patch_points",
            return_value=correction_result,
        ):
            halo_module.main()

        # Verify propagate called once per segment with correct endpoints
        assert mock_dyn.propagate.call_count == n_seg
        for i, call in enumerate(mock_dyn.propagate.call_args_list):
            state_arg = call[0][0]
            time_arg = call[0][1]
            np.testing.assert_array_equal(state_arg, correction_result.state_patch[i])
            assert time_arg == (
                correction_result.t_patch[i],
                correction_result.t_patch[i + 1],
            )

        # Verify JSON file created with halo filename prefix
        json_files = list(tmp_path.glob("halo_ephemeris_correction_*.json"))
        assert len(json_files) == 1

        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert len(data["position_errors_km"]) == n_seg
        assert len(data["corrected_states"]) == N
        assert len(data["corrected_times_et"]) == N

    def test_spice_kernel_unloaded_on_success(self, halo_module, tmp_path):
        """SPICE kernel must be unloaded even on success path."""
        orbit = _fake_halo_orbit()
        correction_result = _fake_correction_result(N)

        mock_spice = MagicMock()
        mock_spice.find_ephemeris_kernel.return_value = "/fake/kernel.bsp"
        mock_spice.utc_to_et.return_value = 1e8
        halo_module.SPICEManager.return_value = mock_spice
        halo_module.Orbit.load_from_file.return_value = orbit
        halo_module.sample_patch_points.return_value = (
            np.linspace(0, orbit.period, N),
            np.random.randn(N, 6) * 0.1,
        )
        halo_module.convert_to_j2000.return_value = (
            np.linspace(1e8, 1e8 + 3e5, N),
            np.random.randn(N, 6) * 1e5,
        )

        mock_dyn = MagicMock()
        mock_dyn.propagate.side_effect = _build_propagate_side_effect(
            correction_result, N - 1
        )
        halo_module.EphemerisDynamics.return_value = mock_dyn
        halo_module.OUTPUT_DIR = tmp_path

        with patch.object(
            halo_module, "correct_ephemeris_patch_points",
            return_value=correction_result,
        ):
            halo_module.main()

        mock_spice.unload_kernel.assert_called_once_with("/fake/kernel.bsp")
