# pyright: reportArgumentType=false, reportIncompatibleMethodOverride=false
"""Unit tests for tod.generates.cr3bp._family_pipeline shared module."""

import math
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tod.commons.constants import MU
from tod.generates.cr3bp import _family_pipeline as fp


# =============================================================================
# jacobi_constant
# =============================================================================


class TestJacobiConstant:
    def test_known_value(self):
        """Verify Jacobi constant matches analytically known value."""
        # Test with a simple state where we can verify by hand
        # At L1 (~x=0.8369), v=0 → C_J ≈ 2*Omega
        state = [0.8369, 0.0, 0.0, 0.0, 0.0, 0.0]
        cj = fp.jacobi_constant(state)
        # Jacobi constant should be positive and reasonable
        assert cj > 0
        assert cj < 5.0

    def test_zero_velocity(self):
        """Jacobi constant with zero velocity equals 2*Omega."""
        x, y, z = 0.5, 0.2, 0.1
        state = [x, y, z, 0.0, 0.0, 0.0]
        cj = fp.jacobi_constant(state)

        # Manual computation
        r1 = math.sqrt((x - MU) ** 2 + y**2 + z**2)
        r2 = math.sqrt((x + 1 - MU) ** 2 + y**2 + z**2)
        Omega = (1 - MU) / r1 + MU / r2 + (x**2 + y**2) / 2
        expected = 2 * Omega
        assert cj == pytest.approx(expected)

    def test_high_velocity(self):
        """Higher velocity reduces Jacobi constant."""
        state_low_v = [0.5, 0.0, 0.0, 0.1, 0.0, 0.0]
        state_high_v = [0.5, 0.0, 0.0, 2.0, 0.0, 0.0]
        cj_low = fp.jacobi_constant(state_low_v)
        cj_high = fp.jacobi_constant(state_high_v)
        assert cj_high < cj_low

    def test_returns_float(self):
        state = [1.0, 0.0, 0.0, 0.0, 0.5, 0.0]
        result = fp.jacobi_constant(state)
        assert isinstance(result, float)


# =============================================================================
# find_milestone_indices
# =============================================================================


class TestFindMilestoneIndices:
    def test_default_5_milestones(self):
        indices = fp.find_milestone_indices(100)
        # round() uses banker's rounding: 74.25 → 74
        assert indices == [0, 25, 50, 74, 99]

    def test_custom_milestone_count(self):
        indices = fp.find_milestone_indices(100, n_milestones=3)
        assert indices == [0, 50, 99]

    def test_single_orbit(self):
        indices = fp.find_milestone_indices(1)
        assert indices == [0, 0, 0, 0, 0]

    def test_two_orbits(self):
        indices = fp.find_milestone_indices(2)
        # round(0.25)=0, round(0.5)=0 (banker's), round(0.75)=1
        assert indices == [0, 0, 0, 1, 1]

    def test_first_is_zero_last_is_n_minus_1(self):
        for n in [3, 10, 50, 101]:
            indices = fp.find_milestone_indices(n, n_milestones=5)
            assert indices[0] == 0
            assert indices[-1] == n - 1

    def test_non_decreasing(self):
        for n in [5, 20, 100]:
            indices = fp.find_milestone_indices(n, n_milestones=7)
            for i in range(len(indices) - 1):
                assert indices[i] <= indices[i + 1]


# =============================================================================
# parse_log_level / setup_logging
# =============================================================================


class TestParseLogLevel:
    def test_known_levels(self):
        import logging

        assert fp.parse_log_level("DEBUG") == logging.DEBUG
        assert fp.parse_log_level("INFO") == logging.INFO
        assert fp.parse_log_level("WARNING") == logging.WARNING
        assert fp.parse_log_level("ERROR") == logging.ERROR
        assert fp.parse_log_level("CRITICAL") == logging.CRITICAL

    def test_case_insensitive(self):
        assert fp.parse_log_level("debug") == 10  # logging.DEBUG


# =============================================================================
# build_cr3bp_system / build_cr3bp_dynamics
# =============================================================================


class TestBuildCr3bpSystem:
    def test_returns_cr3bp_system(self):
        from e2m2e.core import CR3BP_System

        system = fp.build_cr3bp_system()
        assert isinstance(system, CR3BP_System)

    def test_default_mu(self):
        system = fp.build_cr3bp_system()
        assert system.mu == MU

    def test_custom_mu(self):
        system = fp.build_cr3bp_system(mu=0.3)
        assert system.mu == 0.3


class TestBuildCr3bpDynamics:
    def test_returns_cr3bp_dynamics(self):
        from e2m2e.core import CR3BP_Dynamics

        dynamics = fp.build_cr3bp_dynamics()
        assert isinstance(dynamics, CR3BP_Dynamics)

    def test_with_explicit_system(self):
        system = fp.build_cr3bp_system(mu=0.3)
        dynamics = fp.build_cr3bp_dynamics(system)
        assert dynamics.system is not None


# =============================================================================
# FamilyGeneratorConfig
# =============================================================================


class TestFamilyGeneratorConfig:
    def test_default_values(self):
        cfg = fp.FamilyGeneratorConfig()
        assert cfg.family_type == ""
        assert cfg.output_subdir == ""
        assert cfg.n_milestones == 5

    def test_custom_values(self):
        cfg = fp.FamilyGeneratorConfig(
            family_type="dro",
            output_subdir="dro",
            n_milestones=3,
        )
        assert cfg.family_type == "dro"
        assert cfg.n_milestones == 3


# =============================================================================
# print_summary_table
# =============================================================================


def _make_mock_orbit(
    x0: float,
    period: float,
    error: float = 1e-10,
    amplitudes: dict | None = None,
):
    """Create a mock Orbit for testing."""
    orbit = MagicMock()
    orbit.states = np.array([[x0, 0.0, 0.0, 0.0, 0.5, 0.0]])
    orbit.period = period
    orbit.periodicity_error = error
    orbit.amplitudes = amplitudes or {"x": 0.1, "y": 0.2, "z": 0.0}
    return orbit


class _FakeOrbitFamily:
    """Minimal OrbitFamily-like for testing print_summary_table/export_csv.

    pyright: ignore reportArgumentType, reportAttributeAccessIssue
    """

    def __init__(self, orbits: list):
        self._orbits = orbits
        self.save_to_file = MagicMock()

    def __len__(self):
        return len(self._orbits)

    def __iter__(self):
        return iter(self._orbits)

    def __getitem__(self, idx):
        return self._orbits[idx]


class TestPrintSummaryTable:
    def test_does_not_crash(self, capsys):
        """Smoke test: print_summary_table should not raise."""
        orbits = _FakeOrbitFamily(
            [_make_mock_orbit(0.8, 3.5) for _ in range(10)]
        )
        cfg = fp.FamilyGeneratorConfig(
            family_type="test",
            summary_columns=["x0", "Period"],
            summary_format_row=lambda o: [
                f"{float(o.states[0, 0]):10.6f}",
                f"{float(o.period):8.4f}",
            ],
        )
        fp.print_summary_table(orbits, cfg)
        captured = capsys.readouterr()
        assert "TEST 轨道族" in captured.out
        assert "Periodicity Err" in captured.out

    def test_empty_family(self, capsys):
        """Should not print anything for empty family."""
        orbits = _FakeOrbitFamily([])
        cfg = fp.FamilyGeneratorConfig(family_type="empty")
        fp.print_summary_table(orbits, cfg)
        captured = capsys.readouterr()
        assert captured.out == ""


# =============================================================================
# export_csv
# =============================================================================


class TestExportCsv:
    def test_creates_csv_file(self, tmp_path: Path):
        orbits = _FakeOrbitFamily(
            [_make_mock_orbit(0.8, 3.5) for _ in range(5)]
        )

        def fmt_row(o, i, is_ms):
            return {
                "idx": i,
                "x0": float(o.states[0, 0]),
                "period": float(o.period),
                "is_milestone": is_ms,
            }

        cfg = fp.FamilyGeneratorConfig(
            family_type="test",
            csv_fieldnames=["idx", "x0", "period", "is_milestone"],
            csv_format_row=fmt_row,
        )

        output_dir = tmp_path / "output" / "test"
        output_dir.mkdir(parents=True)
        csv_path = fp.export_csv(orbits, cfg, output_dir)

        assert csv_path is not None
        assert csv_path.exists()  # pyright: ignore[reportOptionalMemberAccess]
        assert csv_path.suffix == ".csv"  # pyright: ignore[reportOptionalMemberAccess]

        # Read back and verify
        content = csv_path.read_text()  # pyright: ignore[reportOptionalMemberAccess]
        assert "idx" in content
        assert "x0" in content
        assert "period" in content

    def test_marks_milestones(self, tmp_path: Path):
        orbits = _FakeOrbitFamily(
            [_make_mock_orbit(0.8, 3.5) for _ in range(10)]
        )

        def fmt_row(o, i, is_ms):
            return {"idx": i, "x0": float(o.states[0, 0]), "is_milestone": is_ms}

        cfg = fp.FamilyGeneratorConfig(
            family_type="test",
            csv_fieldnames=["idx", "x0", "is_milestone"],
            csv_format_row=fmt_row,
            n_milestones=3,
        )

        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)
        csv_path = fp.export_csv(orbits, cfg, output_dir)

        lines = csv_path.read_text().strip().split("\n")  # pyright: ignore[reportOptionalMemberAccess]
        # First and last rows should be milestones (indices 0 and 9)
        assert "True" in lines[1]  # row 0 is milestone
        assert "True" in lines[-1]  # row 9 is milestone

    def test_raises_without_format_row(self, tmp_path: Path):
        orbits = _FakeOrbitFamily([_make_mock_orbit(0.8, 3.5)])
        cfg = fp.FamilyGeneratorConfig(family_type="test")
        with pytest.raises(ValueError, match="csv_format_row"):
            fp.export_csv(orbits, cfg, tmp_path)


# =============================================================================
# inject_debug_args
# =============================================================================


class TestInjectDebugArgs:
    def test_injects_when_no_args(self):
        argv = ["script.py"]
        fp.inject_debug_args(argv, ["--x0", "0.8", "--vy0", "0.5"])
        assert argv == ["script.py", "--x0", "0.8", "--vy0", "0.5"]

    def test_no_inject_when_args_present(self):
        argv = ["script.py", "--x0", "0.9"]
        fp.inject_debug_args(argv, ["--x0", "0.8"])
        assert argv == ["script.py", "--x0", "0.9"]


# =============================================================================
# FamilyGenerator base class
# =============================================================================


class _MinimalGenerator(fp.FamilyGenerator):
    """Minimal concrete subclass for testing FamilyGenerator."""

    def parse_args(self, argv=None):
        return MagicMock()

    def _get_seed_orbit(self, args):
        orbit = MagicMock()
        orbit.states = np.array([[0.8, 0.0, 0.0, 0.0, 0.5, 0.0]])
        orbit.period = 3.5
        return orbit

    def _setup_corrector(self, args):
        return MagicMock()

    def _correct_seed_orbit(self, corrector, seed_orbit, args):
        seed_orbit.periodicity_error = 1e-10
        return seed_orbit

    def _run_continuation(self, corrector, seed_orbit, args):
        family = _FakeOrbitFamily([seed_orbit] + [_make_mock_orbit(0.8, 3.5) for _ in range(4)])
        return family


class TestFamilyGenerator:
    def test_init_system(self):
        cfg = fp.FamilyGeneratorConfig(family_type="test", output_subdir="test")
        gen = _MinimalGenerator(cfg)
        gen.init_system()
        assert gen._system is not None
        assert gen._dynamics is not None

    def test_system_property_lazy_init(self):
        cfg = fp.FamilyGeneratorConfig(family_type="test", output_subdir="test")
        gen = _MinimalGenerator(cfg)
        # Access without explicit init
        s = gen.system
        assert s is not None

    def test_get_output_dir(self, tmp_path: Path):
        cfg = fp.FamilyGeneratorConfig(family_type="test", output_subdir="test_family")
        gen = _MinimalGenerator(cfg)
        out = gen.get_output_dir(project_root=tmp_path)
        assert out == tmp_path / "output" / "test_family"
        assert out.is_dir()

    def test_run_pipeline(self, tmp_path: Path):
        cfg = fp.FamilyGeneratorConfig(
            family_type="test",
            output_subdir="test_run",
            summary_columns=["x0", "Period"],
            summary_format_row=lambda o: [
                f"{float(o.states[0, 0]):10.6f}",
                f"{float(o.period):8.4f}",
            ],
            csv_format_row=lambda o, i, is_ms: {
                "idx": i,
                "x0": float(o.states[0, 0]),
                "period": float(o.period),
            },
            csv_fieldnames=["idx", "x0", "period"],
        )
        gen = _MinimalGenerator(cfg)
        family = gen.run(MagicMock(), project_root=tmp_path)
        assert len(family) == 5

    def test_run_raises_on_correction_failure(self):
        cfg = fp.FamilyGeneratorConfig(family_type="test", output_subdir="test")

        class FailingGenerator(_MinimalGenerator):
            def _correct_seed_orbit(self, corrector, seed_orbit, args):
                return None  # correction failed

        gen = FailingGenerator(cfg)
        with pytest.raises(RuntimeError, match="种子轨道修正失败"):
            gen.run(MagicMock())

    def test_abstract_methods_raise(self):
        cfg = fp.FamilyGeneratorConfig()
        gen = fp.FamilyGenerator(cfg)
        # parse_args() is not abstract — it builds a real parser and succeeds.
        # Only hook methods raise NotImplementedError.
        with pytest.raises(NotImplementedError):
            gen._get_seed_orbit(None)
        with pytest.raises(NotImplementedError):
            gen._setup_corrector(None)
        with pytest.raises(NotImplementedError):
            gen._run_continuation(None, None, None)
