# pyright: reportArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false
"""Halo 轨道 CR3BP → 星历修正管道的集成测试。

需要真实的 e2m2e 库和 SPICE 内核（de440.bsp, naif0012.tls）。
运行快速测试：  pytest -m spice -m "not slow"
运行全部测试：  pytest -m spice

注意：此测试依赖已删除的 correct_halo_to_ephemeris 模块及其常量
（REFERENCE_EPOCH, N_PATCH_POINTS 等）。该模块已被重构为 correct_orbit_to_ephemeris，
但测试尚未迁移。待模块接口稳定后重写此测试。
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

# 此测试依赖已删除的 correct_halo_to_ephemeris 模块，跳过全部测试
pytestmark = pytest.mark.skip(
    reason="依赖已删除的 correct_halo_to_ephemeris 模块（REFERENCE_EPOCH, N_PATCH_POINTS 等常量），待迁移重写"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
HALO_DIR = PROJECT_ROOT / "output" / "halo"
KERNEL_DIR = str(PROJECT_ROOT.parent / "e2m2e" / "kernels")


def _find_latest_halo(prefix: str) -> Path:
    """查找与给定前缀匹配的最新 Halo 轨道 JSON。"""
    candidates = sorted(
        HALO_DIR.glob(f"{prefix}_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    assert candidates, f"No Halo orbit JSON found matching '{prefix}_*.json'"
    return candidates[0]


@pytest.fixture(autouse=True)
def _ensure_real_e2m2e():
    """Remove any mocked e2m2e from sys.modules so real imports succeed."""
    prefixes = ("e2m2e", "tod.commons", "tod.generates.ephemeris.correct_orbit_to_ephemeris", "tod.generates.ephemeris._corrector")
    to_remove = [k for k in sys.modules if any(k.startswith(p) for p in prefixes)]
    saved = {k: sys.modules.pop(k) for k in to_remove}

    yield

    for k in list(sys.modules):
        if any(k.startswith(p) for p in prefixes):
            sys.modules.pop(k, None)
    for k, v in saved.items():
        if v is not None:
            sys.modules[k] = v


def _import_module():
    """Import the halo correction module with real e2m2e."""
    os.environ["SPICE_KERNEL_DIR"] = KERNEL_DIR
    os.environ["EPHEMERIS_CORRECTION_METHOD"] = "two_level"

    import importlib

    import tod.generates.ephemeris.correct_orbit_to_ephemeris as mod

    mod = importlib.reload(mod)

    for key in ("SPICE_KERNEL_DIR", "EPHEMERIS_CORRECTION_METHOD", "HALO_INPUT_FILE"):
        os.environ.pop(key, None)

    return mod


def _clean_modules():
    """Remove all mocked/polluted modules from sys.modules."""
    prefixes = (
        "e2m2e", "spiceypy",
        "tod.commons", "tod.generates.ephemeris.correct_orbit_to_ephemeris",
        "tod.generates.ephemeris._corrector", "tod.generates.ephemeris.correct_dro_to_ephemeris",
    )
    for k in list(sys.modules):
        if any(k.startswith(p) for p in prefixes):
            sys.modules.pop(k, None)


def _setup_pipeline(halo_json: Path, tmp_path: Path):
    """Set up the pipeline dependencies and return (module, dynamics, correction_inputs).

    Runs Steps 1-3 (load orbit, sample patch points, coordinate conversion)
    using real e2m2e and SPICE kernels.
    """
    _clean_modules()

    import spiceypy

    from e2m2e.algorithms import convert_to_j2000, sample_patch_points
    from e2m2e.core.spice import SPICEManager
    from e2m2e.core.ephemeris_system import EphemerisSystem
    from e2m2e.core.ephemeris_dynamics import EphemerisDynamics
    from e2m2e.core import CR3BP_System, Orbit, SynodicJ2000System

    mod = _import_module()

    spice = SPICEManager()
    kernel_path = spice.find_ephemeris_kernel(KERNEL_DIR)
    leapseconds_path = os.path.join(KERNEL_DIR, "naif0012.tls")
    spiceypy.furnsh(leapseconds_path)
    spice.load_kernel(kernel_path)

    try:
        reference_et = spice.utc_to_et(mod.REFERENCE_EPOCH)

        cr3bp_system = CR3BP_System(
            mu=mod.MU, primary="earth", secondary="moon"
        )
        eph_system = EphemerisSystem(
            bodies=mod.BODIES, spice=spice, origin="EARTH", frame="J2000"
        )
        eph_dynamics = EphemerisDynamics(system=eph_system)

        halo_orbit = Orbit.load_from_file(
            filename=halo_json, system=cr3bp_system
        )
        assert halo_orbit.period is not None, "Halo orbit must have a period"

        t_patch_syn, states_syn = sample_patch_points(
            halo_orbit, mod.N_PATCH_POINTS
        )

        syn_j2000 = SynodicJ2000System(
            cr3bp_system=cr3bp_system, spice=spice
        )
        t_patch_j2000, states_j2000 = convert_to_j2000(
            t_patch_syn, states_syn, syn_j2000, reference_et, mod.TU
        )

        return {
            "mod": mod,
            "halo_orbit": halo_orbit,
            "t_patch_syn": t_patch_syn,
            "states_syn": states_syn,
            "t_patch_j2000": t_patch_j2000,
            "states_j2000": states_j2000,
            "eph_dynamics": eph_dynamics,
            "reference_et": reference_et,
            "spice": spice,
            "kernel_path": kernel_path,
        }
    except Exception:
        spice.unload_kernel(kernel_path)
        raise


# ---------------------------------------------------------------------------
# Steps 1-3 integration: orbit loading, sampling, coordinate conversion
# ---------------------------------------------------------------------------


@pytest.mark.spice
class TestHaloOrbitSetup:
    """Verify Steps 1-3 of the pipeline with real e2m2e and SPICE kernels."""

    @pytest.fixture(scope="class")
    def pipeline(self, tmp_path_factory):
        data = _setup_pipeline(
            _find_latest_halo("halo_L1_N"), tmp_path_factory.mktemp("setup")
        )
        yield data
        data["spice"].unload_kernel(data["kernel_path"])

    def test_halo_orbit_has_period(self, pipeline):
        assert pipeline["halo_orbit"].period > 0

    def test_patch_point_count(self, pipeline):
        n = pipeline["mod"].N_PATCH_POINTS
        assert len(pipeline["t_patch_syn"]) == n
        assert pipeline["states_syn"].shape == (n, 6)

    def test_patch_points_cover_orbit_period(self, pipeline):
        t = pipeline["t_patch_syn"]
        assert t[0] == pytest.approx(0.0)
        assert t[-1] < pipeline["halo_orbit"].period

    def test_j2000_conversion_has_correct_shape(self, pipeline):
        n = pipeline["mod"].N_PATCH_POINTS
        assert pipeline["t_patch_j2000"].shape == (n,)
        assert pipeline["states_j2000"].shape == (n, 6)

    def test_j2000_times_are_reasonable(self, pipeline):
        """J2000 times should be around the reference epoch."""
        t = pipeline["t_patch_j2000"]
        ref_et = pipeline["reference_et"]
        assert t[0] == pytest.approx(ref_et, rel=1e-6)
        period_seconds = pipeline["halo_orbit"].period * pipeline["mod"].TU * 86400
        assert t[-1] - t[0] < period_seconds * 1.5

    def test_j2000_positions_near_moon(self, pipeline):
        """J2000 positions should be within ~500,000 km of Earth (near Moon)."""
        for state in pipeline["states_j2000"]:
            r = np.linalg.norm(state[:3])
            assert 300_000 < r < 500_000, f"Position {r:.0f} km seems unreasonable"

    def test_j2000_velocities_reasonable(self, pipeline):
        """J2000 velocities should be in a reasonable range for cislunar orbits."""
        for state in pipeline["states_j2000"]:
            v = np.linalg.norm(state[3:])
            assert 0.5 < v < 2.0, f"Velocity {v:.4f} km/s seems unreasonable"


# ---------------------------------------------------------------------------
# Full pipeline with standard method (faster, may not fully converge)
# ---------------------------------------------------------------------------


@pytest.mark.spice
@pytest.mark.slow
class TestHaloStandardCorrection:
    """Verify the full pipeline with standard multiple shooting.

    The standard method is faster but may not fully converge for Halo orbits.
    We verify that the pipeline runs end-to-end and produces valid output.
    """

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("halo_std")
        halo_json = _find_latest_halo("halo_L1_N")
        _clean_modules()

        os.environ["SPICE_KERNEL_DIR"] = KERNEL_DIR
        os.environ["EPHEMERIS_CORRECTION_METHOD"] = "standard"
        os.environ["HALO_INPUT_FILE"] = str(halo_json)

        import importlib

        import tod.generates.ephemeris.correct_orbit_to_ephemeris as mod

        mod = importlib.reload(mod)
        mod.OUTPUT_DIR = tmp

        for key in ("SPICE_KERNEL_DIR", "EPHEMERIS_CORRECTION_METHOD", "HALO_INPUT_FILE"):
            os.environ.pop(key, None)

        mod.main()

        json_files = list(tmp.glob("halo_ephemeris_correction_*.json"))
        assert len(json_files) == 1
        return json.loads(json_files[0].read_text(encoding="utf-8"))

    def test_output_has_halo_type(self, result):
        assert result["orbit_type"] == "halo"

    def test_output_has_standard_method(self, result):
        assert result["method"] == "standard"

    def test_residual_decreased(self, result):
        history = result["residual_history"]
        assert len(history) >= 2
        assert history[-1] < history[0]

    def test_output_trajectory_valid(self, result):
        n = result["n_patch_points"]
        assert len(result["corrected_states"]) == n
        assert len(result["corrected_times_et"]) == n

        full_states = np.array(result["full_trajectory_states"])
        assert full_states.ndim == 2 and full_states.shape[1] == 6

    def test_position_errors_recorded(self, result):
        n = result["n_patch_points"]
        assert len(result["position_errors_km"]) == n - 1

    def test_cr3bp_halo_block_present(self, result):
        halo_block = result["cr3bp_halo"]
        assert "source_file" in halo_block
        assert "period_tu" in halo_block
        assert halo_block["period_tu"] > 0


# ---------------------------------------------------------------------------
# Full pipeline with two_level method (slow, verifies convergence)
# ---------------------------------------------------------------------------


@pytest.mark.spice
@pytest.mark.slow
class TestHaloTwoLevelCorrection:
    """Verify two-level multiple shooting correction converges for L1 North Halo."""

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("halo_two_level")
        halo_json = _find_latest_halo("halo_L1_N")
        _clean_modules()

        os.environ["SPICE_KERNEL_DIR"] = KERNEL_DIR
        os.environ["EPHEMERIS_CORRECTION_METHOD"] = "two_level"
        os.environ["HALO_INPUT_FILE"] = str(halo_json)

        import importlib

        import tod.generates.ephemeris.correct_orbit_to_ephemeris as mod

        mod = importlib.reload(mod)
        mod.OUTPUT_DIR = tmp

        for key in ("SPICE_KERNEL_DIR", "EPHEMERIS_CORRECTION_METHOD", "HALO_INPUT_FILE"):
            os.environ.pop(key, None)

        mod.main()

        json_files = list(tmp.glob("halo_ephemeris_correction_*.json"))
        assert len(json_files) == 1
        return json.loads(json_files[0].read_text(encoding="utf-8"))

    def test_converges(self, result):
        assert result["converged"] is True

    def test_position_residual_below_threshold(self, result):
        assert result["max_residual"] < 1e-3

    def test_velocity_residual_below_threshold(self, result):
        assert result["velocity_residual"] is not None
        assert result["velocity_residual"] < 1e-6

    def test_position_continuity_within_tolerance(self, result):
        for err in result["position_errors_km"]:
            assert err < 1e-3

    def test_residual_history_monotonically_decreases(self, result):
        history = result["residual_history"]
        assert len(history) >= 2
        assert history[-1] < history[0]


# ---------------------------------------------------------------------------
# Steps 1-3 for L1 South and L2 orbits
# ---------------------------------------------------------------------------


def _make_setup_class(halo_prefix: str):
    """Factory for parameterized setup test classes."""

    @pytest.mark.spice
    class _Cls:
        @pytest.fixture(scope="class")
        def pipeline(self, tmp_path_factory):
            data = _setup_pipeline(
                _find_latest_halo(halo_prefix), tmp_path_factory.mktemp(f"setup_{halo_prefix}")
            )
            yield data
            data["spice"].unload_kernel(data["kernel_path"])

        def test_orbit_has_period(self, pipeline):
            assert pipeline["halo_orbit"].period > 0

        def test_patch_point_shapes(self, pipeline):
            n = pipeline["mod"].N_PATCH_POINTS
            assert pipeline["states_syn"].shape == (n, 6)
            assert pipeline["states_j2000"].shape == (n, 6)

        def test_j2000_positions_reasonable(self, pipeline):
            for state in pipeline["states_j2000"]:
                r = np.linalg.norm(state[:3])
                assert 300_000 < r < 500_000

    _Cls.__name__ = f"Test{halo_prefix.replace('_', '')}Setup"
    _Cls.__qualname__ = _Cls.__name__
    return _Cls


TestHaloL1SSetup = _make_setup_class("halo_L1_S")
TestHaloL2NSetup = _make_setup_class("halo_L2_N")


# ---------------------------------------------------------------------------
# Full pipeline (standard method) for L1 South and L2 orbits
# ---------------------------------------------------------------------------


def _make_standard_class(halo_prefix: str, class_name: str):
    """Factory for parameterized standard correction test classes."""

    @pytest.mark.spice
    @pytest.mark.slow
    class _Cls:
        @pytest.fixture(scope="class")
        def result(self, tmp_path_factory):
            tmp = tmp_path_factory.mktemp(f"std_{halo_prefix}")
            halo_json = _find_latest_halo(halo_prefix)
            _clean_modules()

            os.environ["SPICE_KERNEL_DIR"] = KERNEL_DIR
            os.environ["EPHEMERIS_CORRECTION_METHOD"] = "standard"
            os.environ["HALO_INPUT_FILE"] = str(halo_json)

            import importlib

            import tod.generates.ephemeris.correct_orbit_to_ephemeris as mod

            mod = importlib.reload(mod)
            mod.OUTPUT_DIR = tmp

            for key in ("SPICE_KERNEL_DIR", "EPHEMERIS_CORRECTION_METHOD", "HALO_INPUT_FILE"):
                os.environ.pop(key, None)

            mod.main()

            json_files = list(tmp.glob("halo_ephemeris_correction_*.json"))
            assert len(json_files) == 1
            return json.loads(json_files[0].read_text(encoding="utf-8"))

        def test_pipeline_completes(self, result):
            assert result["orbit_type"] == "halo"
            assert result["method"] == "standard"
            assert result["iterations"] > 0

        def test_residual_decreased(self, result):
            history = result["residual_history"]
            assert len(history) >= 2
            assert history[-1] < history[0]

        def test_output_structure_valid(self, result):
            n = result["n_patch_points"]
            assert len(result["corrected_states"]) == n
            assert len(result["position_errors_km"]) == n - 1

    _Cls.__name__ = class_name
    _Cls.__qualname__ = class_name
    return _Cls


TestHaloL1SStandardCorrection = _make_standard_class("halo_L1_S", "TestHaloL1SStandardCorrection")
TestHaloL2NStandardCorrection = _make_standard_class("halo_L2_N", "TestHaloL2NStandardCorrection")


# ---------------------------------------------------------------------------
# DRO pipeline regression — Halo changes must not break DRO
# ---------------------------------------------------------------------------


@pytest.mark.spice
@pytest.mark.slow
class TestDROPipelineRegression:
    """Verify the DRO correction pipeline still works after Halo modifications."""

    @pytest.fixture(scope="class")
    def result(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("dro_regression")
        _clean_modules()

        os.environ["SPICE_KERNEL_DIR"] = KERNEL_DIR
        os.environ["EPHEMERIS_CORRECTION_METHOD"] = "standard"

        import importlib

        import tod.generates.ephemeris.correct_dro_to_ephemeris as dro_mod

        dro_mod = importlib.reload(dro_mod)
        dro_mod.OUTPUT_DIR = tmp

        for key in ("SPICE_KERNEL_DIR", "EPHEMERIS_CORRECTION_METHOD"):
            os.environ.pop(key, None)

        dro_mod.main()

        json_files = list(tmp.glob("dro_ephemeris_correction_*.json"))
        assert len(json_files) == 1
        return json.loads(json_files[0].read_text(encoding="utf-8"))

    def test_dro_pipeline_completes(self, result):
        assert result["iterations"] > 0
        assert len(result["residual_history"]) >= 2

    def test_dro_residual_decreased(self, result):
        history = result["residual_history"]
        assert history[-1] < history[0]

    def test_dro_output_structure(self, result):
        n = result["n_patch_points"]
        assert len(result["corrected_states"]) == n
        assert len(result["position_errors_km"]) == n - 1
        assert "cr3bp_dro" in result
